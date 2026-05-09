/**
 * Nyx UI Hooks
 * Defines the placeholder states for visual feedback.
 * Driven by ai/nyx/core/nyx-core.js
 */

export const NyxHooks = {
    // Dock glow intensity (0.0 to 1.0)
    dock_glow_intensity: 0.0,

    // Icon pulse state (inactive, breathing, alert)
    icon_pulse_state: 'inactive',

    // Workspace focus hint (true if user seems focused on current workspace)
    workspace_focus_hint: false,

    // Awareness level (0: Idle, 1: Observing, 2: Active)
    awareness_level: 0,

    // Active session type
    active_session_type: 'none',

    // --- STAGE 44 UPGRADES ---
    // Predicted next action for UI hinting
    predicted_action: null,

    // System stress level for Adaptive UI (0.0 to 1.0)
    system_stress_level: 0.0,

    // Global window depth map (spatial awareness)
    window_depth_map: {}
};

export function updateHook(key, value) {
    if (NyxHooks.hasOwnProperty(key)) {
        NyxHooks[key] = value;
        // In the future, this will emit a signal to the UI layer (Stage 44D)
    }
}
