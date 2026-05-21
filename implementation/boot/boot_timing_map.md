# SnowOS Boot Timing Map

**Hardware Target:** Modern NVMe SSD, UEFI Fast Boot Enabled
**Total Budget:** 5000ms (5.0s)

| Phase | Component | Start Time (ms) | End Time (ms) | Budget | Output / Constraint |
|---|---|---|---|---|---|
| **0. Firmware** | UEFI + GRUB | 0 | 400 | 400ms | Totally silent. No text. |
| **1. Kernel** | vmlinuz + initramfs | 400 | 1200 | 800ms | Early KMS loads GPU driver. |
| **2. Splash Init** | `snowos-splash` | 1200 | 1400 | 200ms | Vulkan pipeline compiles. |
| **3. Core Init** | `sysinit.target` | 1200 | 2500 | 1300ms | (Runs in parallel with Splash) |
| **4. Broker Start** | `snowos-broker` | 2500 | 2700 | 200ms | Starts after basic sockets. |
| **5. Compositor** | `FrostWM` | 2700 | 3500 | 800ms | Acquires DRM lease from splash. |
| **6. Greeter UI** | `snowos-greeter` | 3500 | 3800 | 300ms | Must launch <300ms after WM ready. |
| **7. Handoff Fade** | Cross-fade shader | 3800 | 4500 | 700ms | Max black screen budget: <700ms. |
| **8. Stable State** | Auth screen ready | 4500 | 5000 | 500ms | Input stack enabled. |

### Post-Boot (Asynchronous)
- `4500ms+`: `snowos-aicore` begins loading ML models into VRAM.
- `5000ms+`: Telemetry daemon flushes boot timings to disk.
