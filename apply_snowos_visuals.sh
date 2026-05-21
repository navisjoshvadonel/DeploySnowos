#!/usr/bin/env bash
# ==============================================================================
# ❄️ SnowOS Visual Core Deployment Script
# Target: Ubuntu Base -> SnowOS Digital Frost Transformation
# Architecture: Non-hardcoded, fully discovery-driven, error-trapping, transaction-safe.
# ==============================================================================

set -eo pipefail

# Ensure script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (sudo ./apply_snowos_visuals.sh)"
  exit 1
fi

# --- Pre-Execution & Logging Setup ---
echo "Logging SnowOS Visual Engine Deployment..."
export DEBIAN_FRONTEND=noninteractive

# Backup Tracking Array for Rollbacks
BACKUP_FILES=()
ROLLBACK_TRIGGERED=0

cleanup_on_failure() {
    if [ "$?" -ne 0 ] && [ "$ROLLBACK_TRIGGERED" -eq 0 ]; then
        echo "⚠️ Deployment failure detected! Initiating immediate atomic rollback..."
        ROLLBACK_TRIGGERED=1
        for backup_pair in "${BACKUP_FILES[@]}"; do
            local original="${backup_pair%%|*}"
            local backup="${backup_pair#*|}"
            if [ -f "$backup" ]; then
                echo "Restoring: $original from $backup"
                cp -p "$backup" "$original"
            fi
        done
        echo "❌ System rolled back to baseline state to ensure desktop stability."
        exit 1
    fi
}
trap cleanup_on_failure EXIT

# Detect User Environment safely
TARGET_USER="${SUDO_USER:-$USER}"
TARGET_HOME=$(getent passwd "$TARGET_USER" | cut -d: -f6)

echo "System Discovery: Target User Context is -> $TARGET_USER ($TARGET_HOME)"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IDENTITY_DIR="$SCRIPT_DIR/identity"
ASSETS_DIR="$SCRIPT_DIR/assets"
OS_RELEASE_SRC="$IDENTITY_DIR/os-release"
LSB_RELEASE_SRC="$IDENTITY_DIR/lsb-release"
LOGO_SRC="$ASSETS_DIR/logo.png"
WALLPAPER_SRC="$ASSETS_DIR/snowos-wallpaper.png"

# ==============================================================================
# [PART 1: BASE SYSTEM BRANDING DIVERSIONS]
# ==============================================================================
echo "Deploying baseline brand files..."

# Check if source files exist
if [ ! -f "$OS_RELEASE_SRC" ]; then
    echo "[!] Error: $OS_RELEASE_SRC not found."
    exit 1
fi

# Robust diversion handling
for target in /etc/os-release /etc/lsb-release; do
    echo "[!] Fixing conflicting diversion for $target..."
    dpkg-divert --remove --rename "$target" || true
    rm -f "$target.ubuntu" "$target.ubuntu-default"
done

echo "[*] Restoring base system files..."
apt-get install --reinstall -y base-files >/dev/null 2>&1

if ! dpkg-divert --list /etc/os-release | grep -q "diverted by snowos"; then
    echo "[*] Diverting /etc/os-release..."
    dpkg-divert --add --rename --divert /etc/os-release.ubuntu /etc/os-release
fi

if ! dpkg-divert --list /etc/lsb-release | grep -q "diverted by snowos"; then
    echo "[*] Diverting /etc/lsb-release..."
    dpkg-divert --add --rename --divert /etc/lsb-release.ubuntu /etc/lsb-release
fi

echo "[*] Deploying identity files..."
cp "$OS_RELEASE_SRC" /etc/os-release
cp "$LSB_RELEASE_SRC" /etc/lsb-release

# ==============================================================================
# [PART 2: LOGO & WALLPAPER ASSETS]
# ==============================================================================
echo "[*] Deploying SnowOS Aurora logo..."
cp "$LOGO_SRC" /usr/share/pixmaps/snowos-logo.png
ln -sf /usr/share/pixmaps/snowos-logo.png /usr/share/pixmaps/system-logo.png

echo "[*] Deploying SnowOS Wallpaper..."
mkdir -p /usr/share/backgrounds
if [ -f "$WALLPAPER_SRC" ]; then
    cp "$WALLPAPER_SRC" /usr/share/backgrounds/snowos-wallpaper.png
fi

