#pragma once

#include <SDL3/SDL_filesystem.h>
#include <SDL3/SDL_stdinc.h>

#include <stdlib.h>

// SDL3 owns the Android activity, input/event loop and native window;
// Vulkan presentation is provided by ReXGlue's AndroidNativeWindowSurface.
// SDL_GetPrefPath maps to Android's private internal-storage directory.
#define DBZ3_PLATFORM_PRE_SETUP(config)                                      \
    do {                                                                     \
        (void)(config);                                                      \
        char* dragonlr_data_path = SDL_GetPrefPath("DragonLR", "DragonLR");  \
        if (dragonlr_data_path) {                                            \
            setenv("XDG_DATA_HOME", dragonlr_data_path, 1);                  \
            setenv("XDG_CACHE_HOME", dragonlr_data_path, 1);                 \
            setenv("HOME", dragonlr_data_path, 1);                           \
            setenv("TMPDIR", dragonlr_data_path, 1);                         \
            SDL_free(dragonlr_data_path);                                    \
        }                                                                    \
    } while (0)

#define DBZ3_PLATFORM_APP_MEMBERS
#define DBZ3_PLATFORM_SHUTDOWN() ((void)0)
