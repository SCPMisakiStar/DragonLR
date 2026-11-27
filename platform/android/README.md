# Android platform

This is the Android-specific host integration for DragonLR.

- Initial ABI: `arm64-v8a`
- Initial minimum API: 29 (Android 10)
- Graphics: ReXGlue Xenos Vulkan backend
- Window/activity/input/audio: SDL3 Android backend
- Native presentation surface: `ANativeWindow` exposed by SDL3

The ReXGlue v0.10 source is checked out by CI and patched at build time by
`tools/patch_rexglue_android.py`. The SDK itself is not vendored in this
repository.

The Gradle project lives in `android/`. It expects the Android SDK package
to have been installed into `rexglue-android/` and the SDL3 Android Java
sources to be present under the checked-out SDK.

This is an in-progress port. A successful SDK build is not yet proof that the
game library or APK builds or starts. Storage Access Framework integration,
touch controls, Android lifecycle validation, and device Vulkan capability
testing remain separate tasks.
