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
    "add_library(rexui OBJECT ${REXUI_SOURCES})\n"
    "add_library(rex::ui ALIAS rexui)\n\n"
    "if(REX_PLATFORM_ANDROID)\n"
    "    target_compile_definitions(rexui PRIVATE VK_USE_PLATFORM_ANDROID_KHR=1)\n"
    "    target_link_libraries(rexui PUBLIC android)\n"
    "endif()",
    "add_library(rexui OBJECT ${REXUI_SOURCES})\n"
    "add_library(rex::ui ALIAS rexui)",
    "Android Vulkan and native-window dependencies",
)

# SDLActivity loads the SDL3 shared library before libmain.so. The SDK's
# desktop defaults are static-only, so Android must build the shared SDL3 target.
patch(
    "thirdparty/CMakeLists.txt",
    "if(ANDROID)\n"
    "    set(SDL_SHARED ON CACHE BOOL \"\" FORCE)\n"
    "    set(SDL_STATIC OFF CACHE BOOL \"\" FORCE)\n"
    "endif()\n\n"
    "set(SDL_TEST OFF CACHE BOOL \"\" FORCE)",
    "set(SDL_TEST OFF CACHE BOOL \"\" FORCE)",
    "SDL3 Android shared library",
)

# Do not turn on Linux desktop audio/video drivers when CMake's UNIX predicate
# also matches Android. SDL selects its native Android backends automatically.
patch(
    "thirdparty/CMakeLists.txt",
    "if(UNIX AND NOT APPLE AND NOT ANDROID)",
    "if(UNIX AND NOT APPLE)",
    "SDL Linux desktop drivers",
)

# NDK libc++ in the selected toolchain has no floating-point std::from_chars
# overload. ReXGlue already carries a C-locale fallback for macOS; enable that
# same fallback on non-Windows targets, including Android.
numeric_path = root / "include/rex/string/numeric.h"
numeric = numeric_path.read_text(encoding="utf-8")
if "REXGLUE_ANDROID_FLOAT_FROM_CHARS" not in numeric:
    if "#if REX_PLATFORM_MAC" not in numeric:
        raise SystemExit("Android patch: numeric.h float parser guard changed")
    numeric = numeric.replace("#if REX_PLATFORM_MAC", "#if !REX_PLATFORM_WIN32")
    old_float_guard = (
        "#if !REX_PLATFORM_WIN32\n"
        "template <typename T>\n"
        "inline std::from_chars_result portable_float_from_chars"
    )
    new_float_guard = (
        "#if !REX_PLATFORM_WIN32\n"
        "#define REXGLUE_ANDROID_FLOAT_FROM_CHARS 1\n"
        "template <typename T>\n"
        "inline std::from_chars_result portable_float_from_chars"
    )
    if old_float_guard not in numeric:
        raise SystemExit("Android patch: numeric.h portable float parser block changed")
    numeric = numeric.replace(old_float_guard, new_float_guard, 1)
    numeric_path.write_text(numeric, encoding="utf-8")

# Android's NDK libc++ has the same missing clock_cast customization as Apple libc++.
# The SDK already provides the fallback under __APPLE__; enable it for __ANDROID__ too.
chrono_path = root / "include/rex/chrono/chrono.h"
chrono = chrono_path.read_text(encoding="utf-8")
old_clock_guard = "#ifdef __APPLE__\n// Apple libc++ does not expose clock_time_conversion or clock_cast."
new_clock_guard = "#if defined(__APPLE__) || defined(__ANDROID__)\n// Apple and Android libc++ do not expose clock_time_conversion or clock_cast."
if new_clock_guard not in chrono:
    if old_clock_guard not in chrono:
        raise SystemExit("Android patch: chrono.h clock_cast fallback guard changed")
    chrono = chrono.replace(old_clock_guard, new_clock_guard, 1)
    chrono_path.write_text(chrono, encoding="utf-8")

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

