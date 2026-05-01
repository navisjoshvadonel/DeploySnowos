/**
 * Nyx Event Listener
 * Monitors SnowOS motion logs and streams them to the core engine.
 * Uses GJS / Gio for file monitoring.
 */

import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

export class EventListener {
    constructor(logDir, callback) {
        this.logDir = logDir;
        this.callback = callback;
        this.monitors = [];
        this.fileOffsets = {};
    }

    start() {
        const directory = Gio.File.new_for_path(this.logDir);
        const enumerator = directory.enumerate_children('standard::name', Gio.FileQueryInfoFlags.NONE, null);
        
        let info;
        while ((info = enumerator.next_file(null))) {
            const fileName = info.get_name();
            if (fileName.startsWith('motion-') && fileName.endsWith('.log')) {
                this._monitorFile(fileName);
            }
        }

        console.log(`Nyx Listener: Monitoring ${this.logDir}`);
    }

    _monitorFile(fileName) {
        const filePath = `${this.logDir}/${fileName}`;
        const file = Gio.File.new_for_path(filePath);
        
        // Initialize offset to end of file to only capture new events
        try {
            const info = file.query_info('standard::size', Gio.FileQueryInfoFlags.NONE, null);
            this.fileOffsets[fileName] = info.get_size();
        } catch (e) {
            this.fileOffsets[fileName] = 0;
        }

        const monitor = file.monitor_file(Gio.FileMonitorFlags.NONE, null);
        monitor.connect('changed', (m, f, other, eventType) => {
            if (eventType === Gio.FileMonitorEvent.CHANGED || eventType === Gio.FileMonitorEvent.CHANGES_DONE_HINT) {
                this._readNewLines(fileName, filePath);
            }
        });
        this.monitors.push(monitor);
    }

    _readNewLines(fileName, filePath) {
        const file = Gio.File.new_for_path(filePath);
        try {
            const [success, contents] = file.load_contents(null);
            if (!success) return;

            // Use TextDecoder if available, else fallback to ByteArray
            let text;
            if (typeof TextDecoder !== 'undefined') {
                text = new TextDecoder().decode(contents);
            } else {
                text = imports.byteArray.toString(contents);
            }
            
            const lastProcessed = this.fileOffsets[fileName] || 0;
            const currentSize = contents.length;

            if (currentSize > lastProcessed) {
                const newText = text.substring(lastProcessed);
                const newLines = newText.split('\n').filter(l => l.trim().length > 0);
                
                newLines.forEach(line => {
                    const event = this._parseLine(line);
                    if (event) this.callback(event);
                });

                this.fileOffsets[fileName] = currentSize;
            }
        } catch (e) {
            console.error(`Error reading ${fileName}: ${e}`);
        }
    }

    _parseLine(line) {
        const regex = /^\[(.+?)\]\s+(.+?):\s+(.+)$/;
        const match = line.match(regex);
        if (match) {
            return {
                timestamp: match[1],
                type: match[2],
                data: match[3]
            };
        }
        return null;
    }
}
