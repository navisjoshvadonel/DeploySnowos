# SnowOS Runtime & Services Strategy

The SnowOS Runtime consists of a suite of specialized, daemonized services that orchestrate the operating system, separate from the traditional Linux init system, though managed by systemd.

## Core Daemons

### 1. `snowos-broker.service`
- **Role:** The central IPC message bus and permission mediator.
- **Function:** Applications and shell components do not talk to the AI directly. They send requests to the broker. The broker checks permissions (e.g., "Can this app read the screen?") and routes the request to `snowos-aicore`.

### 2. `snowos-aicore.service`
- **Role:** The brain of the operating system.
- **Function:** Loads local LLMs or connects to secure cloud APIs. It manages the contextual memory engine, processing user commands, summarizing text, and deciding on autonomous actions.

### 3. `snowos-control.service`
- **Role:** The system settings and hardware manager backend.
- **Function:** Exposes a unified API for the UI to change network settings, display resolution, audio devices, and power profiles, abstracting away the underlying Linux utilities (NetworkManager, PipeWire).

### 4. `snowos-sentinel.service`
- **Role:** The watchdog and self-healing engine.
- **Function:** Continuously monitors the health of the Frost Shell and other core daemons. If the compositor crashes, the Sentinel instantly restarts it. If the AI core hangs, it reloads the model. It also triggers fail-safe recovery modes.

### 5. `snowos-optimizer.service`
- **Role:** The autonomous performance tuner.
- **Function:** Uses AI to predict application usage and dynamically adjusts CPU governors, re-allocates RAM, and manages swap space (zram) to ensure the active window always feels perfectly smooth.

### 6. `snowos-updater.service`
- **Role:** Background update manager.
- **Function:** Silently fetches updates for the Ubuntu base, SnowOS components, and AI models. It prepares the BTRFS snapshots and stages the updates for the next reboot, ensuring a seamless OTA experience.

## Service Hardening
- All SnowOS services run with the principle of least privilege.
- AI memory is encrypted at rest.
- IPC is secured via strict socket permissions.
