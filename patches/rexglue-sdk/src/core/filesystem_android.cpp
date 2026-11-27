/**
 * Android content URI filesystem hooks.
 *
 * The ReXGlue SDK declares these hooks, but v0.10.0 does not ship the Java/JNI
 * ContentResolver bridge that supplies file descriptors. Keep the native SDK
 * linkable until the Android host registers that bridge.
 */
#include <rex/filesystem.h>

namespace rex::filesystem {

void AndroidInitialize() {}
void AndroidShutdown() {}

bool IsAndroidContentUri(const std::string_view source) {
  return source.starts_with("content://");
}

int OpenAndroidContentFileDescriptor(const std::string_view /*uri*/,
                                     const char* /*mode*/) {
  // SAF access requires a file descriptor supplied by the Android host's
  // ContentResolver. Returning -1 is intentional until that bridge is wired.
  return -1;
}

}  // namespace rex::filesystem
