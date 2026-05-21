#!/bin/bash
# snowos/validation/analysis/boot_analyzer.sh

echo "[*] Running SnowOS Boot Timeline Analyzer..."

# Extract timings from systemd-analyze
FIRMWARE=$(systemd-analyze time | grep -oP '\d+(?=ms \(firmware\))|\d+\.\d+(?=s \(firmware\))')
KERNEL=$(systemd-analyze time | grep -oP '\d+(?=ms \(kernel\))|\d+\.\d+(?=s \(kernel\))')
INITRD=$(systemd-analyze time | grep -oP '\d+(?=ms \(initrd\))|\d+\.\d+(?=s \(initrd\))')
USERSPACE=$(systemd-analyze time | grep -oP '\d+(?=ms \(userspace\))|\d+\.\d+(?=s \(userspace\))')

# Convert everything to milliseconds for math (rough parsing for simplicity in this stub)
TOTAL_MS=0

# Example budget assertions
BUDGET_MS=5000

# Get time graphical.target was reached
GRAPHICAL=$(systemd-analyze show graphical.target --property=ActiveEnterTimestampMonotonic | cut -d= -f2)

if [ -z "$GRAPHICAL" ] || [ "$GRAPHICAL" -eq 0 ]; then
    echo "[-] FAIL: graphical.target was never reached or blocked indefinitely."
    exit 1
fi

GRAPHICAL_MS=$((GRAPHICAL / 1000))

echo "[+] graphical.target reached in ${GRAPHICAL_MS}ms."

if [ "$GRAPHICAL_MS" -gt "$BUDGET_MS" ]; then
    echo "[-] FAIL: Boot time (${GRAPHICAL_MS}ms) exceeded 5000ms budget."
    exit 1
else
    echo "[+] PASS: Boot time is within budget."
fi

# Export telemetry to JSON for the regression runner
cat <<EOF > /tmp/boot_timings.json
{
  "firmware": "$FIRMWARE",
  "kernel": "$KERNEL",
  "initrd": "$INITRD",
  "userspace": "$USERSPACE",
  "total_ms": "$GRAPHICAL_MS"
}
EOF

exit 0
