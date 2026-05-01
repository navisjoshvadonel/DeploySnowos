import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as WindowManager from 'resource:///org/gnome/shell/ui/windowManager.js';
import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';
import Shell from 'gi://Shell';

const UI_STATE_FILE = '/home/develop/snowos/nyx/ui_state.json';
const UI_MEMORY_FILE = '/home/develop/snowos/nyx/ui_memory.json';

export default class SnowOSMotionExtension extends Extension {
    enable() {
        this._settings = this._loadConfig();
        this._initMotionPersonality();

        this._originalAnimateWindow = Main.wm._animateWindow;
        Main.wm._animateWindow = this._animateWindow.bind(this);

        this._setupSpatialManager();
        this._setupAdaptiveUI();
        this._setupNyxHooks();
        this._setupWorkspaceListener();
        this._setupWindowPhysics();
        this._setupAIPulseBar();
        this._setupUIMemory();
        this._applyGlobalFrost();
        this._applyBranding();
        
        console.log('SnowOS Next-Gen UI Engine Enabled');
    }

    _applyBranding() {
        // Hide Activities button label
        this._activitiesButton = Main.panel.statusArea.activities;
        if (this._activitiesButton) {
            this._activitiesLabel = this._activitiesButton.get_first_child();
            if (this._activitiesLabel) {
                this._activitiesLabel.hide();
            }
            
            // Add SnowOS Icon
            this._snowosIcon = new St.Icon({
                icon_name: 'snowflake',
                style_class: 'system-status-icon snowos-panel-logo'
            });
            this._activitiesButton.add_child(this._snowosIcon);
        }
    }


    disable() {
        Main.wm._animateWindow = this._originalAnimateWindow;
        if (this._adaptiveTimeout) GLib.source_remove(this._adaptiveTimeout);
        if (this._aiPulseBar) {
            this._aiPulseBar.destroy();
            this._aiPulseBar = null;
        }
        this._removeEffects();
        console.log('SnowOS Next-Gen UI Engine Disabled');
    }

    _loadConfig() {
        return {
            duration: 350,
            scale_start: 0.96,
            z_offset: 30,
            blur_sigma: 15,
            personality: 'default',
            physics_inertia: 0.1
        };
    }

    _initMotionPersonality() {
        switch (this._settings.personality) {
            case 'calm':
                this._settings.duration = 600;
                this._settings.mode = Clutter.AnimationMode.EASE_IN_OUT_SINE;
                break;
            case 'dev':
                this._settings.duration = 200;
                this._settings.mode = Clutter.AnimationMode.EASE_OUT_EXPO;
                break;
            default:
                this._settings.duration = 350;
                this._settings.mode = Clutter.AnimationMode.EASE_OUT_QUART;
        }
    }

    _getUIContext() {
        try {
            let [success, contents] = GLib.file_get_contents(UI_STATE_FILE);
            if (success) {
                return JSON.parse(new TextDecoder().decode(contents));
            }
        } catch (e) {}
        return { stress: 0, focus: 'active', intent: 'none' };
    }

    _animateWindow(shellwm, actor, type, mask) {
        let context = this._getUIContext();
        
        let effectiveZ = context.stress > 0.8 ? 0 : this._settings.z_offset;

        if (type === WindowManager.WindowAnimationType.MAP) {
            actor.set_pivot_point(0.5, 0.5);
            actor.set_scale(this._settings.scale_start, this._settings.scale_start);
            actor.set_opacity(0);
            actor.set_translation(0, 0, -effectiveZ);

            actor.ease({
                scale_x: 1.0,
                scale_y: 1.0,
                opacity: 255,
                translation_z: 0,
                duration: this._settings.duration,
                mode: this._settings.mode,
                onComplete: () => {
                    shellwm.completed_map(actor);
                }
            });
            return;
        }

        if (type === WindowManager.WindowAnimationType.DESTROY) {
            actor.set_pivot_point(0.5, 0.5);
            actor.ease({
                scale_x: this._settings.scale_start,
                scale_y: this._settings.scale_start,
                opacity: 0,
                translation_z: -effectiveZ,
                duration: this._settings.duration,
                mode: this._settings.mode,
                onComplete: () => {
                    shellwm.completed_destroy(actor);
                }
            });
            return;
        }

        this._originalAnimateWindow.call(Main.wm, shellwm, actor, type, mask);
    }

