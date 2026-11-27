# DragonLR Android platform integration.
# The Android NDK toolchain is supplied by Gradle or the CI workflow.

if(NOT ANDROID)
    message(FATAL_ERROR "platform/android requires the Android NDK CMake toolchain")
endif()
if(NOT ANDROID_ABI STREQUAL "arm64-v8a")
    message(FATAL_ERROR "DragonLR Android currently targets arm64-v8a only (got: ${ANDROID_ABI})")
endif()

target_include_directories(dbz3 PRIVATE "${CMAKE_CURRENT_LIST_DIR}")
target_compile_definitions(dbz3 PRIVATE
    DBZ3_PLATFORM_HEADER=\"android_platform.h\"
    VK_USE_PLATFORM_ANDROID_KHR=1
)
target_link_libraries(dbz3 PRIVATE android log)

# SDLActivity loads libmain.so. Keep the CMake target name stable for the
# existing SDK/plugin wiring while using the Android loader's expected name.
set_target_properties(dbz3 PROPERTIES OUTPUT_NAME main)
