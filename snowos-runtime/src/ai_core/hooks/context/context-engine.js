/**
 * Nyx Context Engine
 * Merges raw events into high-level user intent and session states.
 */

export class ContextEngine {
    constructor() {
        this.currentContext = {
            active_app: null,
            window_title: null,
            workspace: 0,
            session_type: 'idle',
            last_activity: Date.now(),
            focus_patterns: []
        };
    }

    processEvent(event) {
        this.currentContext.last_activity = Date.now();

        switch (event.type) {
            case 'focus_change':
                this.currentContext.window_title = event.data;
                this.currentContext.active_app = this._normalizeAppName(event.data);
                break;
            case 'workspace_change':
                this.currentContext.workspace = parseInt(event.data);
                break;
            case 'app_launch':
                this.currentContext.active_app = this._normalizeAppName(event.data);
                break;
        }

        this._detectSessionType();
        return this.currentContext;
    }

    _normalizeAppName(title) {
        if (!title) return 'unknown';
        const t = title.toLowerCase();
        if (t.includes('code') || t.includes('visual studio') || t.includes('vim') || t.includes('terminal')) return 'development';
        if (t.includes('firefox') || t.includes('chrome') || t.includes('browser')) return 'browsing';
        if (t.includes('settings') || t.includes('control center')) return 'system';
        return title;
    }

    _detectSessionType() {
        const app = this.currentContext.active_app;
        
        if (app === 'development') {
            this.currentContext.session_type = 'coding';
        } else if (app === 'browsing') {
            this.currentContext.session_type = 'research';
        } else if (app === 'system') {
            this.currentContext.session_type = 'maintenance';
        } else {
            this.currentContext.session_type = 'general';
        }

        // Detect idle (though usually handled by external idle timer)
        if (Date.now() - this.currentContext.last_activity > 300000) {
            this.currentContext.session_type = 'idle';
        }
    }

    getContext() {
        return { ...this.currentContext };
    }
}