    _setupSpatialManager() {
        this._focusId = global.display.connect('notify::focus-window', () => {
            let win = global.display.focus_window;
            this._applySpatialEffects(win);
        });
    }

    _applySpatialEffects(focusedWin) {
        let context = this._getUIContext();
        let effectiveZ = context.stress > 0.8 ? 0 : this._settings.z_offset;
        let effectiveBlur = context.stress > 0.6 ? 2 : this._settings.blur_sigma;

        global.get_window_actors().forEach(actor => {
            let metaWin = actor.get_meta_window();
            
            let isRelated = false;
            if (focusedWin) {
                if (metaWin.get_transient_for() === focusedWin || focusedWin.get_transient_for() === metaWin) {
                    isRelated = true;
                }
            }

            if (metaWin === focusedWin || isRelated) {
                actor.ease({
                    translation_z: 0,
                    duration: 300,
                    mode: Clutter.AnimationMode.EASE_OUT_QUAD
                });
                if (actor._blurEffect) {
                    actor.remove_effect(actor._blurEffect);
                    actor._blurEffect = null;
                }
                
                if (isRelated && !actor._rippled) {
                    this._triggerRipple(actor);
                }
            } else {
                actor.ease({
                    translation_z: -effectiveZ,
                    duration: 400,
                    mode: Clutter.AnimationMode.EASE_OUT_QUAD
                });
                if (!actor._blurEffect && effectiveBlur > 0) {
                    actor._blurEffect = new Shell.BlurEffect({
                        sigma: effectiveBlur,
                        brightness: 0.9
                    });
                    actor.add_effect(actor._blurEffect);
                } else if (actor._blurEffect) {
                    actor._blurEffect.set_sigma(effectiveBlur);
                }
            }
        });
    }

    _triggerRipple(actor) {
        actor._rippled = true;
        actor.ease({
            scale_x: 1.02,
            scale_y: 1.02,
            duration: 150,
            mode: Clutter.AnimationMode.EASE_OUT_QUAD,
            onComplete: () => {
                actor.ease({
                    scale_x: 1.0,
                    scale_y: 1.0,
                    duration: 150,
                    mode: Clutter.AnimationMode.EASE_IN_QUAD,
                    onComplete: () => { actor._rippled = false; }
                });
            }
        });
    }

    _setupWindowPhysics() {
        this._windowMoveId = global.display.connect('window-demands-attention', (display, win) => {
            let actor = win.get_compositor_private();
            if (actor) {
                actor.ease({
                    scale_x: 1.05,
                    scale_y: 1.05,
                    duration: 100,
                    mode: Clutter.AnimationMode.EASE_OUT_QUAD,
                    onComplete: () => {
                        actor.ease({
                            scale_x: 1.0,
                            scale_y: 1.0,
                            duration: 200,
                            mode: Clutter.AnimationMode.EASE_IN_ELASTIC
                        });
                    }
                });
            }
        });
    }

