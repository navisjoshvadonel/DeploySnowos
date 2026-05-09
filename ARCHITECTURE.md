# SnowOS Architectural Roadmap

SnowOS is evolving into a branded Ubuntu platform composed of a hardened core and a unique visual system.

## Long-Term Structure

### 1. `/kernel_layer`

- performance tuning
- telemetry-informed optimization
- no custom kernel identity claims unless enforcement is real

### 2. `/system_services`

- platform daemons
- local policy enforcement
- runtime brokers
- reliability and rollback helpers

### 3. `/ai_core`

- Nyx runtime
- orchestration
- local memory and state
- authenticated control surfaces

### 4. `/ui_engine`

- SnowOS shell identity
- motion system
- dock and layout behavior
- theme and icon pipeline

### 5. `/app_layer`

- SnowControl
- branded tools
- future sandboxed apps

## Product Split

- `core`: runtime, policies, service hardening, validation
- `visual`: desktop identity, dock, icons, themes, motion
- `all`: complete SnowOS experience
