#pragma once

// ReXGlue v0.10.0 provides these Android-specific initialization hooks in
// its POSIX memory and threading backends. The SDK's Android host header is
// not part of the published tag, so declare the hooks at the platform edge.
namespace rex::memory {
void AndroidInitialize();
}
namespace rex::thread {
void AndroidInitialize();
}

// SDL3 owns the Android activity, input/event loop and native window;
// Vulkan presentation is provided by ReXGlue's AndroidNativeWindowSurface.
#define DBZ3_PLATFORM_PRE_SETUP(config)                                      \
    do {                                                                     \
        (void)(config);                                                      \
        rex::memory::AndroidInitialize();                                    \
        rex::thread::AndroidInitialize();                                    \
    } while (0)

#define DBZ3_PLATFORM_APP_MEMBERS

// Keep Android's dynamically resolved API handles alive until process exit.
// OnShutdown runs before ReXGlue's runtime and worker threads are destroyed.
#define DBZ3_PLATFORM_SHUTDOWN() ((void)0)
