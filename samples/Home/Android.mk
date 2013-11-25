# Do not compile 'Home' for MPQ
ifneq ($(call is-board-platform,msm8960),true)


LOCAL_PATH:= $(call my-dir)
include $(CLEAR_VARS)

LOCAL_MODULE_TAGS := samples

LOCAL_SRC_FILES := $(call all-subdir-java-files)

LOCAL_PACKAGE_NAME := Home

LOCAL_SDK_VERSION := current

include $(BUILD_PACKAGE)



# Conditional check for MPQ ends
endif
