"""Builds msm8917 on an Busytown build host.
"""

import build_busytown

build_goals = build_busytown.DEFAULT_BUILD_GOALS + [
    'tests', '-k'
]

build_busytown.build_target('msm8937_32go', 'userdebug', build_goals)
