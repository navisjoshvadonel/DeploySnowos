import socket
import json
import sys
import time

SOCKET_PATH = "/tmp/snowos_broker.sock"

def request_permission(source_id, target_resource, action, context=""):
    payload = {
        "source_id": source_id,
        "target_resource": target_resource,
        "action": action,
        "context": context
    }
    
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        try:
            client.connect(SOCKET_PATH)
            client.sendall(json.dumps(payload).encode('utf-8'))
            response_data = client.recv(4096)
            return json.loads(response_data.decode('utf-8'))
        except FileNotFoundError:
            return {"status": "ERROR", "reason": "Permission Broker is not running."}
        except Exception as e:
            return {"status": "ERROR", "reason": str(e)}

if __name__ == "__main__":
    app_id = "app.mock_app"
    
    print(f"--- SnowOS Zero Trust Test ({app_id}) ---")
    
    # Test 1: Authorized Action
    print("\n[+] Attempting authorized network connection...")
    resp1 = request_permission(app_id, "network.lan", "connect", "Syncing local data")
    print(f"Response: {resp1}")
    
    # Test 2: Unauthorized Action
    print("\n[!] Attempting unauthorized filesystem access...")
    resp2 = request_permission(app_id, "filesystem.root", "write")
    print(f"Response: {resp2}")
    
    # Test 3: AI Sentinel Anomaly (Velocity attack)
    print("\n[!] Simulating Data Exfiltration Anomaly (rapid authorized requests)...")
    for i in range(7):
        resp3 = request_permission(app_id, "network.lan", "connect", "Syncing local data")
        print(f"Request {i+1}: {resp3}")
        time.sleep(0.05)
