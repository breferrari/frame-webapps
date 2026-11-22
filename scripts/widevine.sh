#!/bin/bash
# Make sure a web app's Chromium profile has the Widevine DRM component before its first start.
#
#   widevine.sh <profile dir>      copy the component into the profile (fetching it first if nobody has it yet)
#   widevine.sh --fetch            only fetch it into the shared seed profile, for later copies
#
# Why: Chromium downloads Widevine by itself about a minute after a profile's first start, and only uses it from the
# next start on. So in a brand-new profile, DRM sites fail the first time (Crunchyroll shows KAT-6005, for example).
# Earlier versions copied the component from your normal Chromium profile, which only helps if you had used Chromium.
# Now, when no copy exists anywhere, a headless Chromium fetches one into a seed profile (about a minute, once).
APP_ID=org.chromium.Chromium
CFG="$HOME/.var/app/$APP_ID/config"
MAIN="${FRAME_WEBAPPS_MAIN_PROFILE:-$CFG/chromium}"   # your normal Chromium profile (the variable is for tests)
SEED="$CFG/frame-webapps-widevine-seed"
HINT=latest-component-updated-widevine-cdm

has() { ls "$1"/WidevineCdm/*/_platform_specific/*/libwidevinecdm.so >/dev/null 2>&1; }

fetch() {
  has "$SEED" && return 0
  mkdir -p "$SEED"
  (
    flock -w 240 9 || exit 1          # one fetch at a time; a second caller waits for the first
    has "$SEED" && exit 0
    rm -f "$SEED"/Singleton*
    flatpak run "$APP_ID" --headless=new --user-data-dir="$SEED" --no-first-run about:blank >/dev/null 2>&1 &
    for _ in $(seq 1 90); do has "$SEED" && break; sleep 2; done
    sleep 2                           # let it finish writing
    pkill -f -- "--user-data-dir=$SEED( |\$)" 2>/dev/null
    sleep 1
    find "$SEED" -mindepth 1 -maxdepth 1 ! -name WidevineCdm -exec rm -rf {} + 2>/dev/null   # keep only the component
    has "$SEED"
  ) 9> "$SEED.lock"
}

if [ "${1:-}" = "--fetch" ]; then
  has "$MAIN" || fetch
  exit
fi

PROFILE="${1:?usage: widevine.sh <profile dir> | --fetch}"
has "$PROFILE" && exit 0
if has "$MAIN"; then SRC="$MAIN"; else fetch || exit 1; SRC="$SEED"; fi
mkdir -p "$PROFILE"
rm -rf "$PROFILE/WidevineCdm"
cp -a "$SRC/WidevineCdm" "$PROFILE/"
# The hint file names the component's folder: point it at this profile's copy.
VERSION_DIR="$(ls -d "$PROFILE"/WidevineCdm/*/ | head -1)"
printf '{"Path":"%s"}' "${VERSION_DIR%/}" > "$PROFILE/WidevineCdm/$HINT"