# Android NDK r27 libc++ does not expose std::jthread/std::stop_token.
# Preserve timer queue behavior with std::thread and an atomic stop flag.
timer_path = root / "src/core/timer_queue.cpp"
timer = timer_path.read_text(encoding="utf-8")
if "REXGLUE_DRAGONLR_ANDROID_THREAD_COMPAT" not in timer:
    marker = "#include <forward_list>\n"
    if marker not in timer:
        raise SystemExit("Android patch: timer_queue.cpp forward_list include marker changed")
    timer = timer.replace(marker, marker + "#include <atomic>\n#include <thread>\n", 1)
    replacements = [
        ("std::jthread([this](std::stop_token stop_token) { TimerThreadMain(stop_token); })",
         "std::thread([this] { TimerThreadMain(); })"),
        ("dispatch_thread_.request_stop();",
         "stop_requested_.store(true, std::memory_order_release);"),
        ("// std::jthread auto-joins on destruction",
         "if (dispatch_thread_.joinable()) {\n      dispatch_thread_.join();\n    }"),
        ("void TimerThreadMain(std::stop_token stop_token)",
         "void TimerThreadMain()"),
        ("while (!stop_token.stop_requested())",
         "while (!stop_requested_.load(std::memory_order_acquire))"),
        ("std::jthread::id dispatch_thread_id()",
         "std::thread::id dispatch_thread_id()"),
        ("std::jthread dispatch_thread_;",
         "std::atomic<bool> stop_requested_{false};\n  std::thread dispatch_thread_;"),
    ]
    for old, new in replacements:
        if old not in timer:
            raise SystemExit("Android patch: timer_queue.cpp expected code not found: " + old)
        timer = timer.replace(old, new, 1)
    timer = timer.replace("namespace rex::thread {",
                          "// REXGLUE_DRAGONLR_ANDROID_THREAD_COMPAT\nnamespace rex::thread {", 1)
    timer_path.write_text(timer, encoding="utf-8")

# ReXGlue v0.10.0 references an integration header absent from the published SDK.
threading_path = root / "src/core/threading_posix.cpp"
threading = threading_path.read_text(encoding="utf-8")
missing_integration_include = "#include <rex/main_android.h>\n"
if "REXGLUE_DRAGONLR_ANDROID_NO_MAIN_HEADER" not in threading:
    if missing_integration_include not in threading:
        raise SystemExit("Android patch: threading_posix.cpp main_android include marker changed")
    threading = threading.replace(
        missing_integration_include,
        "// REXGLUE_DRAGONLR_ANDROID_NO_MAIN_HEADER: SDK has no rex/main_android.h\n",
        1,
    )
    threading_path.write_text(threading, encoding="utf-8")

# Expose the runtime Android API level used by Android memory/thread backends.
platform_header = root / "include/rex/platform.h"
platform_h = platform_header.read_text(encoding="utf-8")
if "REXGLUE_DRAGONLR_ANDROID_API_LEVEL" not in platform_h:
    platform_h += """

#if REX_PLATFORM_ANDROID
#include <android/api-level.h>
namespace rex {
// Runtime device API level; ASharedMemory is available from API 26.
inline int GetAndroidApiLevel() { return android_get_device_api_level(); }
}  // namespace rex
#define REXGLUE_DRAGONLR_ANDROID_API_LEVEL 1
#endif
"""
    platform_header.write_text(platform_h, encoding="utf-8")

