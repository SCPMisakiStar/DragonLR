#!/usr/bin/env python3
"""Apply the DragonLR Android compatibility layer to a checked-out ReXGlue v0.10 SDK.

The SDK itself is fetched as a pinned upstream submodule in CI. This script is
intentionally idempotent and fails closed if upstream source markers drift.
"""
from pathlib import Path
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else "rexglue-sdk-0.10").resolve()

def patch(rel, marker, replacement, label):
    path = root / rel
    if not path.is_file():
        raise SystemExit(f"Android patch: missing SDK file: {path}")
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return
    if replacement not in text:
        raise SystemExit(f"Android patch: expected marker not found in {rel}: {label}")
    path.write_text(text.replace(replacement, marker, 1), encoding="utf-8")

# The upstream platform header already identifies __ANDROID__ and declares
# REX_PLATFORM_ANDROID. Add Android to CMake's platform triplet selection.
patch(
    "CMakeLists.txt",
    "elseif(ANDROID)\n"
    "    if(NOT ANDROID_ABI STREQUAL \"arm64-v8a\")\n"
    "        message(FATAL_ERROR \"DragonLR Android currently supports arm64-v8a only (got: ${ANDROID_ABI})\")\n"
    "    endif()\n"
    "    set(REX_PLATFORM \"android-arm64\")\n"
    "    set(REX_PLATFORM_ANDROID ON)\n"
    "    add_compile_definitions(REX_PLATFORM_ANDROID=1)\n"
    "elseif(UNIX AND NOT APPLE)",
    "elseif(UNIX AND NOT APPLE)",
    "SDK platform detection",
)

# Android has no X11 or Wayland libraries. The SDL Android video backend
# supplies an ANativeWindow, which the Vulkan presenter already understands.
patch(
    "src/ui/CMakeLists.txt",
    "elseif(REX_PLATFORM_ANDROID)\n"
    "    set(REXUI_PLATFORM_SOURCES surface_android.cpp)\n"
    "elseif(APPLE)",
    "elseif(APPLE)",
    "UI platform source selection",
)
patch(
    "src/ui/CMakeLists.txt",
    "if(UNIX AND NOT APPLE AND NOT ANDROID)",
    "if(UNIX AND NOT APPLE)",
    "UI Linux-only X11/Wayland dependencies",
)
# Enable VK_KHR_android_surface declarations in the UI/Vulkan translation units.
patch(
    "src/ui/CMakeLists.txt",
    "add_library(rexui OBJECT ${REXUI_SOURCES})\\n"
    "add_library(rex::ui ALIAS rexui)\\n\\n"
    "if(REX_PLATFORM_ANDROID)\\n"
    "    target_compile_definitions(rexui PRIVATE VK_USE_PLATFORM_ANDROID_KHR=1)\\n"
    "    target_link_libraries(rexui PUBLIC android)\\n"
    "endif()",
    "add_library(rexui OBJECT ${REXUI_SOURCES})\\n"
    "add_library(rex::ui ALIAS rexui)",
    "Android Vulkan and native-window dependencies",
)

# Do not turn on Linux desktop audio/video drivers when CMake's UNIX predicate
# also matches Android. SDL selects its native Android backends automatically.
patch(
    "thirdparty/CMakeLists.txt",
    "if(UNIX AND NOT APPLE AND NOT ANDROID)",
    "if(UNIX AND NOT APPLE)",
    "SDL Linux desktop drivers",
)

