"""Builds q-keystone-qcom-dev cuttlestone_x86_phone on a Busytown build host.
"""

import build_busytown

build_goals = build_busytown.DEFAULT_BUILD_GOALS + ['tests']
build_busytown.build_target('cuttlestone_x86_phone', 'userdebug', build_goals)
