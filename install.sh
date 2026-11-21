#!/bin/bash
# Install or update frame-webapps on a Steam Frame (run in Desktop Mode, in Konsole):
#
#   curl -fsSL https://raw.githubusercontent.com/breferrari/frame-webapps/main/install.sh | bash
#
# Installs into ~/.local/share/frame-webapps (nothing system-wide, no sudo), adds the `frame-webapp` command and an
# "Add Web App" entry to the desktop menu, and two small systemd user units (see README: "What install.sh changes").
# Nothing is restarted.
#   FRAME_WEBAPPS_HOME=/path   install somewhere else
#   FRAME_WEBAPPS_SRC=/path    copy from a local checkout instead of cloning (for development)
set -euo pipefail

REPO="${FRAME_WEBAPPS_REPO:-https://github.com/breferrari/frame-webapps}"
DEST="${FRAME_WEBAPPS_HOME:-$HOME/.local/share/frame-webapps}"
UNITS="$HOME/.config/systemd/user"
# Desktop Mode runs a nested session whose XDG_RUNTIME_DIR is not the one systemd --user listens on.
userctl() { XDG_RUNTIME_DIR="/run/user/$(id -u)" systemctl --user "$@"; }

for tool in git flatpak python3 rsvg-convert steamos-add-to-steam; do
  command -v "$tool" >/dev/null || { echo "Missing program: $tool. frame-webapps is made for SteamOS on the Steam Frame."; exit 1; }
done
flatpak info org.chromium.Chromium >/dev/null 2>&1 ||
  echo "Note: Chromium isn't installed yet. Install it with: flatpak install flathub org.chromium.Chromium"

echo "== installing to $DEST"
if [ -n "${FRAME_WEBAPPS_SRC:-}" ]; then
  mkdir -p "$DEST"
  (cd "$FRAME_WEBAPPS_SRC" && git ls-files -co --exclude-standard -z | tar --null -T - -cf -) | tar -xf - -C "$DEST"
elif [ -d "$DEST/.git" ]; then
  git -C "$DEST" pull --ff-only
elif [ -e "$DEST" ] && [ -n "$(ls -A "$DEST" 2>/dev/null)" ]; then
  echo "$DEST exists and isn't a git checkout. Move it away or set FRAME_WEBAPPS_HOME."; exit 1
else
  git clone --depth 1 "$REPO" "$DEST"
fi
mkdir -p "$DEST/apps" "$DEST/icons" "$DEST/logs" "$DEST/pending"
chmod +x "$DEST/bin/frame-webapp" "$DEST"/scripts/*.sh "$DEST"/scripts/*.py "$DEST"/webapps/*.sh

echo "== command and menu entry"
mkdir -p "$HOME/.local/bin" "$HOME/.local/share/applications"
ln -sf "$DEST/bin/frame-webapp" "$HOME/.local/bin/frame-webapp"
cat > "$HOME/.local/share/applications/frame-webapps-add.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Add Web App
Comment=Turn a website into a Steam app with controller support (frame-webapps)
Exec="$DEST/bin/frame-webapp" gui
Icon=list-add
Categories=Utility;
Terminal=false
EOF
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

echo "== systemd user units"
mkdir -p "$UNITS/steam.service.d"
sed "s|@ROOT@|$DEST|g" "$DEST/systemd/frame-webapps-chromium-lock.service" > "$UNITS/frame-webapps-chromium-lock.service"
sed "s|@ROOT@|$DEST|g" "$DEST/systemd/steam-pending.conf" > "$UNITS/steam.service.d/frame-webapps-pending.conf"
if userctl daemon-reload 2>/dev/null; then
  userctl enable frame-webapps-chromium-lock.service >/dev/null 2>&1 || true
else
  echo "Couldn't reach systemd (no user session?). The units are installed and take effect at the next login."
fi

echo
echo "Done. Add your first web app:"
echo "    frame-webapp add \"Netflix\" https://www.netflix.com"
echo "or open \"Add Web App\" from the desktop menu. Then launch it from the Steam library."
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) echo "(If 'frame-webapp' isn't found, use $HOME/.local/bin/frame-webapp)";; esac
