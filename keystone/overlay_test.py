"""Test overlay."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import shutil
import subprocess
import tempfile
import unittest
import overlay
import overlay_configs
import re


# Extend the overlay config with unit test entries
overlay_configs.OVERLAY_MAP['unittest'] = ['unittest1', 'unittest2']
overlay_configs.FS_VIEW_MAP['unittest'] = [
    ('overlays/unittest1/from_dir', 'to_dir'),
    ('overlays/unittest1/from_file', 'to_file'),
]


class MountTest(unittest.TestCase):

  def testCreate(self):
    mount = overlay.Mount(
        mount_command=['/bin/true'],
        unmount_command=['/bin/true'])
    self.assertEqual(
        mount.mount_command,
        ['/bin/true']
    )

  def testFailedMount(self):
    with self.assertRaises(subprocess.CalledProcessError):
      overlay.Mount(
          mount_command=['/bin/false'],
          unmount_command=['/bin/true']
      )

  def testDelete(self):
    tempdir = tempfile.mkdtemp()
    try:
      unmount_file = os.path.join(tempdir, 'unmounted')
      overlay.Mount(
          mount_command=['/bin/true'],
          unmount_command=['/bin/touch', unmount_file])

      self.assertTrue(os.path.exists(unmount_file))
    finally:
      shutil.rmtree(tempdir)


class OverlayTest(unittest.TestCase):

  class FakeMount(object):

    def __init__(self, mount_command, unmount_command):
      self.mount_command = mount_command
      self.unmount_command = unmount_command

  def setUp(self):
    overlay.Mount = self.FakeMount
    self.source_dir = tempfile.mkdtemp()
    self.overlaid_dir = tempfile.mkdtemp()
    os.mkdir(os.path.join(self.source_dir, 'overlays'))
    os.mkdir(os.path.join(self.source_dir,
                          'overlays', 'unittest1'))
    os.mkdir(os.path.join(self.source_dir,
                          'overlays', 'unittest1', 'from_dir'))
    open(os.path.join(self.source_dir,
                      'overlays', 'unittest1', 'from_file'), 'a').close()
    os.mkdir(os.path.join(self.source_dir,
                          'overlays', 'unittest2'))

  def tearDown(self):
    shutil.rmtree(self.source_dir)

  def testValidTargetOverlayMount(self):
    o = overlay.Overlay(
        target='unittest',
        source_dir=self.source_dir)
    self.assertIsNotNone(o)
    mounts = o.GetMountInfo()
    mount_commands = [' '.join(mount['mount_command']) for mount in mounts]
    unmount_commands = [' '.join(mount['unmount_command']) for mount in mounts]
    self.assertTrue(
        any([
            re.match(
                'sudo mount --types overlay --options '
                'lowerdir=%s/overlays/unittest1:%s/overlays/unittest2:.*/ovtmp_.*:%s,'
                'upperdir=%s/out/overlays/unittest/artifacts,'
                'workdir=%s/out/overlays/unittest/work '
                'overlay %s' %
                (self.source_dir, self.source_dir, self.source_dir,
                 self.source_dir, self.source_dir, self.source_dir), command)
            for command in mount_commands
        ]))
    self.assertIn('sudo umount %s' % os.path.join(self.source_dir),
                  unmount_commands)
    self.assertIn('sudo umount %s' % os.path.join(self.source_dir, 'out'),
                  unmount_commands)

  def testOverlaidDirectory(self):
    o = overlay.Overlay(
        target='unittest',
        source_dir=self.source_dir,
        overlaid_dir=self.overlaid_dir)
    self.assertIsNotNone(o)
    mounts = o.GetMountInfo()
    mount_commands = [' '.join(mount['mount_command']) for mount in mounts]
    unmount_commands = [' '.join(mount['unmount_command']) for mount in mounts]
    self.assertTrue(
        any([
            re.match(
                'sudo mount --types overlay --options '
                'lowerdir=%s/overlays/unittest1:%s/overlays/unittest2:.*/ovtmp_.*:%s,'
                'upperdir=%s/out/overlays/unittest/artifacts,'
                'workdir=%s/out/overlays/unittest/work '
                'overlay %s' %
                (self.source_dir, self.source_dir, self.source_dir,
                 self.source_dir, self.source_dir, self.overlaid_dir), command)
            for command in mount_commands
        ]))
    self.assertIn('sudo umount %s' % os.path.join(self.overlaid_dir),
                  unmount_commands)
    self.assertIn('sudo umount %s' % os.path.join(self.overlaid_dir, 'out'),
                  unmount_commands)

  def testValidTargetFilesystemViewDirectory(self):
    o = overlay.Overlay(
        target='unittest',
        source_dir=self.source_dir)
    self.assertIsNotNone(o)
    mounts = o.GetMountInfo()
    mount_commands = [' '.join(mount['mount_command']) for mount in mounts]
    unmount_commands = [' '.join(mount['unmount_command']) for mount in mounts]
    self.assertTrue(
        any([
            re.match(
                'sudo mount --bind '
                '%s/overlays/unittest1/from_dir .*/bindtmp_' %
                self.source_dir, command) for command in mount_commands
        ]))
    self.assertTrue(
        any([
            re.match(
                'sudo mount --bind '
                '.*/bindtmp_.* %s/to_dir' % self.source_dir, command)
            for command in mount_commands
        ]))
    self.assertIn('sudo umount %s' % os.path.join(self.source_dir, 'to_dir'),
                  unmount_commands)

  def testValidTargetFilesystemViewFile(self):
    o = overlay.Overlay(
        target='unittest',
        source_dir=self.source_dir)
    self.assertIsNotNone(o)
    mounts = o.GetMountInfo()
    mount_commands = [' '.join(mount['mount_command']) for mount in mounts]
    unmount_commands = [' '.join(mount['unmount_command']) for mount in mounts]
    self.assertTrue(
        any([
            re.match(
                'cp %s/overlays/unittest1/from_file .*/ovtmp_.*/to_file' %
                self.source_dir, command) for command in mount_commands
        ]))
    self.assertTrue(
        any([
            re.match('rm -f .*/ovtmp_.*/to_file', command)
            for command in unmount_commands
        ]))

  def testInvalidTarget(self):
    with self.assertRaises(KeyError):
      overlay.Overlay(
          target='unknown',
          source_dir=self.source_dir)


if __name__ == '__main__':
  unittest.main()
