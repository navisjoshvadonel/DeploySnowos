// implementation/nyx/inference/remote_runtime.rs

use crate::inference::provider::InferenceProvider;

pub struct RemoteRuntime {
    api_endpoint: String,
}

impl RemoteRuntime {
    pub fn new(endpoint: &str) -> Self {
        RemoteRuntime {
            api_endpoint: endpoint.to_string(),
        }
    }
}

impl InferenceProvider for RemoteRuntime {
    fn evaluate_intent(&self, _raw_input: &str) -> Result<String, String> {
        // Network execution. PolicyGuard must explicitly approve this capability.
        Ok("intent_parsed".to_string())
    }

    fn extract_entities(&self, _text: &str) -> Result<Vec<String>, String> {
        Ok(vec![])
    }
}
