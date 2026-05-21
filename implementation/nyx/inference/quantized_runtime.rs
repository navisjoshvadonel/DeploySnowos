// implementation/nyx/inference/quantized_runtime.rs

use crate::inference::provider::InferenceProvider;

pub struct QuantizedRuntime {
    // Uses heavily quantized models (e.g., Q4_K_M) specifically for intent routing, not chatting.
}

impl QuantizedRuntime {
    pub fn new() -> Self {
        QuantizedRuntime {}
    }
}

impl InferenceProvider for QuantizedRuntime {
    fn evaluate_intent(&self, _raw_input: &str) -> Result<String, String> {
        // Fast, low-memory execution
        Ok("intent_parsed".to_string())
    }

    fn extract_entities(&self, _text: &str) -> Result<Vec<String>, String> {
        Ok(vec![])
    }
}
