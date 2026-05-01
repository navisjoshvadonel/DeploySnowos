#!/bin/bash

# SnowOS GDM Rebuild Script
# This script extracts the Yaru theme, injects SnowOS branding, and recompiles the gresource.

BUILD_DIR="/home/develop/snowos/gdm-theme-build-v2"
RESOURCE_FILE="/usr/share/gnome-shell/theme/Yaru/gnome-shell-theme.gresource"
OUTPUT_RESOURCE="$BUILD_DIR/snowos.gresource"
LOCAL_GDM_CSS="$BUILD_DIR/theme/gdm.css"

# Backup the local CSS if it exists before extraction overwrites it
if [ -f "$LOCAL_GDM_CSS" ]; then
    echo "Backing up local gdm.css..."
    cp "$LOCAL_GDM_CSS" "$BUILD_DIR/gdm.css.tmp"
fi

mkdir -p "$BUILD_DIR/theme"

echo "Extracting current theme..."
for file in $(gresource list "$RESOURCE_FILE"); do
    # Skip extracting gdm.css if we want to keep our custom one
    # Actually, we extract everything then overwrite gdm.css
    mkdir -p "$BUILD_DIR/theme$(dirname "${file#/org/gnome/shell/theme}")"
    gresource extract "$RESOURCE_FILE" "$file" > "$BUILD_DIR/theme${file#/org/gnome/shell/theme}"
done

echo "Restoring/Injecting SnowOS CSS..."
if [ -f "$BUILD_DIR/gdm.css.tmp" ]; then
    cp "$BUILD_DIR/gdm.css.tmp" "$LOCAL_GDM_CSS"
    rm "$BUILD_DIR/gdm.css.tmp"
else
    # Fallback to the one in /etc if no local temp exists
    cp "/etc/alternatives/gdm3-theme/snowos.css" "$LOCAL_GDM_CSS"
fi

echo "Generating XML manifest..."
# Filter out any files that might cause issues and ensure all files are included
cat <<EOF > "$BUILD_DIR/snowos.gresource.xml"
<?xml version="1.0" encoding="UTF-8"?>
<gresources>
  <gresource prefix="/org/gnome/shell/theme">
$(find "$BUILD_DIR/theme" -type f -not -path '*/.*' -printf "    <file>%P</file>\n")
  </gresource>
</gresources>
EOF

echo "Compiling new gresource..."
cd "$BUILD_DIR/theme"
glib-compile-resources --target="$OUTPUT_RESOURCE" "../snowos.gresource.xml"

echo "Build complete: $OUTPUT_RESOURCE"
echo "To apply, run: sudo cp $OUTPUT_RESOURCE /usr/share/gnome-shell/theme/Yaru/gnome-shell-theme.gresource"
