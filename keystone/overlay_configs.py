"""Defines overlay configuration for keystone builds.

Keep the overlay configuration information in a separate file for easier
tracking.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

OVERLAY_MAP = {
    'sdm845': ['qcom-LA.UM.8.3.r1-incoming', 'keystone'],
    'sdm845_gms': ['qcom-LA.UM.8.3.r1-incoming', 'keystone', 'gms'],
    'sdm660_64': ['qcom-LA.UM.7.2-incoming'],
    'cuttlestone_x86_phone': ['cuttlestone'],
    'msmnile': ['qcom-LA.UM.8.1.r1-incoming', 'keystone'],
    'msm8937_32go': [],
    # NOTE: for the aosp_* targets, the cuttlestone overlay contains more than
    # is needed, but it isn't harmful and allows sharing of some required build
    # infrastructure.
    'aosp_arm64': ['cuttlestone'],
    'aosp_x86_64': ['cuttlestone'],
}

# This subset of LA.UM.8.3 was experimentally determined to be the minimum
# subset of QC projects necessary to build AOSP-defined (or derived) targets,
# such as aosp_x86_64 or Cuttlestone. When combined with the 'cuttlestone'
# overlay, it provides the necessary build infrastructure and project set to
# enable building these targets.
_AOSP_COMPATIBLE_FS_VIEW = [
    # Provides QC vendor extension HALs
    ("overlays/qcom-LA.UM.8.3.r1-incoming/vendor/qcom/opensource/interfaces",
     "vendor/qcom/opensource/interfaces"),
    ("overlays/qcom-LA.UM.8.3.r1-incoming/vendor/qcom/proprietary/interfaces",
     "vendor/qcom/proprietary/interfaces"),
    ("overlays/qcom-LA.UM.8.3.r1-incoming/vendor/qcom/proprietary/commonsys-intf/telephony",
     "vendor/qcom/proprietary/commonsys-intf/telephony"),
    # Provides libril-protobuf-c-nano-enable_malloc, needed by telephony
    # interfaces
    ("overlays/qcom-LA.UM.8.3.r1-incoming/vendor/qcom/proprietary/qcril-hal/nanopb",
     "vendor/qcom/proprietary/qcril-hal/nanopb"),
    # Provides telephony-ext, ims-ext-common, and
    #     qtiNetworkLib, used by a variety of telephony services
    ("overlays/qcom-LA.UM.8.3.r1-incoming/vendor/codeaurora/commonsys/telephony",
     "vendor/codeaurora/commonsys/telephony"),
    ("overlays/qcom-LA.UM.8.3.r1-incoming/vendor/qcom/proprietary/commonsys/telephony-apps",
     "vendor/qcom/proprietary/commonsys/telephony-apps"),
    # Provides display headers used by SurfaceFlinger
    ("overlays/qcom-LA.UM.8.3.r1-incoming/vendor/qcom/opensource/commonsys-intf/display",
     "vendor/qcom/opensource/commonsys-intf/display"),
    # Provides the tcmiface java library
    ("overlays/qcom-LA.UM.8.3.r1-incoming/vendor/qcom/opensource/commonsys/dpm",
     "vendor/qcom/opensource/commonsys/dpm"),
    # Provides system Bluetooth components
    ("overlays/qcom-LA.UM.8.3.r1-incoming/hardware/qcom/bt", "hardware/qcom/bt"),
    ("overlays/qcom-LA.UM.8.3.r1-incoming/vendor/qcom/opensource/commonsys/bluetooth",
     "vendor/qcom/opensource/commonsys/bluetooth"),
    ("overlays/qcom-LA.UM.8.3.r1-incoming/vendor/qcom/opensource/commonsys/bluetooth_ext",
     "vendor/qcom/opensource/commonsys/bluetooth_ext"),
    ("overlays/qcom-LA.UM.8.3.r1-incoming/vendor/qcom/opensource/commonsys/system/bt",
     "vendor/qcom/opensource/commonsys/system/bt"),
    # Provides build scripts
    ("overlays/qcom-LA.UM.8.3.r1-incoming/device/qcom/common/vendor_hal_makefile_generator.sh",
     "device/qcom/common/vendor_hal_makefile_generator.sh"),
    ("overlays/qcom-LA.UM.8.3.r1-incoming/device/qcom/common/stop_scan.mk",
     "vendor/qcom/proprietary/commonsys/Android.mk"),
]

# A map (optionally) specifying a filesystem view mapping for each target.
# The value for each target is a set of (to, from) tuples, representing paths
# (relative to the Android build root) to map into the specified locations.
FS_VIEW_MAP = {
    'cuttlestone_x86_phone': _AOSP_COMPATIBLE_FS_VIEW,
    'aosp_arm64': _AOSP_COMPATIBLE_FS_VIEW,
    'aosp_x86_64': _AOSP_COMPATIBLE_FS_VIEW,
}
