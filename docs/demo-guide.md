# SnowOS v0.1 Demo Guide

The best way to understand SnowOS is to see its Zero Trust and AI capabilities in action. Follow this script to demonstrate the "wow" moments of the OS.

## 1. The Interface (Transparency)
1. **Action:** Open `SnowControl`.
2. **Talking Point:** "In most operating systems, the kernel is a black box. In SnowOS, this dashboard is your window into the AI's brain. You can see every permission granted, every threat blocked, and every resource optimized in real-time."
3. **Visual:** Point out the live Intelligence Feed and the System Health Monitor.

## 2. The Threat (Zero Trust Enforcement)
1. **Action:** Run the provided `mock_app.py` script. This script simulates an application trying to read the local filesystem without the proper capability token.
2. **Talking Point:** "Watch what happens when an unauthorized script tries to act. Because we use a Zero Trust Permission Broker, it doesn't just fail silently."
3. **Visual:** Show the red `BLOCKING: UNAUTHORIZED PROCESS` alert pop up instantly in SnowControl, alongside the AI Sentinel logging the anomaly.

## 3. The Intelligence (Proactive Optimization)
1. **Action:** Launch a heavy, known foreground application (like a game or an IDE).
2. **Talking Point:** "Now, watch the AI Core. It detects the heavy foreground load and looks at historical telemetry."
3. **Visual:** Show the Intelligence Feed logging: `[KERNEL ACTION] Reniced system.updater (PID: 500) to +19 to free CPU cycles.`
4. **Talking Point:** "SnowOS just proactively throttled a background update to guarantee your foreground app stays smooth. It didn't ask you to close the updater; it just handled the resource arbitration autonomously."

## 4. The Control (User Override)
1. **Action:** In SnowControl, click to manually revoke a previously granted network permission for a module.
2. **Talking Point:** "While the AI is smart, you are always the absolute authority. Revoking this token immediately kills the module's network access at the socket level."
