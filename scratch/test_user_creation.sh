#!/bin/bash
USER_NAME="test-snowos-sys"
GROUP_NAME="test-snowos-sys"
HOME_DIR="/var/lib/snowos/test"

echo "Testing groupadd..."
groupadd -f -r "$GROUP_NAME" 2>&1 || echo "groupadd failed"

echo "Testing useradd..."
useradd -r -M -d "$HOME_DIR" -s /usr/sbin/nologin -g "$GROUP_NAME" "$USER_NAME" 2>&1 || echo "useradd failed"

echo "Checking result..."
id "$USER_NAME" || echo "User not found"
grep "$USER_NAME" /etc/passwd || echo "Not in passwd"
