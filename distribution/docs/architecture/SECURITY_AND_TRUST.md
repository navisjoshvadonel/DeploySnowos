# SnowOS Security & Trust Architecture

SnowOS treats the user’s cognitive data and personal context as the most sensitive payload on the machine. This document outlines the explicit threat models, trust boundaries, and broker architectures that harden the OS against internal and external threats, including AI hallucination and unauthorized state mutation.

---

## 1. Threat Model & Security Model

**Primary Threats:**
1. **Malicious External Agents:** Exploiting network-facing services to access the user's semantic memory graph.
2. **AI Recursion/Hallucination:** `snowos-aicore` entering an infinite loop or incorrectly mutating system state based on false premises.
3. **Pre-Auth Data Leakage:** Side-channel attacks exposing user context before biometric/TPM authentication.
4. **Broker Bypass:** A rogue application directly modifying `snowos-broker` policies to grant itself AI integration.

**The SnowOS Security Model (Zero-Trust Cognition):**
- **Default Deny:** The AI cannot execute *any* command or read *any* file without explicitly passing through the `snowos-broker` policy engine.
- **Data at Rest:** All semantic embeddings and user memory graphs are LUKS-encrypted and TPM-sealed.
- **Ephemeral Context:** Pre-auth memory is held entirely in RAM and completely flushed upon shutdown or a failed auth threshold.

---

## 2. Trust Boundaries

Trust boundaries in SnowOS are rigidly defined to separate raw hardware from cognitive inference.

### Trust Domains:
- **Domain A (Hardware/Kernel):** Trusted. Contains UEFI, Kernel, and core Systemd init. Immutable.
- **Domain B (The Broker):** Trusted. The `snowos-broker` is a static, read-only binary that mediates all IPC. It holds the cryptographic keys post-auth.
- **Domain C (Cognitive Core):** Untrusted/Observed. `snowos-aicore` runs here. It is treated as a highly capable but potentially volatile entity. It cannot access the internet directly.
- **Domain D (User Space/Apps):** Untrusted. Standard applications (Flatpaks, browsers). They must request AI services via the Broker.

---

## 3. TPM 2.0 Integration & Pre-Auth Flow

**Objective:** Prevent identity leakage through side channels before the user is authenticated.

### Authentication State Machine:
1. **S0 (Boot):** OS loads. TPM 2.0 validates the boot chain (PCRs 0, 2, 4, 7, 8, 9).
2. **S1 (Pre-Auth / Greeter):** `snowos-greeter` launches. The AI runs in "Blind Mode." It can see the weather and hardware but cannot see the user's name or history. The primary LUKS key remains sealed in the TPM.
3. **S2 (Negotiation):** The user enters proximity. The IR camera securely identifies them.
4. **S3 (Unseal):** The Broker requests the TPM to unseal the LUKS key.
5. **S4 (Cognitive Handoff):** The user's semantic graph is mounted. `snowos-aicore` switches from Blind Mode to "Personalized Mode" instantly.

---

## 4. AI Broker Architecture & Permission Graph

The `snowos-broker` is the architectural heart of SnowOS security.

### 4.1 Immutable Broker Design
- The Broker is implemented in Rust. It does not use dynamic libraries for its core policy engine.
- Policies are stored in `/system/broker/policies.ro` (Read-Only). The AI cannot rewrite its own constraints.

### 4.2 The Permission Graph
When `snowos-aicore` wishes to take an action (e.g., "Dim the lights and open the IDE"), it submits an `Intent` to the Broker.

1. **Intent Parsing:** Broker reads the intent (`ACTION: MODIFY_UI`, `TARGET: SYSTEM_THEME`).
2. **Policy Evaluation:** Broker checks the Permission Graph. Does `aicore` have permission to modify `SYSTEM_THEME`? Yes.
3. **Ethical Constraints Check:** Broker evaluates if this action violates the "Human Final Authority" rule. (Theme changes are allowed; file deletions are not).
4. **Execution:** Broker forwards the approved command to `snowos-control`.

### 4.3 Sentinel Enforcement
`snowos-sentinel` watches the Broker. If the Broker crashes or hangs during an intent evaluation, Sentinel triggers a fail-safe that cuts off `aicore` IPC and reloads the Broker.