    _setupAdaptiveUI() {
        this._adaptiveTimeout = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 2, () => {
            this._refreshAdaptiveState();
            return GLib.SOURCE_CONTINUE;
        });
    }

    _refreshAdaptiveState() {
        let context = this._getUIContext();
        let isNight = new Date().getHours() >= 20 || new Date().getHours() < 6;

        if (this._panelBlur) {
            let targetBlur = context.stress > 0.7 ? 10 : 30;
            this._panelBlur.set_sigma(targetBlur);
        }

        if (context.stress > 0.7) {
            this._setDockMode('compact');
        } else {
            this._setDockMode('normal');
        }

        if (isNight) {
            Main.panel.add_style_class_name('snowos-night-frost');
        } else {
            Main.panel.remove_style_class_name('snowos-night-frost');
        }
    }

    _setDockMode(mode) {
        let settings = new Gio.Settings({ schema_id: 'org.gnome.shell.extensions.dash-to-dock' });
        try {
            if (mode === 'compact') {
                settings.set_int('dash-max-icon-size', 32);
            } else {
                settings.set_int('dash-max-icon-size', 48);
            }
        } catch (e) {}
    }

    _setupAIPulseBar() {
        this._aiPulseBar = new St.BoxLayout({
            name: 'ai-pulse-bar',
            style_class: 'ai-pulse-bar',
            reactive: true,
            can_focus: true,
            track_hover: true,
            height: 4,
            width: 200
        });

        Main.panel._centerBox.add_child(this._aiPulseBar);
        this._animateAIPulse();
    }

    _animateAIPulse() {
        if (!this._aiPulseBar) return;
        let context = this._getUIContext();
        let isActive = context.ai_active || false;
        
        let targetOpacity = isActive ? 255 : 150;
        let minOpacity = isActive ? 100 : 50;
        let duration = isActive ? 500 : 2000;

        this._aiPulseBar.ease({
            opacity: targetOpacity,
            duration: duration,
            mode: Clutter.AnimationMode.EASE_IN_OUT_SINE,
            onComplete: () => {
                if (!this._aiPulseBar) return;
                this._aiPulseBar.ease({
                    opacity: minOpacity,
                    duration: duration,
                    mode: Clutter.AnimationMode.EASE_IN_OUT_SINE,
                    onComplete: () => this._animateAIPulse()
                });
            }
        });
    }

    _setupUIMemory() {
        // Track window position changes
        this._windowChangedId = global.display.connect('window-demands-attention', (display, win) => {
            this._recordWindowMemory(win);
        });
        
        this._windowFocusId = global.display.connect('notify::focus-window', () => {
            let win = global.display.focus_window;
            if (win) this._recordWindowMemory(win);
        });
    }

    _recordWindowMemory(win) {
        let appId = win.get_wm_class() || win.get_title();
        let frame = win.get_frame_rect();
        
        let memory = {};
        try {
            let [success, contents] = GLib.file_get_contents(UI_MEMORY_FILE);
            if (success) memory = JSON.parse(new TextDecoder().decode(contents));
        } catch (e) {}

        if (!memory.window_placements) memory.window_placements = {};
        memory.window_placements[appId] = { x: frame.x, y: frame.y, w: frame.width, h: frame.height };

        try {
            GLib.file_set_contents(UI_MEMORY_FILE, JSON.stringify(memory, null, 2));
        } catch (e) {}
    }

    _applyGlobalFrost() {
        this._panelBlur = new Shell.BlurEffect({
            sigma: 30,
            brightness: 0.7
        });
        Main.panel.add_effect(this._panelBlur);
        Main.panel.add_style_class_name('snowos-frost-panel');
    }

    _removeEffects() {
        if (this._panelBlur) Main.panel.remove_effect(this._panelBlur);
        global.get_window_actors().forEach(actor => {
            if (actor._blurEffect) {
                actor.remove_effect(actor._blurEffect);
            }
        });
    }

    _setupNyxHooks() {
        this._windowCreatedId = global.display.connect('window-created', (display, win) => {
            this._logInteraction('app_launch', win.get_wm_class() || win.get_title());
        });
    }

    _setupWorkspaceListener() {
        this._workspaceId = global.workspace_manager.connect('active-workspace-changed', () => {
            this._logInteraction('workspace_change', global.workspace_manager.get_active_workspace_index().toString());
        });
    }

    _logInteraction(event, data) {
        let logPath = `/home/develop/snowos/logs/motion-${event}.log`;
        let message = `[${new Date().toISOString()}] ${event}: ${data}\n`;
        try {
            let file = Gio.File.new_for_path(logPath);
            let out = file.append_to(Gio.FileCreateFlags.NONE, null);
            out.write_all(message, null);
            out.close(null);
        } catch (e) {}
    }
}
