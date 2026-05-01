import http.server
import socketserver
import json
import os
import time
import threading

PORT = 8000
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

# Mock event data to simulate live broker/sentinel feeds
mock_events = [
    {"id": 1, "time": "10:24:01", "source": "app.browser", "action": "network.wan", "status": "GRANTED", "type": "broker"},
    {"id": 2, "time": "10:24:05", "source": "app.mock_app", "action": "display.surface", "status": "GRANTED", "type": "broker"},
    {"id": 3, "time": "10:24:06", "source": "app.mock_app", "action": "hardware.keyboard", "status": "DENIED", "type": "broker"},
    {"id": 4, "time": "10:24:07", "source": "app.mock_app", "action": "KEYLOGGER PREVENTION", "status": "CRITICAL", "type": "sentinel"}
]

class SnowControlHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=FRONTEND_DIR, **kwargs)

    def do_GET(self):
        if self.path == '/api/events':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(mock_events).encode())
        elif self.path == '/api/system_state':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            state = {
                "cpu": "12%",
                "ram": "2.4 GB",
                "agents_active": 3,
                "trust_score": 98
            }
            self.wfile.write(json.dumps(state).encode())
        else:
            # Serve static frontend files
            super().do_GET()

def run_server():
    with socketserver.TCPServer(("", PORT), SnowControlHandler) as httpd:
        print(f"SnowControl Backend active at http://localhost:{PORT}")
        httpd.serve_forever()

if __name__ == "__main__":
    run_server()