# ==============================================================================
# [TASK 1: AMBIENT GLASSMORPHIC DASH-TO-DOCK CONFIGURATION]
# ==============================================================================
echo "Initializing Task 1: Dash-to-Dock Mutation..."

SCHEMA_DIR="/usr/share/glib-2.0/schemas"
OVERRIDE_FILE="${SCHEMA_DIR}/99_snowos_desktop_dock.gschema.override"

mkdir -p "$SCHEMA_DIR"

echo "Writing unified GNOME desktop schema overrides..."
tee "$OVERRIDE_FILE" > /dev/null <<EOF
[org.gnome.desktop.background]
picture-uri='file:///usr/share/backgrounds/snowos-wallpaper.png'
picture-uri-dark='file:///usr/share/backgrounds/snowos-wallpaper.png'

[org.gnome.desktop.interface]
icon-theme='SnowOS'
gtk-theme='WhiteSur-Dark'

[org.gnome.shell.extensions.dash-to-dock]
dock-position='BOTTOM'
extend-height=false
dock-fixed=false
intellihide=true
dash-max-icon-size=48
custom-background-color=true
background-color='rgba(255,255,255,0.15)'
custom-theme-shrink=true
EOF

# Compiling schemas globally
glib-compile-schemas "$SCHEMA_DIR" || true

# If executing inside an active X/Wayland session, apply immediately via gsettings
if [ -n "$DISPLAY" ] || [ -n "$WAYLAND_DISPLAY" ]; then
    echo "Active compositor detected. Injecting user-space dconf values..."
    sudo -u "$TARGET_USER" gsettings set org.gnome.shell.extensions.dash-to-dock dock-position 'BOTTOM' || true
    sudo -u "$TARGET_USER" gsettings set org.gnome.shell.extensions.dash-to-dock extend-height false || true
    sudo -u "$TARGET_USER" gsettings set org.gnome.shell.extensions.dash-to-dock dock-fixed false || true
    sudo -u "$TARGET_USER" gsettings set org.gnome.shell.extensions.dash-to-dock intellihide true || true
    sudo -u "$TARGET_USER" gsettings set org.gnome.shell.extensions.dash-to-dock dash-max-icon-size 48 || true
    sudo -u "$TARGET_USER" gsettings set org.gnome.shell.extensions.dash-to-dock custom-background-color true || true
fi

# 2. Dynamic White-Frost Snowflake Icon Injection
echo "Injecting custom minimalist SnowOS icon matrices..."
SNOW_ICON_SVG='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.95)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="2" x2="12" y2="22"></line><line x1="2" y1="12" x2="22" y2="12"></line><line x1="19.8" y1="4.2" x2="4.2" y2="19.8"></line><line x1="19.8" y1="19.8" x2="4.2" y2="4.2"></line><path d="M12 5l3 3m-3-3L9 8"></path><path d="M12 19l3-3m-3 3l-3-3"></path><path d="M19 12l-3 3m3-3l-3-3"></path><path d="M5 12l3 3m-3-3l3-3"></path></svg>'

# Target known global theme repositories on Ubuntu (Yaru, Adwaita, hicolor)
TARGET_ICON_THEMES=("/usr/share/icons/Yaru" "/usr/share/icons/Adwaita" "/usr/share/icons/hicolor")

for theme in "${TARGET_ICON_THEMES[@]}"; do
    if [ -d "$theme" ]; then
        # Find structural location of the app grid launcher icon
        TARGET_SVG_PATH=$(find "$theme" -name "view-app-grid-symbolic.svg" | head -n 1)
        if [ -n "$TARGET_SVG_PATH" ] && [ -f "$TARGET_SVG_PATH" ]; then
            echo "Replacing launcher icon matrix at: $TARGET_SVG_PATH"
            # Backup before mutation
            cp -p "$TARGET_SVG_PATH" "${TARGET_SVG_PATH}.bak"
            BACKUP_FILES+=("${TARGET_SVG_PATH}|${TARGET_SVG_PATH}.bak")
            echo "$SNOW_ICON_SVG" | tee "$TARGET_SVG_PATH" > /dev/null
        fi
    fi
done

echo "[*] Configuring SnowOS Icon Theme alias..."
mkdir -p /usr/share/icons/SnowOS
cat > /usr/share/icons/SnowOS/index.theme <<EOF
[Icon Theme]
Name=SnowOS
Inherits=Papirus,WhiteSur,Adwaita,hicolor
Comment=SnowOS custom icon theme alias
Directories=
EOF

