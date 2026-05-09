import os
import sys

import requests

BRIDGE_URL = os.environ.get("SNOWOS_BRIDGE_URL", "http://127.0.0.1:8000/bridge/error")


def main():
    if len(sys.argv) < 3:
        return

    command = sys.argv[1]
    exit_code = sys.argv[2]
    error_msg = sys.argv[3] if len(sys.argv) > 3 else ""
    cwd = os.getcwd()

    payload = {
        "command": command,
        "exit_code": exit_code,
        "error": error_msg,
        "cwd": cwd,
    }

    try:
        response = requests.post(BRIDGE_URL, json=payload, timeout=2)
        if response.status_code == 200:
            data = response.json()
            if data.get("suggestion"):
                print(f"\nSnowOS Nyx Suggestion: {data['suggestion']}")
                if data.get("fix_cmd"):
                    print(f"SnowOS Nyx Fix command: {data['fix_cmd']}")
    except Exception:
        pass


if __name__ == "__main__":
    main()
