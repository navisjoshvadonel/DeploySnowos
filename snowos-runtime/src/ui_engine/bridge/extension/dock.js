import Clutter from 'gi://Clutter';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import GLib from 'gi://GLib';

export class DockEngine {
    constructor(dockWidget) {
        this._dock = dockWidget;
        this._revealZone = 50; 
        this._velocityThreshold = 0.5;
        this._lastPos = { x: 0, y: 0 };
        this._lastTime = 0;
        this._isVisible = true; // For testing
        
        this._setupIcons();
        this._setupListeners();
    }

    _setupIcons() {
        // Dummy icons for FrostLine demonstration
        const iconNames = ['system-file-manager', 'utilities-terminal', 'browser', 'nyx-ai'];
        this._icons = [];

        iconNames.forEach(name => {
            const icon = new St.Icon({
                icon_name: name,
                style_class: 'snowos-icon',
                icon_size: 48,
                reactive: true,
                track_hover: true
            });
            this._dock.add_child(icon);
            this._icons.push(icon);
        });
    }

    _setupListeners() {
        this._pointerConnection = global.stage.connect('captured-event', (actor, event) => {
            if (event.type() === Clutter.EventType.MOTION) {
                this._handleMotion(event);
            }
            return Clutter.EVENT_PROPAGATE;
        });
    }

    _handleMotion(event) {
        const [x, y] = event.get_coords();
        const time = event.get_time();
        
        // Magnification logic
        this._icons.forEach(icon => {
            const [ix, iy] = icon.get_transformed_position();
            const [iw, ih] = icon.get_transformed_size();
            const icx = ix + iw / 2;
            const icy = iy + ih / 2;
            
            const dist = Math.sqrt(Math.pow(x - icx, 2) + Math.pow(y - icy, 2));
            const threshold = 150;
            
            if (dist < threshold) {
                const scale = 1 + (0.3 * (1 - dist / threshold));
                icon.set_scale(scale, scale);
            } else {
                icon.set_scale(1, 1);
            }
        });

        this._lastPos = { x, y };
        this._lastTime = time;
    }

    _reveal() {
        if (this._isVisible) return;
        this._isVisible = true;
        this._dock.ease({
            translation_y: 0,
            opacity: 255,
            duration: 300,
            mode: Clutter.AnimationMode.EASE_OUT_QUART
        });
    }

    _hide() {
        if (!this._isVisible) return;
        this._isVisible = false;
        this._dock.ease({
            translation_y: 100,
            opacity: 0,
            duration: 300,
            mode: Clutter.AnimationMode.EASE_IN_QUART
        });
    }

    destroy() {
        if (this._pointerConnection) {
            global.stage.disconnect(this._pointerConnection);
        }
    }
}
