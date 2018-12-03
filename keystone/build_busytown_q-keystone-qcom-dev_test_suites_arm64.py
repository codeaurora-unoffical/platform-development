"""Builds q-keystone-qcom-dev test_suites_arm64 on a Busytown build host.

"""

import build_busytown

build_goals = [
    'TARGET_PRODUCT=aosp_arm64',
    'WITH_DEXPREOPT_BOOT_IMG_AND_SYSTEM_SERVER_ONLY=true', 'cts', 'dist',
    'cts_instant', 'tradefed-all', 'vts', 'general-tests', 'gamecore-all'
]
build_busytown.build_target('aosp_arm64', 'userdebug', build_goals)
