# python3

"""Monitors META repos and META Cloud Builds.

Periodically polls META repos to detect new META releases and kick off new META
integration builds. Also monitors META integration builds and pushes build state
to a Cloud SQL database.
"""

import asyncio
import logging
import os
import random
import re


# Extract just the git tag from the output of 'git ls-remote --refs --tags'.
GIT_TAG_REGEX = r'refs/tags/(r[a-z0-9_\.]+)'


# Route logs to StackDriver when running in the Cloud. The Google Cloud logging
# library enables logs for INFO level by default.
# Adapted from the "Setting up StackDriver Logging for Python" page at
# https://cloud.google.com/logging/docs/setup/python
logger = logging.getLogger(__name__)
try:
  import google.cloud.logging
  client = google.cloud.logging.Client()
  logger.addHandler(client.get_default_handler())
  logger.setLevel(logging.INFO)
except ImportError:
  logger.addHandler(logging.StreamHandler())


def make_subprocess_cmd(cmd):
  """Creates a function that returns an async subprocess.

  Args:
    cmd: Command to run in the subprocess. Arguments should be provided when
      calling the returned function.
  Returns:
    A function that creates an asyncio.subprocess.Process instance.
  """
  def subprocess_cmd(*args, cwd):
    logger.info('Running "%s %s"', cmd, ' '.join(args))
    return asyncio.create_subprocess_exec(
        cmd, *args, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE, cwd=cwd)
  return subprocess_cmd


class MetaMonitorCommands:

  def __init__(self):
    self.git = make_subprocess_cmd('git')
    self.tar = make_subprocess_cmd('tar')
    self.gcloud = make_subprocess_cmd('gcloud')
    self.gsutil = make_subprocess_cmd('gsutil')
    self.rm = make_subprocess_cmd('rm')


async def fetch_git_tags(commands, url):
  """Fetch tags from the provided git repository URL.

  Args:
    commands: Subprocess creation object.
    url: URL of git repo to retrieve tags from.
  Returns:
    A list of git tags in the repo. Returns an empty list when the undelying
    git command fails.
  """
  git_subproc = await commands.git(
      'ls-remote', '--refs', '--tags', url, cwd=None)
  stdout, _ = await git_subproc.communicate()
  returncode = await git_subproc.wait()
  if returncode:
    logger.warning('git ls-remote returned %d', returncode)
    return []

  raw_tags = stdout.decode('utf-8', 'ignore')
  meta_tags = re.findall(GIT_TAG_REGEX, raw_tags)
  return meta_tags


async def clone_git_repo(commands, url, target_work_dir):
  """Clone git repository at the provided URL.

  Args:
    commands: Subprocess creation object.
    url: URL of git repo to clone.
    target_work_dir: Path to destination folder for the cloned repo.
  Returns:
    The git tag that is returned by running 'git describe' in the cloned repo.
    Returns the empty string when the underlying commands fail.
  """
  rm_subproc = await commands.rm('-rf', target_work_dir, cwd=None)
  stdout, _ = await rm_subproc.communicate()
  returncode = await rm_subproc.wait()
  if returncode:
    logger.warning('rm returned %d', returncode)
    return ''

  git_clone_subproc = await commands.git(
      'clone', '--depth=1', '--quiet', url, target_work_dir, cwd=None)
  stdout, _ = await git_clone_subproc.communicate()
  returncode = await git_clone_subproc.wait()
  if returncode:
    logger.warning('git clone returned %d', returncode)
    return ''

  git_describe_subproc = await commands.git('describe', cwd=target_work_dir)
  stdout, _ = await git_describe_subproc.communicate()
  returncode = await git_describe_subproc.wait()
  if returncode:
    logger.warning('git describe returned %d', returncode)
    return ''

  meta_tag = stdout.decode('utf-8', 'ignore').strip()
  return meta_tag


