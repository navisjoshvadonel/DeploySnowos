#!/bin/bash

# =========================================================
# SNOWOS DIGITAL FROST LOGIN BOOTSTRAP
# =========================================================

export DISPLAY=:1
export XDG_SESSION_TYPE=x11

# Kill stuck sessions safely
pkill Xorg 2>/dev/null
pkill xinit 2>/dev/null

# Ensure Plymouth fully exits
plymouth quit 2>/dev/null

# Small stabilization delay
sleep 2

# Start dedicated X session
xinit /usr/bin/python3 /home/develop/snowos/snowos-login/login_app.py -- :1 vt1 -nolisten tcp
