#pragma once

// Platform hook included by src/main.cpp. SDL3 owns the Android activity,
// input/event loop and native window; Vulkan presentation is provided by
// ReXGlue's AndroidNativeWindowSurface.
#define DBZ3_PLATFORM_PRE_SETUP(config) ((void)(config))
#define DBZ3_PLATFORM_APP_MEMBERS
#define DBZ3_PLATFORM_SHUTDOWN() ((void)0)
