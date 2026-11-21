#!/bin/bash
# Install or update frame-webapps on a Steam Frame (run in Desktop Mode, in Konsole):
#
#   curl -fsSL https://raw.githubusercontent.com/breferrari/frame-webapps/main/install.sh | bash
#
# Installs into ~/.local/share/frame-webapps (nothing system-wide, no sudo), then runs `frame-webapp setup`, which adds
# the `frame-webapp` command, the "Web Apps" manager (Steam library and desktop menu) and one small systemd user unit
# (see README: "What install.sh changes"). Nothing is restarted.
#   FRAME_WEBAPPS_HOME=/path   install somewhere else
#   FRAME_WEBAPPS_SRC=/path    copy from a local checkout instead of cloning (for development)
set -euo pipefail

REPO="${FRAME_WEBAPPS_REPO:-https://github.com/breferrari/frame-webapps}"
DEST="${FRAME_WEBAPPS_HOME:-$HOME/.local/share/frame-webapps}"

for tool in git flatpak python3 rsvg-convert; do
  command -v "$tool" >/dev/null || { echo "Missing program: $tool. frame-webapps is made for SteamOS on the Steam Frame."; exit 1; }
done
flatpak info org.chromium.Chromium >/dev/null 2>&1 ||
  echo "Note: Chromium isn't installed yet. Install it with: flatpak install flathub org.chromium.Chromium"

echo "== installing to $DEST"
if [ -n "${FRAME_WEBAPPS_SRC:-}" ]; then
  mkdir -p "$DEST"
  (cd "$FRAME_WEBAPPS_SRC" && git ls-files -co --exclude-standard -z | tar --null -T - -cf -) | tar -xf - -C "$DEST"
elif [ -d "$DEST/.git" ]; then
  git -C "$DEST" config core.fileMode false   # a chmod must never block an update
  git -C "$DEST" pull --ff-only
elif [ -e "$DEST" ] && [ -n "$(ls -A "$DEST" 2>/dev/null)" ]; then
  echo "$DEST exists and isn't a git checkout. Move it away or set FRAME_WEBAPPS_HOME."; exit 1
else
  git clone --depth 1 "$REPO" "$DEST"
  git -C "$DEST" config core.fileMode false
fi
chmod +x "$DEST/bin/frame-webapp" "$DEST"/scripts/*.sh "$DEST"/scripts/*.py "$DEST"/webapps/*.sh "$DEST/manager/Web Apps"

echo "== setting up"
"$DEST/bin/frame-webapp" setup

echo
echo "Done. Open \"Web Apps\" from the Steam library or the desktop menu, or use the command:"
echo "    frame-webapp add \"Netflix\" https://www.netflix.com"
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) echo "(If 'frame-webapp' isn't found, use $HOME/.local/bin/frame-webapp)";; esac