# Bionic does not implement getcontext/makecontext/swapcontext. ReXGlue fibers
# are used by the guest kernel scheduler, so preserve them with a cooperative
# AArch64 context switch that saves the AAPCS64 callee-saved register set.
fiber_header = root / "include/rex/thread/fiber.h"
fiber_h = fiber_header.read_text(encoding="utf-8")
if "REXGLUE_DRAGONLR_ANDROID_FIBER_CONTEXT" not in fiber_h:
    old_includes = """#if REX_PLATFORM_LINUX || REX_PLATFORM_MAC
#if REX_PLATFORM_MAC && !defined(_XOPEN_SOURCE)
// Darwin hides the deprecated ucontext APIs unless _XOPEN_SOURCE is defined
// before including <ucontext.h>.
#define _XOPEN_SOURCE 700
#endif
#include <ucontext.h>
#include <cstdint>
#include <vector>
#endif"""
    new_includes = """#if (REX_PLATFORM_LINUX && !REX_PLATFORM_ANDROID) || REX_PLATFORM_MAC
#if REX_PLATFORM_MAC && !defined(_XOPEN_SOURCE)
// Darwin hides the deprecated ucontext APIs unless _XOPEN_SOURCE is defined
// before including <ucontext.h>.
#define _XOPEN_SOURCE 700
#endif
#include <ucontext.h>
#endif

#if REX_PLATFORM_LINUX || REX_PLATFORM_MAC || REX_PLATFORM_ANDROID
#include <cstdint>
#include <vector>
#endif

#if REX_PLATFORM_ANDROID
// REXGLUE_DRAGONLR_ANDROID_FIBER_CONTEXT
// Layout is shared with rex_android_fiber_swap() in fiber_android.cpp.
struct alignas(16) AndroidFiberContext {
  std::uint64_t x19_x30[12];
  uint64_t sp;
  uint64_t d8_d15[8];
};
#endif"""
    if old_includes not in fiber_h:
        raise SystemExit("Android patch: fiber.h include block changed")
    fiber_h = fiber_h.replace(old_includes, new_includes, 1)
    old_fields = """#elif REX_PLATFORM_LINUX || REX_PLATFORM_MAC
  ucontext_t context_{};
  std::vector<uint8_t> stack_;
  void (*entry_)(void*) = nullptr;
  void* arg_ = nullptr;
  bool is_thread_fiber_ = false;

  static void Trampoline();
#endif"""
    new_fields = """#elif (REX_PLATFORM_LINUX && !REX_PLATFORM_ANDROID) || REX_PLATFORM_MAC
  ucontext_t context_{};
  std::vector<uint8_t> stack_;
  void (*entry_)(void*) = nullptr;
  void* arg_ = nullptr;
  bool is_thread_fiber_ = false;

  static void Trampoline();
#elif REX_PLATFORM_ANDROID
  AndroidFiberContext context_{};
  std::vector<uint8_t> stack_;
  void (*entry_)(void*) = nullptr;
  void* arg_ = nullptr;
  bool is_thread_fiber_ = false;

  static void Trampoline();
#endif"""
    if old_fields not in fiber_h:
        raise SystemExit("Android patch: fiber.h private backend block changed")
    fiber_h = fiber_h.replace(old_fields, new_fields, 1)
    fiber_header.write_text(fiber_h, encoding="utf-8")

core_cmake_path = root / "src/core/CMakeLists.txt"
core_cmake = core_cmake_path.read_text(encoding="utf-8")
if "REXGLUE_DRAGONLR_ANDROID_FIBER_SOURCE" not in core_cmake:
    if "        fiber_posix.cpp\n" not in core_cmake:
        raise SystemExit("Android patch: core CMake fiber_posix source marker changed")
    core_cmake = core_cmake.replace(
        "        fiber_posix.cpp\n",
        "        $<$<NOT:$<BOOL:${ANDROID}>>:fiber_posix.cpp> # REXGLUE_DRAGONLR_ANDROID_FIBER_SOURCE\n",
        1,
    )
    platform_end = """        threading_posix.cpp
    )
endif()

# Xenos data-format layer"""
    platform_new = """        threading_posix.cpp
    )
endif()

if(ANDROID)
    target_sources(rexcore PRIVATE fiber_android.cpp)
endif()

# Xenos data-format layer"""
    if platform_end not in core_cmake:
        raise SystemExit("Android patch: core CMake platform source block changed")
    core_cmake = core_cmake.replace(platform_end, platform_new, 1)
    core_cmake_path.write_text(core_cmake, encoding="utf-8")

