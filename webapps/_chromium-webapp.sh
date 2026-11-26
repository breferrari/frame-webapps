#!/bin/bash
# Shared launcher for Chromium "web apps" on the Steam Frame (Flathub Chromium, app mode, fullscreen).
#   [WEBAPP_EXTENSIONS="ext1,ext2"] _chromium-webapp.sh <WindowClass> <URL> [extra chromium args]
# Called by the per-app launchers that `frame-webapp add` writes into apps/.
#
# Each web app has ITS OWN Chromium profile (…/config/webapp-<WindowClass>), separate from your normal Chromium.
# Why: Flatpak gives every Chromium instance a private /tmp, so a second instance can't reach the first one's
# SingletonSocket to hand over. It then takes over the shared profile while the first still uses it, which shows
# a pile of "Profile error occurred" windows. Separate profiles can run side by side. You sign in once per app.
#
# Stale lock fix: Flatpak Chromium always runs as PID 2 in its sandbox, so its lock is "<host>-2". After a
# session restart kills it, the lock stays and blocks the next start. If no Chromium is using THIS profile,
# remove the leftover Singleton* files.
#
# Controllers: Steam can't link a Flatpak window to its shortcut, so a layout's keys/wheel never reach the page.
# Instead the shortcut keeps a *gamepad* layout in Steam and the "frame-gamepad" extension (extensions/frame-gamepad)
# reads the virtual Xbox pad via the Gamepad API inside the page.
# Chromium's gamepad backend needs the udev database, which the Flatpak sandbox lacks: --filesystem=/run/udev:ro.
CLASS="$1"; URL="$2"; shift 2
APP_ID=org.chromium.Chromium
CFG="$HOME/.var/app/$APP_ID/config"
PROFILE="$CFG/webapp-$CLASS"
ROOT="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"   # the frame-webapps folder
EXT_ROOT="$ROOT/webapps/extensions"
mkdir -p "$PROFILE" "$ROOT/logs"

# Widevine (DRM, needed by Crunchyroll/Netflix…): a new profile has none on its first start, so DRM video would fail
# once. scripts/widevine.sh copies it in, fetching it first if this Frame has no copy yet (about a minute, once).
# The manager needs no DRM: it starts right away and fetches in the background, ready for the first app.
if [ "$CLASS" = FrameWebAppsManager ]; then
  (bash "$ROOT/scripts/widevine.sh" --fetch >/dev/null 2>&1 &)
else
  bash "$ROOT/scripts/widevine.sh" "$PROFILE" >/dev/null 2>&1
fi

if ! pgrep -f -- "--user-data-dir=$PROFILE( |$)" >/dev/null; then
  rm -f "$PROFILE/SingletonLock" "$PROFILE/SingletonSocket" "$PROFILE/SingletonCookie"
fi

# Per-app extensions (comma-separated names under webapps/extensions/).
EXT_ARGS=()
if [ -n "${WEBAPP_EXTENSIONS:-}" ]; then
  dirs=""
  IFS=',' read -ra exts <<< "$WEBAPP_EXTENSIONS"
  for e in "${exts[@]}"; do [ -f "$EXT_ROOT/$e/manifest.json" ] && dirs="${dirs:+$dirs,}$EXT_ROOT/$e"; done
  [ -n "$dirs" ] && EXT_ARGS=(--load-extension="$dirs")
fi
# TV mode: present the browser as a TV, so sites such as youtube.com/tv serve their TV interface.
[ "${WEBAPP_TV:-}" = 1 ] && EXT_ARGS+=("--user-agent=Mozilla/5.0 (SMART-TV; Linux; Tizen 6.0) AppleWebKit/537.36 (KHTML, like Gecko) 85.0.4183.93/6.0 TV Safari/537.36")
echo "$(date '+%F %T') $CLASS ${URL%%\?*} extensions=${WEBAPP_EXTENSIONS:-none}" >> "$ROOT/logs/launch.log"   # without any query (it may hold a token)

# Chromium's own log (media/DRM/GPU errors, and the extension's "[frame-gamepad]" lines), last run only.
exec > "$ROOT/logs/$CLASS-chromium.log" 2>&1

exec flatpak run --filesystem=/run/udev:ro "$APP_ID" \
  --enable-logging=stderr --v=0 \
  --ozone-platform=x11 \
  --user-data-dir="$PROFILE" \
  --app="$URL" \
  --start-fullscreen \
  --class="$CLASS" \
  --no-first-run \
  --no-default-browser-check \
  --hide-crash-restore-bubble \
  --disable-features=Translate \
  "${EXT_ARGS[@]}" \
  "$@"
