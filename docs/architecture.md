# SnowOS Architecture

SnowOS is built on a strict 5-Layer structure to ensure modularity, security, and performance.

## 1. Kernel Layer (`/kernel_layer`)
Interfaces directly with Linux. Contains the **Predictive Optimizer** which utilizes real-time telemetry to predict user intent and dynamically adjust process priorities (`renice`) and cache allocations.

## 2. System Services Layer (`/system_services`)
The heart of the Zero Trust model.
- **Permission Broker:** The central nervous system. Mediates all access requests.
- **AI Sentinel:** The immune system. Monitors behavioral streams for anomalies.
- **Reliability Manager:** The safety net. Handles atomic state snapshots and rollbacks to protect against unrecoverable crashes.

## 3. AI Core Layer (`/ai_core`)
The intelligence engine. It contains a persistent memory store (SQLite) and a continuous feedback loop that evaluates the outcomes of its own decisions, increasing or decreasing confidence scores over time.

## 4. UI Engine Layer (`/ui_engine`)
Contains **SnowCompositor**, a secure Wayland-based display engine that prevents unauthorized input/output access (like keyloggers) by explicitly verifying with the Permission Broker before drawing pixels.

## 5. Application Layer (`/app_layer`)
Where user space apps live, including **SnowControl**, the central intelligence dashboard that provides a window into the AI's real-time decision-making process.

## Communication (IPC)
No module can directly call another. All cross-layer communication happens securely via UNIX domain sockets located in `/tmp/snowos_sockets/`.