fiber_android_source = root / "src/core/fiber_android.cpp"
if not fiber_android_source.exists():
    fiber_android_source.write_text(r'''/**
 * @file        rex/core/fiber_android.cpp
 * @brief       AArch64 Android cooperative fiber backend.
 *
 * Bionic does not provide the deprecated ucontext switching functions.
 * This backend switches contexts using the AAPCS64 callee-saved registers.
 */
#include <rex/platform.h>
#if REX_PLATFORM_ANDROID

#include <rex/thread/fiber.h>

#include <cassert>
#include <cstddef>
#include <cstdint>
#include <pthread.h>

namespace rex::thread {

static_assert(offsetof(AndroidFiberContext, sp) == 96);
static_assert(offsetof(AndroidFiberContext, d8_d15) == 104);
static_assert(sizeof(AndroidFiberContext) == 176);

extern "C" __attribute__((naked)) void rex_android_fiber_swap(
    AndroidFiberContext*, const AndroidFiberContext*) {
  __asm__ volatile(
      "stp x19, x20, [x0, #0]\n"
      "stp x21, x22, [x0, #16]\n"
      "stp x23, x24, [x0, #32]\n"
      "stp x25, x26, [x0, #48]\n"
      "stp x27, x28, [x0, #64]\n"
      "stp x29, x30, [x0, #80]\n"
      "mov x9, sp\n"
      "str x9, [x0, #96]\n"
      "stp d8, d9, [x0, #104]\n"
      "stp d10, d11, [x0, #120]\n"
      "stp d12, d13, [x0, #136]\n"
      "stp d14, d15, [x0, #152]\n"
      "ldp x19, x20, [x1, #0]\n"
      "ldp x21, x22, [x1, #16]\n"
      "ldp x23, x24, [x1, #32]\n"
      "ldp x25, x26, [x1, #48]\n"
      "ldp x27, x28, [x1, #64]\n"
      "ldp x29, x30, [x1, #80]\n"
      "ldr x9, [x1, #96]\n"
      "mov sp, x9\n"
      "ldp d8, d9, [x1, #104]\n"
      "ldp d10, d11, [x1, #120]\n"
      "ldp d12, d13, [x1, #136]\n"
      "ldp d14, d15, [x1, #152]\n"
      "ret\n");
}

thread_local Fiber* Fiber::tls_current_ = nullptr;

Fiber* Fiber::ConvertCurrentThread() {
  auto* fiber = new Fiber();
  fiber->is_thread_fiber_ = true;
  tls_current_ = fiber;
  return fiber;
}

Fiber* Fiber::Create(size_t stack_size, void (*entry)(void*), void* arg) {
  if (!entry || stack_size < 16 * 1024) {
    return nullptr;
  }

  auto* fiber = new Fiber();
  fiber->entry_ = entry;
  fiber->arg_ = arg;
  fiber->stack_.resize(stack_size);

  const uintptr_t stack_top =
      reinterpret_cast<uintptr_t>(fiber->stack_.data() + fiber->stack_.size()) &
      ~static_cast<uintptr_t>(0xF);
  fiber->context_.sp = stack_top;
  fiber->context_.x19_x30[11] =
      reinterpret_cast<uintptr_t>(&Fiber::Trampoline);
  return fiber;
}

void Fiber::Trampoline() {
  Fiber* fiber = tls_current_;
  assert(fiber && fiber->entry_);
  fiber->entry_(fiber->arg_);
  // Match the POSIX backend: a fiber without a successor terminates its host thread.
  pthread_exit(nullptr);
}

void Fiber::SwitchTo(Fiber* target) {
  assert(target && target != tls_current_);
  Fiber* from = tls_current_;
  assert(from && "ConvertCurrentThread must precede SwitchTo");
  tls_current_ = target;
  rex_android_fiber_swap(&from->context_, &target->context_);
}

void Fiber::Destroy() {
  if (is_thread_fiber_) {
    assert(this == tls_current_);
    tls_current_ = nullptr;
  } else {
    assert(this != tls_current_ && "Destroy called on the currently running fiber");
  }
  delete this;
}

}  // namespace rex::thread

#endif  // REX_PLATFORM_ANDROID
''', encoding="utf-8")

print(f"Applied Android CMake/window/timer/fiber compatibility patches to {root}")

