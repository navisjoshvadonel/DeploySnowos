/**
 * Nyx Core Engine
 * The central intelligence layer of SnowOS.
 * Orchestrates event listening, context interpretation, and UI hooks.
 */

import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import { EventListener } from '../events/event-listener.js';
import { ContextEngine } from '../context/context-engine.js';
import { NyxHooks, updateHook } from '../hooks/nyx-hooks.js';

class NyxCore {
    constructor() {
        this.logDir = '/home/develop/snowos/logs';
        this.memoryPath = '/home/develop/snowos/ai/nyx/memory/nyx-memory.jsonl';
        this.nyxEventLog = '/home/develop/snowos/logs/nyx-events.log';
        
        this.contextEngine = new ContextEngine();
        this.listener = new EventListener(this.logDir, this.onEvent.bind(this));
    }

    start() {
        console.log('❄️ Nyx AI Awareness Layer Starting...');
        this.listener.start();
        
        // Initial state
        this.updateUI();

        // Keep the process alive
        this.loop = new GLib.MainLoop(null, false);
        this.loop.run();
    }

    onEvent(event) {
        // 1. Normalize and process context
        const context = this.contextEngine.processEvent(event);

        // 2. Log to system memory
        this.logToMemory(event, context);

        // 3. Update UI hooks
        this.updateUI(context);

        // 4. Structured logging
        this.logEvent(event, context);
    }

    updateUI(context = null) {
        if (!context) return;

        // Drive UI state based on context
        if (context.session_type === 'coding') {
            updateHook('dock_glow_intensity', 0.8);
            updateHook('icon_pulse_state', 'breathing');
            updateHook('awareness_level', 2);
        } else if (context.session_type === 'idle') {
            updateHook('dock_glow_intensity', 0.2);
            updateHook('icon_pulse_state', 'inactive');
            updateHook('awareness_level', 0);
        } else {
            updateHook('dock_glow_intensity', 0.5);
            updateHook('icon_pulse_state', 'active');
            updateHook('awareness_level', 1);
        }

        updateHook('active_session_type', context.session_type);
        updateHook('workspace_focus_hint', true);
    }

    logToMemory(event, context) {
        const entry = {
            timestamp: new Date().toISOString(),
            event_type: event.type,
            app: context.active_app,
            session: context.session_type,
            workspace: context.workspace
        };

        try {
            const file = Gio.File.new_for_path(this.memoryPath);
            const out = file.append_to(Gio.FileCreateFlags.NONE, null);
            const message = JSON.stringify(entry) + '\n';
            out.write_all(message, null);
            out.close(null);
        } catch (e) {}
    }

    logEvent(event, context) {
        const timestamp = new Date().toISOString();
        const message = `[${timestamp}] [NYX] Context Shift: ${context.session_type} (App: ${context.active_app}, Workspace: ${context.workspace})\n`;
        
        try {
            const file = Gio.File.new_for_path(this.nyxEventLog);
            const out = file.append_to(Gio.FileCreateFlags.NONE, null);
            out.write_all(message, null);
            out.close(null);
        } catch (e) {}
    }
}

// Entry Point
const nyx = new NyxCore();
nyx.start();
