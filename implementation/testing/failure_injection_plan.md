# SnowOS Failure Injection Testing Plan

To ensure SnowOS behaves like aerospace infrastructure, it must be systematically subjected to the following failure vectors during the CI/CD pipeline using QEMU.

## 1. Hardware & Driver Failures
- **Test 1A (GPU Crash):** Inject a simulated kernel panic into the `amdgpu` or `i915` driver 2 seconds after boot.
  - *Expected Result:* `snowos-sentinel` detects the hang, drops to `kiosk-shell` Safe Mode via LLVMpipe within 3 seconds.
- **Test 1B (TPM Unavailable):** Boot the OS with the virtual TPM module explicitly detached.
  - *Expected Result:* System boots to greeter in "Blind Mode." User cannot decrypt the `/user` partition. Safe failure without boot loop.

## 2. Software & Orchestration Failures
- **Test 2A (Compositor Deadlock):** Send `SIGSTOP` to the `frostwm` process right after DRM handoff.
  - *Expected Result:* Watchdog ping fails after 3000ms. Service is killed with `SIGKILL` and restarted seamlessly.
- **Test 2B (AI Daemon Crash):** Inject a segmentation fault into `snowos-aicore` during an active workspace arrangement.
  - *Expected Result:* `snowos-broker` rejects dangling IPC requests. Sentinel restarts `aicore`. Desktop environment remains completely stable and usable.

## 3. Storage & Update Failures
- **Test 3A (Corrupted Update):** Manually delete a critical `.so` file in the `@system_pending` BTRFS snapshot and reboot.
  - *Expected Result:* FrostWM fails to load 3 times. Sentinel triggers Safe Mode. System automatically reverts GRUB to `@system_current`.

## Execution Environment
All tests will be executed headlessly via QEMU, monitoring the `boot_telemetry_schema` output through serial console to verify exact millisecond recovery times.