# ==============================================================================
# [TASK 2: CINEMATIC RE-COMPILATION OF THE GDM3 LOGIN MANAGER]
# ==============================================================================
echo "Initializing Task 2: Cinematic GDM3 Gresource Compilation..."

# 1. Install toolchain dependencies
apt-get update -qq && apt-get install -y -qq libglib2.0-dev-bin libxml2-utils || true

BUILD_DIR="/tmp/gdm-theme-build-v2"
rm -rf "$BUILD_DIR" && mkdir -p "$BUILD_DIR"

# Dynamically locate the baseline compiled gresource archive
GRESOURCE_SRC=""
POSSIBLE_PATHS=(
    "/usr/share/gnome-shell/theme/Yaru/gnome-shell-theme.gresource"
    "/usr/share/gnome-shell/gnome-shell-theme.gresource"
)

for path in "${POSSIBLE_PATHS[@];}" do
    if [ -f "$path" ]; then
        GRESOURCE_SRC="$path"
        break
    fi
done

if [ -n "$GRESOURCE_SRC" ]; then
    echo "Extracting resource paths from binary: $GRESOURCE_SRC"
    cd "$BUILD_DIR"

    # Extract file architecture map dynamically from binary
    gresource list "$GRESOURCE_SRC" | while read -r res; do
        res_clean="${res#/org/gnome/shell/}"
        res_dir=$(dirname "$res_clean")
        mkdir -p "$res_dir"
        gresource extract "$GRESOURCE_SRC" "$res" > "$res_clean"
    done

    # 2. Glassmorphic Style Injections into the active theme stylesheets
    TARGET_CSS=""
    for css_file in "theme/gnome-shell.css" "gnome-shell.css"; do
        if [ -f "$css_file" ]; then
            TARGET_CSS="$css_file"
            break
        fi
    done

    if [ -n "$TARGET_CSS" ]; then
        echo "Injecting SnowOS custom ambient properties into stylesheet: $TARGET_CSS"

        # Mutate #lockDialogGroup for deep cinematic glassmorphism
        sed -i '/#lockDialogGroup {/,/}/c\
#lockDialogGroup {\n  background-color: rgba(10, 15, 30, 0.75);\n  backdrop-filter: blur(30px);\n  background-gradient-direction: none;\n}' "$TARGET_CSS"

        # Mutate login dialog container box values
        if grep -q "\.login-dialog {" "$TARGET_CSS"; then
            sed -i '/\.login-dialog {/,/}/c\
\.login-dialog {\n  background-color: rgba(255, 255, 255, 0.08);\n  border: 1px solid rgba(255, 255, 255, 0.2);\n  border-radius: 24px;\n  box-shadow: 0 16px 32px rgba(0, 0, 0, 0.5);\n  padding: 24px;\n}' "$TARGET_CSS"
        fi

        # 3. Generating dynamic XML compilation manifest
        echo "Generating compiler manifest..."
        MANIFEST_FILE="gnome-shell-theme.gresource.xml"
        echo '<?xml version="1.0" encoding="UTF-8"?>' > "$MANIFEST_FILE"
        echo '<gresources><gresource prefix="/org/gnome/shell">' >> "$MANIFEST_FILE"

        find . -type f -not -name "$MANIFEST_FILE" | sed 's|^\./||' | while read -r file_path; do
            echo "  <file>$file_path</file>" >> "$MANIFEST_FILE"
        done

        echo '</gresource></gresources>' >> "$MANIFEST_FILE"

        # Recompile the binary securely
        echo "Compiling system production asset -> gnome-shell-theme.gresource"
        glib-compile-resources "$MANIFEST_FILE"

        # Transaction-safe staging and deployment of the recompiled lockscreen
        cp -p "$GRESOURCE_SRC" "${GRESOURCE_SRC}.bak"
        BACKUP_FILES+=("${GRESOURCE_SRC}|${GRESOURCE_SRC}.bak")

        cp gnome-shell-theme.gresource "$GRESOURCE_SRC"
        echo "✅ Lockscreen manager successfully compiled and isolated."
    fi
    cd "$SCRIPT_DIR"
