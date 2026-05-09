# SnowOS Architecture

SnowOS is organized as a branded Ubuntu platform with a distinct runtime and visual layer.

## 1. Kernel Layer (`/kernel_layer`)

Uses Ubuntu's Linux base and focuses on measured optimization work, not custom kernel replacement claims.

## 2. System Services Layer (`/system_services`)

Contains SnowOS platform daemons such as:

- boot orchestration
- Permission Broker
- AI Sentinel
- reliability tooling
- module and plugin infrastructure

## 3. AI Core Layer (`/ai_core`)

Contains Nyx and related SnowOS intelligence services, local state, and interface backends.

## 4. UI Engine Layer (`/ui_engine`)

Contains SnowOS desktop presentation logic:

- shell extensions
- motion behavior
- dock behavior
- theming assets

## 5. Application Layer (`/app_layer`)

Contains SnowControl and other user-facing applications.

## Runtime Contract

SnowOS services communicate through a shared runtime directory:

- runtime directory: `/run/snowos`
- boot status: `/run/snowos/boot-status.json`
- feature flags: `/run/snowos/feature-flags.json`
- broker socket: `/run/snowos/broker.sock`
- sentinel socket: `/run/snowos/sentinel.sock`

This keeps the platform contract explicit and avoids raw world-writable socket paths in `/tmp`.

## Boot Contract

SnowOS now has a first-class boot stage before the rest of the platform comes online:

- `snowos-boot.service` prepares runtime directories
- `TrustBoot` validates the SnowOS integrity manifest
- snapshot tooling captures a recoverable baseline
- the active boot profile resolves enabled AI features
- SnowControl reads boot status and feature flags from runtime files
