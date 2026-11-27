#pragma once

#include <android/native_window.h>

#include <rex/ui/surface.h>

namespace rex::ui {

// Non-owning wrapper around the ANativeWindow supplied by SDL3. The SDL
// window owns the native window; the presenter must be destroyed before it.
class AndroidNativeWindowSurface final : public Surface {
 public:
  explicit AndroidNativeWindowSurface(ANativeWindow* window) : window_(window) {}

  TypeIndex GetType() const override { return kTypeIndex_AndroidNativeWindow; }
  ANativeWindow* window() const { return window_; }

 protected:
  bool GetSizeImpl(uint32_t& width_out, uint32_t& height_out) const override;

 private:
  ANativeWindow* window_ = nullptr;
};

}  // namespace rex::ui
