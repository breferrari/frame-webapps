#!/bin/bash
# Build the release archive: the tool plus a small compiled launcher, for installers that copy an app folder to the
# Frame and add one program from it to Steam (FramePort), and for anyone without git.
#
#   scripts/make-release.sh
#
# Builds from the committed state (git archive HEAD) on an aarch64 Linux machine with gcc, such as the Frame itself.
# Writes dist/frame-webapps-v<version>-steamos-arm64.tar.gz and updates frameport.json (version, address, checksum).
# Then: commit frameport.json, tag v<version>, and upload the archive to that release.
set -euo pipefail

ROOT="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
cd "$ROOT"
[ "$(uname -m)" = aarch64 ] || { echo "Build this on an aarch64 machine (the launcher is compiled natively)."; exit 1; }
VERSION="$(python3 -I bin/frame-webapp --version | awk '{print $2}')"
NAME="frame-webapps-v$VERSION-steamos-arm64"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
STAGE="$WORK/frame-webapps"
mkdir -p "$STAGE" dist

git archive HEAD bin manager scripts systemd webapps launcher LICENSE README.md docs/web-apps.md | tar -x -C "$STAGE"
rm -f "$STAGE/scripts/make-release.sh"

# The program an installer adds to Steam, and the .desktop file that names it and the app.
gcc -Os -static -nostdlib -ffreestanding -fno-stack-protector -Wall -o "$STAGE/web-apps" launcher/web-apps.c
strip "$STAGE/web-apps"
cp manager/icon.png "$STAGE/web-apps.png"
printf '[Desktop Entry]\nType=Application\nName=Web Apps\nComment=Add websites to Steam as apps with controller support\nExec=web-apps\nIcon=web-apps\nCategories=Utility;\n' > "$STAGE/web-apps.desktop"
echo "Installed from the release archive. Apps and icons live in ~/.local/share/frame-webapps." > "$STAGE/.external"

# Same bytes for the same commit: fixed order, owner and time.
tar --sort=name --owner=0 --group=0 --numeric-owner --mtime="$(git log -1 --format=%cI)" \
    -C "$WORK" -cf - frame-webapps | gzip -n > "dist/$NAME.tar.gz"
SHA="$(sha256sum "dist/$NAME.tar.gz" | cut -d' ' -f1)"

cat > frameport.json <<JSON
{
  "schema": "framedrop.install/v1",
  "name": "Web Apps",
  "version": "$VERSION",
  "files": [{ "url": "https://github.com/breferrari/frame-webapps/releases/download/v$VERSION/$NAME.tar.gz", "sha256": "$SHA" }],
  "frameport": {
    "description": "Add websites to your Steam library as apps that work with the controller.",
    "icon": "https://raw.githubusercontent.com/breferrari/frame-webapps/main/manager/icon.png"
  }
}
JSON
echo "dist/$NAME.tar.gz  ($(stat -c %s "dist/$NAME.tar.gz") bytes)"
echo "sha256 $SHA"
