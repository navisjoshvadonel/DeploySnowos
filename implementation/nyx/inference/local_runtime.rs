// implementation/nyx/inference/local_runtime.rs

use crate::inference::provider::InferenceProvider;

pub struct LocalRuntime {
    model_path: String,
}

impl LocalRuntime {
    pub fn new(path: &str) -> Self {
        LocalRuntime {
            model_path: path.to_string(),
        }
    }
}

impl InferenceProvider for LocalRuntime {
    fn evaluate_intent(&self, _raw_input: &str) -> Result<String, String> {
        // High fidelity local execution (requires significant RAM/VRAM)
        Ok("intent_parsed".to_string())
    }

    fn extract_entities(&self, _text: &str) -> Result<Vec<String>, String> {
        Ok(vec![])
    }
}
