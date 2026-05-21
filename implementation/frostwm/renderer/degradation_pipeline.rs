// implementation/frostwm/renderer/degradation_pipeline.rs

use std::process::Command;

pub enum RenderingTier {
    Tier1NativeVulkan,
    Tier2OpenGL,
    Tier3Software,
}

pub struct HardwareDetector;

impl HardwareDetector {
    /// Probes the system environment rapidly during early boot.
    /// Does not block on long GPU queries; relies on Early KMS state.
    pub fn negotiate_capability() -> RenderingTier {
        let virt_check = Command::new("systemd-detect-virt")
            .output()
            .expect("Failed to execute systemd-detect-virt");

        if virt_check.status.success() {
            // We are inside KVM, VMware, or VirtualBox.
            // Aggressively drop to software to prevent UI deadlocks.
            println!("[FrostWM] Virtualized environment detected. Downgrading to Tier 3 Software Renderer.");
            return RenderingTier::Tier3Software;
        }

        // Fast path check for Vulkan support via DRM nodes
        let has_vulkan = std::path::Path::new("/dev/dri/renderD128").exists();
        if has_vulkan {
            RenderingTier::Tier1NativeVulkan
        } else {
            RenderingTier::Tier2OpenGL
        }
    }
}

pub fn apply_degradation(tier: RenderingTier, backend: &mut crate::renderer::vulkan_backend::VulkanBackend) {
    match tier {
        RenderingTier::Tier1NativeVulkan => backend.load_cinematic_pipeline(),
        RenderingTier::Tier2OpenGL => {
            // Strip glassmorphism, keep basic shadows
            backend.active_shaders.clear();
            backend.active_shaders.push(crate::renderer::vulkan_backend::ShaderStage::ShadowPass);
        },
        RenderingTier::Tier3Software => {
            // Pure Pixman. No GPU reliance.
            backend.active_shaders.clear();
        }
    }
}
