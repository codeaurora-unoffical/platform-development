"""Builds msm8917 on an Busytown build host.
"""

import build_busytown

# TODO(b/119317944): Remove SKIP_ABI_CHECKS
build_goals = [
    'TEMPORARY_DISABLE_PATH_RESTRICTIONS=true', 'SKIP_ABI_CHECKS=true', '-k'
]

build_busytown.build_target('msm8937_32go', 'userdebug', build_goals)
