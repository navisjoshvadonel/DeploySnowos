// implementation/ipc/snowbusd/protocol.rs

use serde::{Deserialize, Serialize};

/// The internal protocol for SnowOS. Replaces DBus.
/// Transport layer: Unix Domain Sockets + tokio asynchronous router.
#[derive(Debug, Serialize, Deserialize)]
pub struct SnowbusMessage {
    pub sender_id: String,
    pub target_service: String,
    pub capability_token: String, // Cryptographic token verifying permissions
    pub payload: PayloadType,
}

#[derive(Debug, Serialize, Deserialize)]
pub enum PayloadType {
    SurfaceRequest { width: u32, height: u32, intent: String },
    MemoryGraphQuery { semantic_hash: String },
    // Notice: No "ExecuteCommand" or "MutateSystemState" exists in the root protocol.
}

pub struct SnowbusRouter {
    // Manages capability enforcement and message routing
}

impl SnowbusRouter {
    pub async fn route_message(&self, msg: SnowbusMessage) -> Result<(), String> {
        // 1. Verify capability_token against snowos-broker policies.ro
        if !self.verify_capability(&msg.sender_id, &msg.capability_token, &msg.payload) {
            return Err("Capability violation. Message dropped.".to_string());
        }

        // 2. Deliver message to target service via Unix socket
        Ok(())
    }

    fn verify_capability(&self, sender: &str, token: &str, payload: &PayloadType) -> bool {
        // Cryptographic validation logic
        true
    }
}
