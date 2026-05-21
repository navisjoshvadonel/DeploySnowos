# SnowOS Architecture

SnowOS is organized as a branded Ubuntu platform with a distinct runtime and visual layer.

## 1. Kernel Layer (`/kernel_layer`)

Uses Ubuntu's Linux base and focuses on measured optimization work, not custom kernel replacement claims.

## 2. System Services Layer (`/system_services`)

Contains SnowOS platform daemons such as:

- boot orchestration
- Permission Broker (`broker.sock`)
- AI Sentinel (upgraded with **Sentinel-Nyx healing loop**)
- reliability tooling
- module and plugin infrastructure

## 3. AI Core Layer (`/ai_core`)

Contains Nyx and related SnowOS intelligence services, local state, and interface backends.

### Cognitive Subsystems (Next-Gen)

| Subsystem | Location | Purpose |
|---|---|---|
| **NyxVFS** | `ai/nyxvfs/` | Neural Virtual Filesystem — semantic file search, contextual symlinks |
| **Healing Bridge** | `ai/nyxvfs/healing_bridge.py` | Sentinel-Nyx self-healing loop, BTRFS snapshot recovery |
| **Intent Governor** | `ai/performance/intent_governor.py` | Behavioral prediction, vmtouch pre-caching, CPU governor |
| **Context Engine** | `ai/context_engine.py` | Real xdotool window detection, battery/memory telemetry, VLM capture |

## 4. UI Engine Layer (`/ui_engine`)

Contains SnowOS desktop presentation logic:

- shell extensions, motion behavior, dock behavior, theming assets
- **Frostbite** (`ui_engine/frostbite/`) — native AI companion chatbot sidebar

## 5. Application Layer (`/app_layer`)

Contains SnowControl and other user-facing applications.

## Runtime Contract

SnowOS services communicate through a shared runtime directory:

- runtime directory: `/run/snowos`
- boot status: `/run/snowos/boot-status.json`
- feature flags: `/run/snowos/feature-flags.json`
- broker socket: `/run/snowos/broker.sock`
- sentinel socket: `/run/snowos/sentinel.sock`
- **nyxvfs socket**: `/run/snowos/nyxvfs.sock`
- **healing bridge socket**: `/run/snowos/nyx_heal.sock`

This keeps the platform contract explicit and avoids raw world-writable socket paths in `/tmp`.

## Boot Contract

SnowOS now has a first-class boot stage before the rest of the platform comes online:

- `snowos-boot.service` prepares runtime directories
- `TrustBoot` validates the SnowOS integrity manifest
- snapshot tooling captures a recoverable baseline
- the active boot profile resolves enabled AI features
- SnowControl reads boot status and feature flags from runtime files

## Cognitive OS Commands (Nyx CLI)

| Command | Description |
|---|---|
| `nyx find <query>` | Semantic filesystem search — zero-keyword conceptual file discovery |
| `nyx vfs stats` | NyxVFS index statistics |
| `nyx vfs context <path>` | Contextual symlinks for a project directory |
| `nyx vfs index` | Trigger background re-index of watched directories |
| `nyx governor status` | Intent governor state — power profile, predicted apps |
| `nyx governor run` | Trigger immediate governor evaluation |
