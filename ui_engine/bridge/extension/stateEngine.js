import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import GLib from 'gi://GLib';

export class StateEngine {
    constructor() {
        this._state = 'explore'; // default
        this._setupListeners();
    }

    _setupListeners() {
        // In a real implementation, we would listen for window focus changes
        // or system events (e.g., idle time for Night mode)
        this._focusConnection = global.display.connect('notify::focus-window', () => {
            this._handleFocusChange();
        });
    }

    _handleFocusChange() {
        const focusWindow = global.display.focus_window;
        if (focusWindow) {
            // If a window is focused and it's full screen, enter Focus Mode
            if (focusWindow.is_fullscreen()) {
                this.setState('focus');
            } else {
                this.setState('explore');
            }
        }
    }

    setState(newState) {
        if (this._state === newState) return;
        
        console.log(`SnowOS State Engine: Transitioning to ${newState}`);
        
        // Remove old state class
        Main.uiGroup.remove_style_class_name(`snowos-state-${this._state}`);
        
        this._state = newState;
        
        // Add new state class
        Main.uiGroup.add_style_class_name(`snowos-state-${this._state}`);
        
        this._applyStateBehaviors();
    }

    _applyStateBehaviors() {
        if (this._state === 'focus') {
            Main.panel.hide();
            // In a real shell, we'd apply blur to background windows here
        } else {
            Main.panel.show();
        }
    }

    destroy() {
        if (this._focusConnection) {
            global.display.disconnect(this._focusConnection);
        }
    }
}