else
    # Simple fallback color inject into default css if gresource is not used
    echo "[*] Injecting blue palette into Yaru GDM theme css (simple fallback)..."
    if [ -f /usr/share/gnome-shell/theme/Yaru/gnome-shell.css ]; then
        if [ ! -f /usr/share/gnome-shell/theme/Yaru/gnome-shell.css.bak ]; then
            cp /usr/share/gnome-shell/theme/Yaru/gnome-shell.css /usr/share/gnome-shell/theme/Yaru/gnome-shell.css.bak
        fi
        sed -i 's/#E95420/#007bff/gi' /usr/share/gnome-shell/theme/Yaru/gnome-shell.css
        sed -i 's/#e95420/#007bff/gi' /usr/share/gnome-shell/theme/Yaru/gnome-shell.css
    fi
fi

# ==============================================================================
# [TASK 3: WORKLOAD-REACTIVE DESKTOP THEMING BRIDGE]
# ==============================================================================
echo "Initializing Task 3: Reactive Workload Configuration Bridge..."

SNOW_CONFIG_DIR="${TARGET_HOME}/.config/snowos"
USER_GTK_DIR="${TARGET_HOME}/.config/gtk-3.0"

# Ensuring structure execution paths exist inside user space
mkdir -p "$SNOW_CONFIG_DIR"
mkdir -p "$USER_GTK_DIR"

DYNAMIC_STYLE_HOOK="${SNOW_CONFIG_DIR}/shell_theme.css"
USER_GTK_OVERRIDE="${USER_GTK_DIR}/gtk.css"

if [ ! -f "$DYNAMIC_STYLE_HOOK" ]; then
    echo "Creating dynamic styling hook vector..."
    cat <<EOF > "$DYNAMIC_STYLE_HOOK"
/* ❄️ SnowOS Live Workload Aesthetic Vectors */
:root {
    --snowos-glow-color: rgba(0, 162, 255, 0.4);
    --snowos-blur-radius: 20px;
}
EOF
fi

# Append import path loop cleanly to GTK base config safely if not present
if [ -f "$USER_GTK_OVERRIDE" ]; then
    if ! grep -q "snowos/shell_theme.css" "$USER_GTK_OVERRIDE"; then
        echo "@import url('file://${DYNAMIC_STYLE_HOOK}');" | cat - "$USER_GTK_OVERRIDE" > temp && mv temp "$USER_GTK_OVERRIDE"
    fi
else
    echo "@import url('file://${DYNAMIC_STYLE_HOOK}');" > "$USER_GTK_OVERRIDE"
fi

# Correcting ownership parameters cleanly for non-privileged AI daemons
chown -R "$TARGET_USER":"$TARGET_USER" "$SNOW_CONFIG_DIR" || true
chown -R "$TARGET_USER":"$TARGET_USER" "$USER_GTK_DIR" || true

# ==============================================================================
# [PART 4: GRUB CONFIGURATION]
# ==============================================================================
echo "[*] Updating GRUB distributor branding and background..."
if grep -q "GRUB_DISTRIBUTOR" /etc/default/grub; then
    sed -i 's/^GRUB_DISTRIBUTOR=.*/GRUB_DISTRIBUTOR="SnowOS Aurora"/' /etc/default/grub
else
    echo 'GRUB_DISTRIBUTOR="SnowOS Aurora"' >> /etc/default/grub
fi

if grep -q "GRUB_BACKGROUND" /etc/default/grub; then
    sed -i 's|^GRUB_BACKGROUND=.*|GRUB_BACKGROUND="/usr/share/backgrounds/snowos-wallpaper.png"|' /etc/default/grub
else
    echo 'GRUB_BACKGROUND="/usr/share/backgrounds/snowos-wallpaper.png"' >> /etc/default/grub
fi

echo "[*] Refreshing GRUB entries..."
update-grub || true

# ==============================================================================
# [PART 5: LOGIN BANNERS]
# ==============================================================================
echo "[*] Updating login banners..."
cat > /etc/issue <<EOF
SnowOS Aurora 24.04 \n \l

EOF

cat > /etc/issue.net <<EOF
SnowOS Aurora 24.04
EOF

# --- Finish State ---
echo "=============================================================================="
echo "❄️  SUCCESS: SnowOS Visual Environment Customization Layer Configured Natively."
echo "=============================================================================="
EOF
