# SnowOS Cognitive Architecture

This document defines the core cognitive boundaries, epistemic models, and creative augmentation engines that power SnowOS. By designing explicit boundaries and structured fallback states, we convert traditional AI limitations into resilient, engineered safety mechanisms.

---

## 1. The Epistemic Layer: Offline First & Reality Anchoring

**Objective:** Preserve privacy while allowing controlled awareness of external reality without assuming constant internet connectivity.

### 1.1 Architecture & Trust Boundaries
SnowOS operates an **Offline-First Epistemic Model**. The AI core (`snowos-aicore`) assumes it is air-gapped by default. Network access is heavily mediated through a zero-trust external interface.

**Trust Boundaries:**
- **Tier 0 (Local Absolute):** Hardware state, verified system logs, immutable filesystem state.
- **Tier 1 (Local Inference):** Context engine deductions, user-generated embeddings.
- **Tier 2 (Cached External):** Synchronized metadata (weather, time, calendar) signed cryptographically.
- **Tier 3 (Speculative/WAN):** Live internet search, external LLM API fallbacks.

### 1.2 Reality Confidence Index (RCI)
To prevent hallucination, the system tags every memory and inference with an RCI score (0.0 to 1.0):
- `RCI 1.0`: Verified local reality (e.g., "The laptop lid is closed.")
- `RCI 0.8`: Recent synchronized reality (e.g., "Weather was sunny 1 hour ago.")
- `RCI 0.2`: Speculative external context (e.g., "The user might be driving based on time.")

*The AI explicitly surfaces its RCI to the user when uncertain, phrasing responses as "Based on my last sync at 08:00..."*

### 1.3 Synchronization Model & Daemons
- **`snowos-epistemic-sync.service`**: A secure WAN synchronization daemon that negotiates minimal metadata extraction over an encrypted channel.
- **Cache Invalidation:** Knowledge ages based on its source. Tier 2 data decays linearly; after 24 hours, its RCI drops to 0, forcing a re-fetch or triggering the "Emergency Offline Reasoning Mode."
- **Cryptographic Provenance:** External data is signed by the broker before entering the local semantic graph, ensuring no forged state can deceive the AI.

---

## 2. Pre-Auth Identity Blindness

**Objective:** Enable intelligent pre-login behavior (greeting, ambient awareness) while cryptographically shielding personal context.

### 2.1 The Zero Knowledge Identity Layer
Prior to decryption, the `snowos-aicore` operates in a **Pre-Auth Cognitive State**.

**What the AI knows:**
- Hardware state (battery, temperature).
- Boot health & Sentinel metrics.
- Environmental conditions (time, ambient light).
- Anonymous behavioral heuristics (e.g., "User usually logs in around 09:00").

**What the AI CANNOT know:**
- Private files, journal entries, conversations.
- Personalized memory embeddings.

### 2.2 TPM-Sealed User Memory
The user's cognitive memory graph is sealed via TPM 2.0. The `snowos-broker` intercepts early boot context and holds the AI in "Greeter Mode." 

**Biometric Negotiation System:**
As the user approaches, the webcam/IR sensors feed anonymous presence vectors to the AI. The conversational unlock architecture allows the system to say, "Good morning, the system is ready," but it cannot reference the user's name or pending tasks until the TPM unseals the key.

---

## 3. Self-Reference & Safety (Introspection Model)

**Objective:** Prevent recursive AI self-destruction, deadlock, or infinite self-analysis loops.

### 3.1 Cognitive Stack Depth Protections
When `snowos-aicore` analyzes its own logs or system states (via `snowos-sentinel`), it operates under a strict **Introspection Depth Limit**.
- **Recursion Algorithm:** `Max Depth = 3`. If the AI queries its own reasoning trace to explain a previous reasoning trace, the broker terminates the chain at depth 3 and forces a "Summary State."

### 3.2 The Immutable Safety Kernel
- The AI is explicitly forbidden from modifying `snowos-broker` policies or bypassing `snowos-sentinel`.
- **Layered Permission Broker:** A static, compiled Rust binary (`snowos-broker`) evaluates all AI IPC requests against a read-only policy tree.
- **Watchdog Rollback Model:** If self-modification attempts escalate or cognitive latency spikes beyond 2000ms, the watchdog kills the `aicore` process, restores the last stable memory snapshot, and restarts the daemon gracefully (invisible to the user).

---

## 4. Human Creative Gap (Augmentation Engine)

**Objective:** Create a framework where the AI assists and orchestrates without replacing human agency.

### 4.1 Ambient Focus Orchestration
The **Creative Augmentation Engine** measures user momentum rather than just parsing commands.
- **Cognitive Workload Estimation:** The system tracks window switching velocity, typing speed, and active context. High context-switching indicates "distraction."
- **Distraction Reduction Engine:** The AI subtly dims background windows, suppresses non-critical notifications, and adjusts color temperature based on the estimated cognitive load.

### 4.2 Ethical Boundaries for Cognitive Influence
- **Non-Authoritarian Rule:** The AI may *suggest* a workspace layout ("You seem to be coding; shall I arrange your IDE and terminal?"), but it will *never* move a window or delete a file autonomously.
- **Human Final Authority:** All destructive or highly mutative actions require physical confirmation (e.g., clicking a glassmorphic prompt).

---

## 5. Future Cognitive OS Evolution (Roadmap)

### 5.1 Beyond Static Computing
SnowOS is architected to evolve into a fully **Autonomous Platform**:
- **Distributed Cognition:** Future iterations will allow local devices (laptop, phone, workstation) to share a unified cryptographic memory graph over a local mesh network, creating a continuous ambient intelligence.
- **Context-Aware Scheduling:** Moving beyond standard Linux CFS, the scheduler will prioritize threads based on semantic context (e.g., giving maximum priority to a video rendering job because the AI knows the user is waiting for it, while throttling background updates).
- **Spatial / Conversational Interfaces:** Transitioning from rigid windows to dynamic, AI-generated viewports that expand and collapse based on conversational intent, acting as true extensions of the user's mind.
