// implementation/nyx/cognitive_surface/attention_engine.rs

pub struct AttentionEngine {
    // Determines interruption priority and suppresses low-value events
}

impl AttentionEngine {
    pub fn new() -> Self {
        AttentionEngine {}
    }

    /// Evaluates if an incoming system event is worth breaking the user's current focus.
    pub fn should_interrupt(&self, event_severity: u32, active_intent_focus_level: u32) -> bool {
        // High focus level (e.g., coding) suppresses anything below CRITICAL severity
        if active_intent_focus_level > 80 && event_severity < 90 {
            println!("[AttentionEngine] Suppressing non-critical event to protect focus.");
            return false;
        }
        true
    }
}