async def archive_git_repo(
    commands, alias, work_dir, target_work_dir, git_tag):
  """Zip and upload the target folder to Cloud Storage

  Args:
    commands: Subprocess creation object.
    alias: Shorthand name for the repository.
    work_dir: Top level working folder.
    target_work_dir: Path to the cloned target repository.
    git_tag: Git tag at target repository HEAD.
  Returns:
    True for success. False for failure.
  """
  archive_name = 'meta-source-%s.tar.gz' % alias
  tar_subproc = await commands.tar(
      '-C', target_work_dir, '-czf', archive_name, '.', cwd=work_dir)
  await tar_subproc.communicate()
  returncode = await tar_subproc.wait()
  if returncode:
    logger.warning('%s: tar returned %d', alias, returncode)
    return False

  gsutil_subproc = await commands.gsutil(
      '-q', 'cp', archive_name,
      'gs://meta-source/%s/%s/meta-source.tar.gz' % (alias, git_tag),
      cwd=work_dir)
  await gsutil_subproc.communicate()
  returncode = await gsutil_subproc.wait()
  if returncode:
    logger.warning('%s: gsutil returned %d', alias, returncode)
    return False

  return True


async def cleanup_target(commands, alias, work_dir, target_work_dir):
  """Remove all artifacts

  Args:
    commands: Subprocess creation object.
    alias: Shorthand name for the repository.
    work_dir: Top level working folder.
    target_work_dir: Path to the cloned target repository.
  Returns:
    True for success. False for failure.
  """
  rm_subproc = await commands.rm('-rf', target_work_dir, cwd=None)
  await rm_subproc.communicate()
  returncode = await rm_subproc.wait()
  if returncode:
    logger.warning('rm returned %d', returncode)
    return False

  rm_subproc = await commands.rm(
      '-f', 'meta-source-{}.tar.gz'.format(alias), cwd=work_dir)
  returncode = await rm_subproc.wait()
  if returncode:
    logger.warning('rm returned %d', returncode)
    return False

  return True


async def target_meta_loop(commands, git_url, git_alias, interval, work_dir, loop):
  """Main loop to poll a git repository for new tags.

  Args:
    commands: Subprocess creation object.
    git_url: URL to the repository to patrol.
    git_alias: Human friendly name for the repository.
    interval: Time in seconds to wait between poll attempts.
    loop: A reference to the asyncio event loop in use.
  Returns:
    Nothing. Loops forever.
  """
  target_work_dir = os.path.join(work_dir, git_alias)

  # Stagger the wakeup time of the target loops to avoid hammering the remote
  # server with requests all at once.
  next_wakeup_time = loop.time() + random.randrange(0, interval)

  # TODO(brianorr): Fetch META tags from CloudSQL.
  current_meta_tags = await fetch_target_git_tags(commands, git_url)
  current_meta_tags = current_meta_tags[:-1]

  while True:
    # Start from a clean workspace.
    await cleanup_target(commands, git_alias, work_dir, target_work_dir)

    # Calculate the polling loop's next wake-up time. To stay on schedule we
    # keep incrementing next_wakeup_time by the polling inteval until we
    # arrive at a time in the future.
    while next_wakeup_time < loop.time():
      next_wakeup_time += interval
    sleep_time = max(0, next_wakeup_time - loop.time())
    logger.info('%s: sleeping for %f', git_alias, sleep_time)
    await asyncio.sleep(sleep_time)

    # Retrieve current tags from the remote repo.
    new_tags = await fetch_git_tags(commands, git_url)
    if not new_tags:
      continue
    logger.info('%s: fetched tags: %s', git_alias, ' '.join(new_tags))

    # See if new META tags were added since the last check.
    meta_tags_delta = set(new_tags) - set(current_tags)
    if not meta_tags_delta:
      logger.info('%s: no new tags', git_alias)
      continue
    logger.info('%s: new tags: %s', git_alias, ' '.join(meta_tags_delta))

    # Clone the repo and verify that HEAD points to a new tag.
    git_tag = await clone_git_repo(commands, git_url, target_work_dir)
    if git_tag not in new_tags:
      logger.warning(
          '%s: expected new tags but HEAD points to %s', git_alias, git_tag)
      continue

    # Zip and archive the cloned repo to Cloud Storage.
    archive_success = await archive_git_repo(
        commands, git_alias, work_dir, target_work_dir, git_tag)
    if not archive_success:
      continue

    # TODO(brianorr): Kick off Cloud Build for the new tag.
    current_meta_tags = new_meta_tags
