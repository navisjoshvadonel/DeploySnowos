# SnowOS Architectural Roadmap

This directory structure maps the future evolution of SnowOS from a prototype into a production-ready, AI-native operating system. The codebase is being transitioned into five distinct layers to enforce Zero Trust security, modularity, and high performance.

## The 5-Layer Architecture

### 1. `/kernel_layer`
- **Purpose:** Low-level hardware abstraction, CPU/RAM scheduling, and initial boot sequences.
- **Future Contents:** eBPF plugins, CFS AI modifiers, fast-boot initializers.
- **Current Prototype Mapping:** Parts of `/core` and `/performance`.

### 2. `/system_services`
- **Purpose:** IPC buses, file systems, network stack, and background daemons.
- **Future Contents:** The Module Manager, Permission Broker, and standard OS services.
- **Current Prototype Mapping:** `/system`, `/network`, and parts of `/plugins`.

### 3. `/ai_core`
- **Purpose:** The centralized intelligence hub for SnowOS.
- **Future Contents:** Nyx Autonomous Kernel, Context Engine, Predictive Optimizer, and Semantic Memory (ChromaDB).
- **Current Prototype Mapping:** The `/nyx` directory, `/ai`, and `/memory`.

### 4. `/ui_engine`
- **Purpose:** The standalone, GPU-accelerated visual environment.
- **Future Contents:** SnowCompositor, Theme & Animation Engine, and Dynamic Layout Manager.
- **Current Prototype Mapping:** `/ui`, `/snowos-visuals`, `/snowos-login`, and `/ui_intelligence`.

### 5. `/app_layer`
- **Purpose:** User-facing, sandboxed container applications.
- **Future Contents:** SnowControl (Central Control Panel), default apps, and third-party containers.
- **Current Prototype Mapping:** Existing GUI tools like `snow_dashboard.py`.

---

## Migration Strategy
To avoid breaking the current SnowOS prototype, we will incrementally migrate existing modules into this new layered structure. Future development will strictly adhere to defining explicit API contracts between these layers.
