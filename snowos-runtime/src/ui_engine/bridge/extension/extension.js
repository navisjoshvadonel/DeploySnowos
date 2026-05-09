import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import Shell from 'gi://Shell';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import { DockEngine } from './dock.js';
import { StateEngine } from './stateEngine.js';
import { NyxBridge } from './nyxBridge.js';

export default class SnowOSUIEngine extends Extension {
    enable() {
        console.log('SnowOS UI Engine: Enabled');
        this._applyStyles();
        this._setupShader();
        this._setupAperture();
        this._setupDock();
        this._setupShortcuts();
        this._setupWindowListeners();
        this._dockEngine = new DockEngine(this._dock);
        this._stateEngine = new StateEngine();
        this._nyx = new NyxBridge(this._stateEngine);
    }

    disable() {
        console.log('SnowOS UI Engine: Disabled');
        this._removeWindowListeners();
        if (this._nyx) {
            this._nyx.destroy();
            this._nyx = null;
        }
        if (this._stateEngine) {
            this._stateEngine.destroy();
            this._stateEngine = null;
        }
        if (this._dockEngine) {
            this._dockEngine.destroy();
            this._dockEngine = null;
        }
        this._destroyDock();
        this._destroyAperture();
        this._destroyShader();
        this._removeStyles();
        this._removeShortcuts();
    }

    _setupWindowListeners() {
        this._windowTracker = Shell.WindowTracker.get_default();
        this._onWindowOpened = global.display.connect('window-created', (display, window) => {
            this._bloomWindow(window);
        });
    }

    _removeWindowListeners() {
        if (this._onWindowOpened) {
            global.display.disconnect(this._onWindowOpened);
        }
    }

    _bloomWindow(window) {
        // Find the actor for this window
        const actor = window.get_compositor_private();
        if (!actor) return;

        actor.set_pivot_point(0.5, 0.5);
        actor.set_scale(0.9, 0.9);
        actor.set_opacity(0);
        
        actor.ease({
            scale_x: 1.0,
            scale_y: 1.0,
            opacity: 255,
            translation_y: -10,
            duration: 500,
            mode: Clutter.AnimationMode.EASE_OUT_QUART,
            onComplete: () => {
                actor.ease({
                    translation_y: 0,
                    duration: 300,
                    mode: Clutter.AnimationMode.EASE_IN_OUT_SINE
                });
            }
        });
    }

    _setupShader() {
        // Frost Shader Layer - Animated Noise & Particles
        this._shader = new St.Widget({
            style_class: 'snowos-shader',
            visible: true,
            reactive: false,
            x_expand: true,
            y_expand: true
        });
        Main.uiGroup.add_child(this._shader);
        Main.uiGroup.set_child_below_sibling(this._shader, null); // Base layer
    }

    _destroyShader() {
        if (this._shader) {
            this._shader.destroy();
            this._shader = null;
        }
    }

    _setupDock() {
        this._dock = new St.BoxLayout({
            style_class: 'snowos-dock',
            vertical: false,
            visible: true,
            reactive: true,
            x_expand: false,
            y_expand: false,
            x_align: Clutter.ActorAlign.CENTER,
            y_align: Clutter.ActorAlign.END
        });

        Main.uiGroup.add_child(this._dock);
        
        const constraint = new Clutter.AlignConstraint({
            source: Main.layoutManager.uiGroup,
            align_axis: Clutter.AlignAxis.X_AXIS,
            factor: 0.5
        });
        this._dock.add_constraint(constraint);
    }

    _destroyDock() {
        if (this._dock) {
            this._dock.destroy();
            this._dock = null;
        }
    }

    _setupAperture() {
        this._aperture = new St.BoxLayout({
            style_class: 'snowos-aperture',
            vertical: true,
            visible: false,
            reactive: true,
            can_focus: true,
            track_hover: true,
            x_expand: true,
            y_expand: true,
        });

        const label = new St.Label({
            text: 'Aperture • Nyx AI',
            style_class: 'aperture-title'
        });
        this._aperture.add_child(label);

        Main.uiGroup.add_child(this._aperture);
        
        // Center it
        const constraint = new Clutter.AlignConstraint({
            source: Main.layoutManager.uiGroup,
            align_axis: Clutter.AlignAxis.BOTH,
            factor: 0.5
        });
        this._aperture.add_constraint(constraint);
    }

    _destroyAperture() {
        if (this._aperture) {
            this._aperture.destroy();
            this._aperture = null;
        }
    }

    _setupShortcuts() {
        // In a real shell environment, we would use Main.wm.addKeybinding
        // For this prototype, we'll simulate the toggle logic
        this._toggleAperture = () => {
            this._aperture.visible = !this._aperture.visible;
            if (this._aperture.visible) {
                this._aperture.grab_key_focus();
            }
        };
        console.log('SnowOS UI Engine: Shortcuts initialized (Meta+Space)');
    }

    _removeShortcuts() {
        console.log('SnowOS UI Engine: Shortcuts removed');
    }

    _applyStyles() {
        // Placeholder for applying custom CSS classes to shell elements
        Main.panel.add_style_class_name('snowos-panel');
    }

    _removeStyles() {
        Main.panel.remove_style_class_name('snowos-panel');
    }
}
