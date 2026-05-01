import os
import sys
import signal
import time


from ai_core.nyx_kernel import NyxAI

def main():
    print("❄️ Starting Nyx Headless Service...")
    # Initialize Nyx without starting the interactive terminal
    nyx = NyxAI(autonomous=False)
    
    print("✅ Nyx Core and API Server are now active.")
    print("🌐 Listening on port 4040...")
    
    # Keep the main thread alive
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        print("\nStopping Nyx...")
        nyx.scheduler.stop()
        nyx.scheduler_engine.stop()
        nyx.knowledge.stop()
        nyx.reflection.stop()
        nyx.autonomy.stop()
        nyx.api_server.stop()
        nyx.ui_state.stop()
        nyx.arch_profiler.stop()

if __name__ == "__main__":
    main()
