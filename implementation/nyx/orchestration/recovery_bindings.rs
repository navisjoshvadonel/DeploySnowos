// implementation/nyx/orchestration/recovery_bindings.rs

use crate::memory::persistence::PersistenceLayer;

pub struct RecoveryBindings {
    persistence: PersistenceLayer,
}

impl RecoveryBindings {
    pub fn new(persistence: PersistenceLayer) -> Self {
        RecoveryBindings { persistence }
    }

    /// Callback triggered by FrostWM's Brainstem during a 3-strike escalation.
    pub fn handle_safe_mode_escalation(&self) {
        println!("[RecoveryBindings] FrostWM escalating to Safe Mode. Flushing memory graph.");
        // We do NOT try to keep drawing. We immediately serialize our semantic context.
        // FrostWM handles the physical recovery.
        let _ = self.persistence.flush_to_disk(&crate::memory::context_graph::ContextGraph::new());
    }
}
