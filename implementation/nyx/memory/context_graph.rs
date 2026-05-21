// implementation/nyx/memory/context_graph.rs

use std::collections::HashMap;

pub type ContextId = u64;

/// Represents a persistent cognitive state replacing a "desktop session".
pub struct SemanticContext {
    pub id: ContextId,
    pub active_intent: String,
    pub related_files: Vec<String>,
    pub active_processes: Vec<u32>,
    pub surface_allocations: Vec<u64>, // FrostWM Surface IDs
    pub agent_ownership: Option<String>,
    pub temporal_metadata: TemporalMetadata,
    pub security_scope: String,
}

pub struct TemporalMetadata {
    pub created_at: i64,
    pub last_accessed: i64,
    pub relevance_score: f32,
}

pub struct ContextGraph {
    pub nodes: HashMap<ContextId, SemanticContext>,
}

impl ContextGraph {
    pub fn new() -> Self {
        ContextGraph {
            nodes: HashMap::new(),
        }
    }

    pub fn insert_context(&mut self, context: SemanticContext) {
        self.nodes.insert(context.id, context);
    }
}
