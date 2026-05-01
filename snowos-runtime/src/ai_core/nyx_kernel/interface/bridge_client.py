import sys
import requests
import json
import os

def main():
    if len(sys.argv) < 3:
        return

    command = sys.argv[1]
    exit_code = sys.argv[2]
    error_msg = sys.argv[3] if len(sys.argv) > 3 else ""
    
    # Context
    cwd = os.getcwd()
    
    payload = {
        "command": command,
        "exit_code": exit_code,
        "error": error_msg,
        "cwd": cwd
    }

    try:
        # Send to Nyx Backend (assuming port 4040 as configured in nyx.py)
        # We use a direct internal processing call for speed if we can, 
        # but here we use the API to remain decoupled.
        response = requests.post(
            "http://localhost:4040/bridge/error", 
            json=payload,
            timeout=2
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("suggestion"):
                print(f"\n\033[1;34m❄️ Nyx Suggestion:\033[0m {data['suggestion']}")
                if data.get("fix_cmd"):
                    print(f"\033[1;32m🔧 Fix command:\033[0m {data['fix_cmd']}")
    except Exception:
        pass

if __name__ == "__main__":
    main()