# WindowSDL must create the Android surface from SDL's ANativeWindow property.
window_path = root / "src/ui/window_sdl.cpp"
window = window_path.read_text(encoding="utf-8")
if "REXGLUE_DRAGONLR_ANDROID_SURFACE" not in window:
    include_old = """#if REX_PLATFORM_WIN32
#include <rex/ui/surface_win.h>
#elif REX_PLATFORM_MAC
#include <CoreFoundation/CoreFoundation.h>
#include <SDL3/SDL_metal.h>

#include <rex/ui/surface_mac.h>
#else
#include <X11/Xlib-xcb.h>
#include <rex/ui/surface_gnulinux.h>
#endif"""
    include_new = """#if REX_PLATFORM_WIN32
#include <rex/ui/surface_win.h>
#elif REX_PLATFORM_MAC
#include <CoreFoundation/CoreFoundation.h>
#include <SDL3/SDL_metal.h>

#include <rex/ui/surface_mac.h>
#elif REX_PLATFORM_ANDROID
#include <rex/ui/surface_android.h>
#else
#include <X11/Xlib-xcb.h>
#include <rex/ui/surface_gnulinux.h>
#endif"""
    if include_old not in window:
        raise SystemExit("Android patch: window_sdl.cpp platform include block changed")
    window = window.replace(include_old, include_new, 1)

    old_handle = """#if REX_PLATFORM_WIN32
  if (!sdl_window_) {
    return nullptr;
  }
  return SDL_GetPointerProperty(SDL_GetWindowProperties(sdl_window_),
                                SDL_PROP_WINDOW_WIN32_HWND_POINTER, nullptr);
#else
  return nullptr;
#endif"""
    new_handle = """#if REX_PLATFORM_WIN32
  if (!sdl_window_) {
    return nullptr;
  }
  return SDL_GetPointerProperty(SDL_GetWindowProperties(sdl_window_),
                                SDL_PROP_WINDOW_WIN32_HWND_POINTER, nullptr);
#elif REX_PLATFORM_ANDROID
  if (!sdl_window_) {
    return nullptr;
  }
  return SDL_GetPointerProperty(SDL_GetWindowProperties(sdl_window_),
                                SDL_PROP_WINDOW_ANDROID_WINDOW_POINTER, nullptr);
#else
  return nullptr;
#endif"""
    if old_handle not in window:
        raise SystemExit("Android patch: GetNativeWindowHandle block changed")
    window = window.replace(old_handle, new_handle, 1)

    old_surface = """#elif REX_PLATFORM_MAC
  if (allowed_types & Surface::kTypeFlag_CAMetalLayer) {
    SDL_MetalView metal_view = SDL_Metal_CreateView(sdl_window_);
    if (metal_view) {
      void* layer = SDL_Metal_GetLayer(metal_view);
      if (layer) {
        return std::make_unique<CAMetalLayerSurface>(sdl_window_, metal_view, layer);
      }
      SDL_Metal_DestroyView(metal_view);
    }
  }
#else
  SDL_PropertiesID props = SDL_GetWindowProperties(sdl_window_);"""
    new_surface = """#elif REX_PLATFORM_MAC
  if (allowed_types & Surface::kTypeFlag_CAMetalLayer) {
    SDL_MetalView metal_view = SDL_Metal_CreateView(sdl_window_);
    if (metal_view) {
      void* layer = SDL_Metal_GetLayer(metal_view);
      if (layer) {
        return std::make_unique<CAMetalLayerSurface>(sdl_window_, metal_view, layer);
      }
      SDL_Metal_DestroyView(metal_view);
    }
  }
#elif REX_PLATFORM_ANDROID
  if (allowed_types & Surface::kTypeFlag_AndroidNativeWindow) {
    SDL_PropertiesID props = SDL_GetWindowProperties(sdl_window_);
    auto* native_window = static_cast<ANativeWindow*>(
        SDL_GetPointerProperty(props, SDL_PROP_WINDOW_ANDROID_WINDOW_POINTER, nullptr));
    if (native_window) {
      return std::make_unique<AndroidNativeWindowSurface>(native_window);
    }
  }
#else
  SDL_PropertiesID props = SDL_GetWindowProperties(sdl_window_);"""
    if old_surface not in window:
        raise SystemExit("Android patch: CreateSurfaceImpl block changed")
    window = window.replace(old_surface, new_surface, 1)
    window = window.replace(
        "namespace rex::ui {",
        "// REXGLUE_DRAGONLR_ANDROID_SURFACE\nnamespace rex::ui {",
        1,
    )
    window_path.write_text(window, encoding="utf-8")

print(f"Applied Android CMake/window compatibility patches to {root}")
