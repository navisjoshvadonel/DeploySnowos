import os
import time

def main():
    print("[WeatherAgent] Starting up...")
    
    # 1. Retrieve injected capability token
    token = os.environ.get("SNOWOS_TOKEN")
    
    if not token:
        print("[WeatherAgent] ERROR: No capability token injected. Sandbox broken.")
        return
        
    print(f"[WeatherAgent] Successfully received capability token: {token}")
    print("[WeatherAgent] Attempting to connect to Permission Broker with token...")
    
    # Simulate doing work
    try:
        while True:
            print("[WeatherAgent] Fetching weather data (Authorized)...")
            time.sleep(1)
    except KeyboardInterrupt:
        print("[WeatherAgent] Shutting down cleanly.")

if __name__ == "__main__":
    main()
