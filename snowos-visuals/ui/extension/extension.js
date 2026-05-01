import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as WindowManager from 'resource:///org/gnome/shell/ui/windowManager.js';
import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';

const SNOWOS_MOTION_CONF = '/home/develop/snowos/ui/theme/snowos-motion.conf';

export default class SnowOSMotionExtension extends Extension {
    enable() {
        this._settings = {
            duration: 350,
            scale_start: 0.96,
            curve: [0.2, 0.8, 0.2, 1.0],
            inactive_dim: 0.4
        };

        this._originalAnimateWindow = Main.wm._animateWindow;
        Main.wm._animateWindow = this._animateWindow.bind(this);

        this._setupNyxHooks();
        this._setupWorkspaceListener();
        
        console.log('SnowOS Motion Extension Enabled');
    }

    disable() {
        Main.wm._animateWindow = this._originalAnimateWindow;
        this._settings = null;
        console.log('SnowOS Motion Extension Disabled');
    }

    _animateWindow(shellwm, actor, type, mask) {
        // SnowOS Custom Window Animations: Fade + Scale
        if (type === WindowManager.WindowAnimationType.MAP) {
            actor.set_pivot_point(0.5, 0.5);
            actor.set_scale(this._settings.scale_start, this._settings.scale_start);
            actor.set_opacity(0);

            actor.ease({
                scale_x: 1.0,
                scale_y: 1.0,
                opacity: 255,
                duration: this._settings.duration,
                mode: Clutter.AnimationMode.EASE_OUT_QUART,
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
                duration: this._settings.duration,
                mode: Clutter.AnimationMode.EASE_IN_QUART,
                onComplete: () => {
                    shellwm.completed_destroy(actor);
                }
            });
            return;
        }

        this._originalAnimateWindow.call(Main.wm, shellwm, actor, type, mask);
    }

    _setupNyxHooks() {
        // Nyx Hooks: Focus change
        this._focusId = global.display.connect('notify::focus-window', () => {
            let win = global.display.focus_window;
            if (win) {
                this._logInteraction('focus_change', win.get_title());
                this._applyFocusEffect(win);
            }
        });

        // Nyx Hooks: App launch (simplified via window map)
        this._windowCreatedId = global.display.connect('window-created', (display, win) => {
            this._logInteraction('app_launch', win.get_wm_class() || win.get_title());
        });
    }

    _applyFocusEffect(win) {
        // Remove glow from all windows first (simplified)
        global.get_window_actors().forEach(actor => {
            actor.remove_style_class_name('window-focus-glow');
        });

        let actor = win.get_compositor_private();
        if (actor) {
            actor.add_style_class_name('window-focus-glow');
        }
    }

    _setupWorkspaceListener() {
        this._workspaceId = global.workspace_manager.connect('active-workspace-changed', () => {
            let index = global.workspace_manager.get_active_workspace_index();
            this._logInteraction('workspace_change', index.toString());
            this._applyWorkspaceEffects();
        });
    }

    _applyWorkspaceEffects() {
        // Future implementation for dimming inactive workspaces
        // This usually requires iterating through all window actors and applying effects
    }

    _logInteraction(event, data) {
        let logPath = `/home/develop/snowos/logs/motion-${event}.log`;
        let timestamp = new Date().toISOString();
        let message = `[${timestamp}] ${event}: ${data}\n`;
        
        // Simple file append for hooks
        try {
            let file = Gio.File.new_for_path(logPath);
            let out = file.append_to(Gio.FileCreateFlags.NONE, null);
            out.write_all(message, null);
            out.close(null);
        } catch (e) {
            // Silently fail if log dir doesn't exist
        }
    }
}
