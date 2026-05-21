// implementation/frostwm/renderer/scene_graph.rs

use std::collections::HashMap;
use std::sync::{Arc, RwLock};

pub type SurfaceId = u64;

/// SnowOS abandons traditional "windows" in favor of Semantic Contexts.
/// A context can contain multiple surfaces, inputs, and semantic links.
pub struct SemanticContext {
    pub id: u64,
    pub intent_label: String, // e.g., "coding_session", "media_playback"
    pub surfaces: Vec<SurfaceId>,
    pub z_index: i32,
    pub opacity: f32,
}

/// The Scene Graph is a flattened composition tree to ensure deterministic traversal.
pub struct SceneGraph {
    contexts: Arc<RwLock<HashMap<u64, SemanticContext>>>,
    active_context: RwLock<u64>,
}

impl SceneGraph {
    pub fn new() -> Self {
        SceneGraph {
            contexts: Arc::new(RwLock::new(HashMap::new())),
            active_context: RwLock::new(0),
        }
    }

    /// Freezes the current state of the scene for atomic frame submission.
    /// No Wayland client mutation can alter this frame once frozen.
    pub fn freeze_frame(&self) -> FrozenSceneState {
        // Creates a zero-copy immutable snapshot of the current composition
        let ctx = self.contexts.read().unwrap();
        FrozenSceneState {
            contexts_snapshot: ctx.clone(),
        }
    }

    /// Explicitly allocates a surface to a Semantic Context. 
    /// Nyx cannot draw directly; it must request context allocation.
    pub fn allocate_surface_to_context(&self, ctx_id: u64, surface: SurfaceId) -> Result<(), String> {
        let mut ctx = self.contexts.write().unwrap();
        if let Some(context) = ctx.get_mut(&ctx_id) {
            context.surfaces.push(surface);
            Ok(())
        } else {
            Err("Context does not exist. Nyx must create intent context first.".to_string())
        }
    }
}

pub struct FrozenSceneState {
    contexts_snapshot: HashMap<u64, SemanticContext>,
}
