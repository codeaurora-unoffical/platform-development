"""Runs a command in an Android Build container.
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
import os
import overlay_configs
import re
import subprocess

_IMAGE = 'android-build'


def run(container_command, android_target, docker_bin, meta_dir,
        local_device_path = None):
  """Runs a command in an Android Build container.

  Args:
    container_command: A string with the command to be executed
      inside the container.
    android_target: A string with the name of the target to be prepared
      inside the container.
    docker_bin: A string that invokes docker.
    meta_dir: An optional path to a folder containing the META build.
    local_device_path: If provided, the local USB device at this path is mounted
      inside the container.

  Returns:
    A list of strings with the command executed.
  """
  docker_command = [
      docker_bin, 'run',
      '--mount', 'type=bind,source=%s,target=/src' % os.getcwd(),
  ]
  if meta_dir:
    docker_command.extend([
        '--mount', 'type=bind,source=%s,target=/meta,readonly' % meta_dir
    ])
  if local_device_path:
    docker_command.extend([
        '--mount',
        'type=bind,source=%s,target=%s' % (local_device_path,
                                           local_device_path),
    ])
  docker_command.extend([
      '--rm',
      '--tty',
      '--privileged',
      '--interactive',
      _IMAGE,
      'python', '-B', '/src/development/keystone/nsjail.py',
      '--android_target', android_target,
      '--chroot', '/',
      '--source_dir', '/src',
      '--user_id', str(os.getuid()),
      '--group_id', str(os.getgid())
  ])
  docker_command.extend(['--command', container_command])

  subprocess.check_call(docker_command)

  return docker_command


def get_local_device_path():
  """Gets the device path for the local connected Qualcomm USB device."""
  # Use `lsusb` to find the connected USB devices.
  for line in subprocess.check_output(['lsusb']).split('\n'):
    # Extract the bus and device numbers from the `lsusb` result.
    bus_and_device = re.match(r'.*([0-9]{3}).*([0-9]{3}).*Qualcomm.*', line)
    if bus_and_device:
      return '/dev/bus/usb/%s/%s' % (bus_and_device.group(1),
                                     bus_and_device.group(2))
  raise RuntimeError('Unable to find a connected Qualcomm device.')


def main():
  # Use the top level module docstring for the help description
  parser = argparse.ArgumentParser(
      description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument(
      '--container_command',
      default='/bin/bash',
      help='Command to be executed inside the container. '
      'Defaults to /bin/bash.')
  parser.add_argument(
      '--android_target',
      choices=overlay_configs.OVERLAY_MAP.keys(),
      required=True,
      help='Android target for building inside container.')
  parser.add_argument(
      '--docker_bin',
      default='docker',
      help='Binary that invokes docker. Default to \'docker\'')
  parser.add_argument(
      '--meta_dir',
      default='',
      help='Full path to META folder. Default to \'\'')
  parser.add_argument(
      '--mount_local_device',
      action='store_true',
      help='If provided, the local connected Qualcomm USB device is mounted '
      'inside the container. WARNING: Using this flag will cause the adb server '
      'to be killed on the host machine.')
  args = parser.parse_args()

  if args.mount_local_device:
    # A device can only communicate with one adb server at a time, so the adb server is
    # killed on the host machine.
    for line in subprocess.check_output(['ps','-eo','cmd']).split('\n'):
      if re.match(r'adb.*fork-server.*', line):
        print('An adb server is running on your host machine. This server must be '
              'killed to use the --mount_local_device flag.')
        print('Continue? [y/N]: ', end='')
        if raw_input().lower() != 'y':
          exit()
        subprocess.check_call(['adb', 'kill-server'])
    local_device_path = get_local_device_path()
  else:
    local_device_path = None

  run(container_command=args.container_command,
      android_target=args.android_target,
      docker_bin=args.docker_bin,
      meta_dir=args.meta_dir,
      local_device_path=local_device_path)


if __name__ == '__main__':
  main()
