// implementation/nyx/cognitive_surface/adaptive_surface.rs

pub struct AdaptiveSurface {
    pub surface_id: u64,
    pub primary_intent: String,
    pub is_expanded: bool,
}

impl AdaptiveSurface {
    pub fn new(id: u64, intent: &str) -> Self {
        AdaptiveSurface {
            surface_id: id,
            primary_intent: intent.to_string(),
            is_expanded: false,
        }
    }

    /// Reshapes the surface based on the active cognitive task.
    /// Example: A coding context expands the editor and collapses the terminal unless active.
    pub fn reshape_for_context(&mut self, active_intent: &str) {
        if self.primary_intent == active_intent {
            self.expand();
        } else {
            self.collapse_to_dock();
        }
    }

    fn expand(&mut self) {
        self.is_expanded = true;
        // Request spatial allocation from FrostWM
    }

    fn collapse_to_dock(&mut self) {
        self.is_expanded = false;
        // Request minimal footprint from FrostWM
    }
}
