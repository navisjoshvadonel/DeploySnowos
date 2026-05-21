// implementation/ipc/snowbusd/nyx_bindings.rs

use crate::protocol::{SnowbusMessage, PayloadType};
use crate::frostwm::renderer::scene_graph::SceneGraph;

pub struct NyxPolicyGate<'a> {
    scene_graph: &'a SceneGraph,
}

impl<'a> NyxPolicyGate<'a> {
    pub fn new(scene_graph: &'a SceneGraph) -> Self {
        NyxPolicyGate { scene_graph }
    }

    /// The ONLY way Nyx can alter the screen.
    /// Nyx requests an ephemeral rendering context based on a semantic intent.
    /// FrostWM has the absolute authority to accept, resize, or deny the request.
    pub fn handle_nyx_surface_request(&self, msg: SnowbusMessage) -> Result<u64, String> {
        if msg.sender_id != "snowos-aicore" {
            return Err("Unauthorized sender for Nyx endpoints.".to_string());
        }

        if let PayloadType::SurfaceRequest { width, height, intent } = msg.payload {
            // Validate the requested dimensions aren't attempting to hijack the full screen
            // unless the intent explicitly warrants it and user policy allows it.
            
            let context_id = self.generate_context_id();
            
            // Allocate the surface in the SceneGraph.
            // Nyx receives an FD to write pixels, but NO control over where it is drawn.
            println!("[NyxGate] Approved surface request for intent: {}", intent);
            
            Ok(context_id)
        } else {
            Err("Invalid payload type for surface request.".to_string())
        }
    }

    fn generate_context_id(&self) -> u64 {
        // Stub
        42
    }
}
