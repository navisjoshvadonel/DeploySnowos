// implementation/nyx/cognitive_surface/human_override.rs

pub struct HumanOverrideLayer {
    is_frozen: bool,
}

impl HumanOverrideLayer {
    pub fn new() -> Self {
        HumanOverrideLayer {
            is_frozen: false,
        }
    }

    /// Triggered by a strict hardware interrupt or uninterceptable FrostWM global keybind.
    /// This is the "kill switch" for anticipation.
    pub fn engage_manual_override(&mut self) {
        println!("[HumanOverride] MANUAL OVERRIDE ENGAGED. Freezing all predictions.");
        self.is_frozen = true;
        
        // 1. Halt WorkspaceSynthesizer immediately
        // 2. Revoke active Agent sandboxes if requested
        // 3. Drop all adaptive surface resizing
    }

    pub fn is_autonomous_allowed(&self) -> bool {
        !self.is_frozen
    }
}
