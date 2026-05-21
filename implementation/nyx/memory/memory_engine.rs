// implementation/nyx/memory/memory_engine.rs

use crate::memory::context_graph::ContextGraph;

pub struct MemoryEngine {
    // Manages relevance scoring and memory compression to prevent bloat.
}

impl MemoryEngine {
    pub fn new() -> Self {
        MemoryEngine {}
    }

    /// Evaluates the entire semantic graph and adjusts relevance scores.
    /// Recent contexts decay slowly, repeated workflows strengthen.
    pub fn apply_temporal_decay(&self, graph: &mut ContextGraph, current_time: i64) {
        for (_, context) in graph.nodes.iter_mut() {
            let age = current_time - context.temporal_metadata.last_accessed;
            
            // Example decay logic: lose 0.01 relevance per hour
            let decay_factor = (age as f32 / 3600.0) * 0.01;
            context.temporal_metadata.relevance_score -= decay_factor;
            
            if context.temporal_metadata.relevance_score < 0.0 {
                context.temporal_metadata.relevance_score = 0.0;
            }
        }
    }
}
