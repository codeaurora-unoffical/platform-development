# python3

"""Tests for meta_monitor."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import asyncio
import os
import shutil
import tempfile
import unittest
from unittest.mock import Mock

import meta_monitor


class _MockProcess():

  def __init__(self, returncode, stdout, stderr):
    self.returncode = returncode
    self.stdout = stdout
    self.stderr = stderr

  async def wait(self):
    return self.returncode

  async def communicate(self):
    return self.stdout, self.stderr


def _MakeMockCommand(returncode_dict, stdout_dict, stderr_dict):
  """Construct a coroutine to return a MockProcess.

  Parameters are provided as dictionaries where the key is the first argument
  to the subprocess' command line. This allows mock commands to behave
  differently depending on the subcommand issued. Very useful for mocking
  commands such as 'git' where behavior is determined by the second command
  line argument (ex: 'git describe', 'git ls-remote', 'git clone').

  Args:
    returncode_dict: Value to return from the wait() function. Defaults to
      zero if no matching dictionary key.
    stdout_dict: Byte array to return for stdout from the communicate()
      function. Defaults to empty string if no matching dictionary key.
    stderr_dict: Byte array to return for stderr from the communicate()
      function. Defaults to empty string if no matching dictionary key.
  Returns:
    A coroutine that creates a MockProcess instance.
  """
  async def _GetMockProcess(*args, cwd):
    returncode = 0
    stdout = ''.encode()
    stderr = ''.encode()

    if args:
      if args[0] in returncode_dict:
        returncode = returncode_dict[args[0]]

      if args[0] in stdout_dict:
        stdout = stdout_dict[args[0]]

      if args[0] in stderr_dict:
        stderr = stderr_dict[args[0]]

    return _MockProcess(returncode, stdout, stderr)
  return _GetMockProcess


class MetaMonitorTest(unittest.TestCase):

  async def _init_git_repo(self, git_dir):
    proc = await asyncio.create_subprocess_exec(
        'git', 'init', '--quiet', cwd=git_dir)
    returncode = await proc.wait()
    self.assertEqual(returncode, 0)

    proc = await asyncio.create_subprocess_exec(
        'git', 'commit', '--quiet', '--allow-empty', '--message="First"',
        cwd=git_dir)
    returncode = await proc.wait()
    self.assertEqual(returncode, 0)

    proc = await asyncio.create_subprocess_exec(
        'git', 'tag', '-a', 'r0001', '-m', 'Tag r0001', cwd=git_dir)
    returncode = await proc.wait()
    self.assertEqual(returncode, 0)

    proc = await asyncio.create_subprocess_exec(
        'git', 'commit', '--quiet', '--allow-empty', '--message="Second"',
        cwd=git_dir)
    returncode = await proc.wait()
    self.assertEqual(returncode, 0)

    proc = await asyncio.create_subprocess_exec(
        'git', 'tag', '-a', 'r0002', '-m', 'Tag r0002', cwd=git_dir)
    returncode = await proc.wait()
    self.assertEqual(returncode, 0)

  def setUp(self):
    self._temp_dir = tempfile.mkdtemp()
    self._upstream_dir = os.path.join(self._temp_dir, 'upstream')
    os.makedirs(self._upstream_dir)
    asyncio.get_event_loop().run_until_complete(
        self._init_git_repo(self._upstream_dir))

  def tearDown(self):
    shutil.rmtree(self._temp_dir, ignore_errors=True)

  def testFetchGitTagsSuccess(self):
    commands = meta_monitor.MetaMonitorCommands()

    upstream_url = 'file://' + self._upstream_dir
    tags = asyncio.get_event_loop().run_until_complete(
        meta_monitor.fetch_git_tags(commands, upstream_url))
    self.assertEqual(tags, ['r0001', 'r0002'])

  def testCloneGitRepoSuccess(self):
    commands = meta_monitor.MetaMonitorCommands()

    upstream_url = 'file://' + self._upstream_dir
    local_work_dir = os.path.join(self._temp_dir, 'local')
    tag = asyncio.get_event_loop().run_until_complete(
        meta_monitor.clone_git_repo(
            commands, upstream_url, local_work_dir))
    self.assertEqual(tag, 'r0002')

  def testArchiveSuccess(self):
    target = 'snapdragon-high-mid-2018-spf-1-0-1'
    work_dir = '/tmp'
    target_work_dir = os.path.join(work_dir, target)
    tag = 'r1.0.1_00004.0'

    commands = unittest.mock.Mock()

    mock_tar = commands.tar
    mock_tar.side_effect = _MakeMockCommand({}, {}, {})

    mock_gsutil = commands.gsutil
    mock_gsutil.side_effect = _MakeMockCommand({}, {}, {})

    success = asyncio.get_event_loop().run_until_complete(
        meta_monitor.archive_git_repo(
            commands, target, work_dir, target_work_dir, tag))
    self.assertTrue(success)

    mock_tar.assert_called_once_with(
        '-C', target_work_dir,
        '-czf', 'meta-source-%s.tar.gz' % target,
        '.',
        cwd=work_dir)
    mock_gsutil.assert_called_once_with(
        '-q', 'cp', 'meta-source-%s.tar.gz' % target,
        'gs://meta-source/%s/%s/meta-source.tar.gz' % (target, tag),
        cwd='/tmp')


if __name__ == '__main__':
  unittest.main()
