# python3

"""Entry point for Keystone META monitor.

Defines the entry point for the META monitor service. Provides a platform
dependent customization wrapper around the meta_monitor library. Useful for
encapsulating dependencies (ex: google.cloud.logging) that shouldn't
necessarily live in the meta_monitor library itself.
"""

import argparse
import asyncio
import logging
import tempfile

import meta_monitor

# URL template of Qualcomm META repo for each SoC target platform.
GIT_URL_TEMPLATE = 'https://chipmaster2.qti.qualcomm.com/home2/git/google-inc/{}_test_device.git'

# List git repositories to monitor.
META_TARGETS = [
    [GIT_URL_TEMPLATE.format('sdm845-la-2-0'), 'sdm845'],
    [GIT_URL_TEMPLATE.format('snapdragon-high-mid-2017-spf-3-0'), 'sdm660'],
    [GIT_URL_TEMPLATE.format('snapdragon-high-mid-2018-spf-1-0-1'), 'msm8917'],
    [GIT_URL_TEMPLATE.format('sm8150-la-1-0'), 'sm8150']
]


# Route logs to StackDriver. The Google Cloud logging library enables logs
# for INFO level by default.
# Taken from the "Setting up StackDriver Logging for Python" page at
# https://cloud.google.com/logging/docs/setup/python
logger = logging.getLogger(__name__)
try:
  import google.cloud.logging
  client = google.cloud.logging.Client()
  logger.addHandler(client.get_default_handler())
  logger.setLevel(logging.INFO)
except ImportError:
  logger.addHandler(logging.StreamHandler())


def main():
  # Parse command line flags.
  parser = argparse.ArgumentParser()
  parser.add_argument(
      '--meta_poll_interval',
      type=int,
      default=7200,
      help='Time between META poll attempts in seconds.')
  args = parser.parse_args()

  # Create a top level working folder for clone and archive operations.
  work_dir = tempfile.mkdtemp()
  logger.info('Working folder is %s', work_dir)

  # Use actual subprocess commands in production.
  commands = meta_monitor.MetaMonitorCommands()

  # Create a polling loop coroutine for each Qualcomm SoC.
  loop = asyncio.get_event_loop()
  targets = [
      meta_monitor.target_meta_loop(
          commands, target_list[0], target_list[1], args.meta_poll_interval,
          work_dir, loop)
      for target_list in META_TARGETS]

  # Use asyncio.gather() to submit all coroutines to the event loop as
  # recommended by @gvanrossum in the GitHub issue comments at
  # https://github.com/python/asyncio/issues/477#issuecomment-269038238
  try:
    loop.run_until_complete(asyncio.gather(*targets))
  except KeyboardInterrupt:
    logger.warning('Received interrupt: shutting down')
  finally:
    loop.close()


if __name__ == '__main__':
  main()
