"""Mounts all the projects required by a selected Android target.

For details on how vendor overlays work see the vendor overlays
section of the README.md.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import subprocess
import tempfile
import overlay_configs


class Mount(object):
  """Manages a filesystem mount.
  """

  def __init__(self, mount_command, unmount_command):
    self.mount_command = None
    self.unmount_command = None
    subprocess.check_call(mount_command)
    self.mount_command = mount_command
    self.unmount_command = unmount_command

  def __del__(self):
    if self.unmount_command:
      subprocess.check_call(self.unmount_command)


class Overlay(object):
  """Manages filesystem overlays of Android source tree.
  """

  def _MountOverlay(self, source_dir, overlay_dirs, target, overlaid_dir):
    """Mounts the selected overlay directory.

    OverlayFS creates a merge directory composed of a union
    of source_dir and the overlay_dirs. Then source_dir is replaced
    by the resulting merge directory.

    OverlayFS also needs two new directories: upperdir and workdir.

    upperdir stores any files written to the merge directory.
    This is located in overlays/artifacts.

    workdir is a temporary working cache required by OverlayFS.
    This is located in overlays/work.

    Args:
      source_dir: A string with the path to the Android platform source.
      overlay_dirs: A list of strings with the paths to the overlay
        directory to apply.
      target: A string with the name of the target to be prepared.
      overlaid_dir: A string with the path to the source with the overlays
        applied to it.
    """
    lowerdirs = overlay_dirs
    lowerdirs.append(source_dir)

    overlay_out_dir = os.path.join(source_dir, 'out', 'overlays')
    target_out_dir = os.path.join(overlay_out_dir, target)
    workdir = os.path.join(target_out_dir, 'work')
    upperdir = os.path.join(target_out_dir, 'artifacts')

    if not os.path.isdir(overlay_out_dir):
      os.mkdir(overlay_out_dir)
    if not os.path.isdir(target_out_dir):
      os.mkdir(target_out_dir)
    if not os.path.isdir(workdir):
      os.mkdir(workdir)
    if not os.path.isdir(upperdir):
      os.mkdir(upperdir)

    mount_options = 'lowerdir=%s,' % ':'.join(lowerdirs)
    mount_options += 'upperdir=%s,' % upperdir
    mount_options += 'workdir=%s' % workdir

    mount_command = [
        'sudo', 'mount',
        '--types', 'overlay',
        '--options', mount_options,
        'overlay',
        overlaid_dir
    ]
    unmount_command = ['sudo', 'umount', overlaid_dir]
    self._AddMount(mount_command, unmount_command)

  def _BindMount(self, source_dir, dest_dir):
    """Creates a bind mount for the specified directories.

    Args:
      source_dir: A string with the path of a source directory to bind. It must
        exist.
      dest_dir: A string with the path of a destination directory to bind the
        source into. If it does not exist, it will be created.
    """
    if not os.path.exists(dest_dir):
      os.makedirs(dest_dir)
    self._AddMount(['sudo', 'mount', '--bind', source_dir, dest_dir],
                   ['sudo', 'umount', dest_dir])

  def _CopyFileMount(self, source_path, dest_path):
    """Copies a file to the specified destination.

    It simulates the other mount mechanisms, in that it will be removed during
    the unmount phase.

    Args:
      source_path: A string with the path of a source file to copy. It must
        exist.
      dest_path: A string with the path to copy the file to. It should not
        exist.
    """
    dest_dir = os.path.dirname(dest_path)
    if not os.path.exists(dest_dir):
      os.makedirs(dest_dir)
    self._AddMount(['cp', source_path, dest_path], ['rm', '-f', dest_path])

  def _AddMount(self, mount_command, unmount_command):
    mount = Mount(
        mount_command=mount_command,
        unmount_command=unmount_command)
    self._mounts.append(mount)

  def GetMountInfo(self):
    """Gets details on the filesystem devices mounted.

    Returns:
      A list of dicts. Each dict entry represents a device mounted
      with the following fields:
        mount_command: A list of strings with the command that was
          used for mounting.
        unmount_command: A list of strings with the command that will
          be used for unmounting.
    """
    mount_info = [{'mount_command': mount.mount_command,
                   'unmount_command': mount.unmount_command}
                  for mount in self._mounts]
    return mount_info

  def __init__(self, target, source_dir, overlaid_dir=None):
    """Inits Overlay with the details of what is going to be overlaid.

    Args:
      target: A string with the name of the target to be prepared.
      source_dir: A string with the path to the Android platform source.
      overlaid_dir: A string with the path to the source with the overlays
        applied to it. If none is provided, the overlays shall be applied
        directly to provided source_dir.
    """

    if not overlaid_dir:
      overlaid_dir = source_dir

    self._overlay_dirs = None
    self._mounts = []

    # Bind-mounts on top of the source directory need to happen after the
    # overlay has been applied. OverlayFS does not carry forward bind submounts
    # from the origin lower layers. Any bind submounts must be performed after
    # OverlayFS is mounted.
    post_overlay_bind_mounts = []

    # Save a reference to the workspace out directory.
    out_dir = os.path.join(source_dir, 'out')
    overlaid_out_dir = os.path.join(overlaid_dir, 'out')
    if not os.path.exists(out_dir):
      os.makedirs(out_dir)
    original_out_dir = tempfile.mkdtemp(prefix='outtmp_')
    self._BindMount(out_dir, original_out_dir)
    post_overlay_bind_mounts.append((original_out_dir, overlaid_out_dir))

    overlay_dirs = []
    for overlay_dir in overlay_configs.OVERLAY_MAP[target]:
      overlay_dir = os.path.join(source_dir, 'overlays', overlay_dir)
      overlay_dirs.append(overlay_dir)

    # The dynamic_overlay_dir is a directory that shall be created and populated
    # now, as opposed to the overlays dirs in the 'overlays/' directory which 
    # are provided statically with the source directory. We use the 
    # dynamic_overlay_dir for adding elements which are created dynamically,
    # like copied files and the overlay/ path whiteout.
    dynamic_overlay_dir = tempfile.mkdtemp(prefix='ovtmp_')
    overlay_dirs.append(dynamic_overlay_dir)

    # Create an empty overlays file to white out overlays dir.
    # Otherwise the build system will try to detect all
    # the Android.bp and Android.mk modules under the overlays
    # dir and conflict with the ovelays applied at the top.
    overlay_whiteout = os.path.join(dynamic_overlay_dir, 'overlays')
    open(overlay_whiteout, 'a').close()

    # If specified for this target, create a custom filesystem view
    if target in overlay_configs.FS_VIEW_MAP:
      for path_relative_from, path_relative_to in overlay_configs.FS_VIEW_MAP[
          target]:
        path_from = os.path.join(source_dir, path_relative_from)
        if os.path.isfile(path_from):
          path_to = os.path.join(dynamic_overlay_dir, path_relative_to)
          self._CopyFileMount(path_from, path_to)
        elif os.path.isdir(path_from):
          # Here we create intermediate bind mounts because the 'overlays/'
          # directory will ultimately be hidden in the final OverlayFS target,
          # making any dir under 'overlays/' unreachable.
          path_to = os.path.join(overlaid_dir, path_relative_to)
          bind_intermediate_dir = tempfile.mkdtemp(prefix='bindtmp_')
          self._BindMount(path_from, bind_intermediate_dir)
          post_overlay_bind_mounts.append((bind_intermediate_dir, path_to))
        else:
          raise ValueError("Path '%s' must be a file or directory" % path_from)

    self._MountOverlay(source_dir, overlay_dirs, target, overlaid_dir)
    self._overlay_dirs = overlay_dirs
    print('Applied overlays ' + ' '.join(self._overlay_dirs))

    # Now that we've applied an overlay any files written
    # under the repo workspace root directory will be redirected
    # to out/overlays/artifacts. This is is fine for any misbehaving
    # modules attempting to write to the source during a build.
    # However, any modules attempting to write directly to out
    # during a build should be allowed to do so.
    #
    # Lucky for us we saved a reference to the original out file system
    # node (the first entry in the post_overlay_bind_mounts list). Now all we
    # have to do is bind the saved reference back to out and that will take
    # precedence over the overlay filesystem.

    for path_from, path_to in post_overlay_bind_mounts:
      self._BindMount(path_from, path_to)

  def __del__(self):
    """Cleans up Overlay.
    """
    if self._overlay_dirs:
      print('Stripped out overlay ' + ' '.join(self._overlay_dirs))
