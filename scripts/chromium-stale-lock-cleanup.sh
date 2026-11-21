#!/bin/bash
# Clear stale Flatpak-Chromium profile locks left behind when a session restart kills Chromium.
# Runs at each VR-session start (frame-webapps-chromium-lock.service, WantedBy=gamescope-session.target).
#
# Flatpak Chromium always runs as PID 2 in its sandbox, so its SingletonLock is "<host>-2". The next Chromium finds
# PID 2 alive (itself) and refuses the profile ("in use by another process"). Only acts when NO Chromium runs.
APP_ID=org.chromium.Chromium
CFG="$HOME/.var/app/$APP_ID/config"
ROOT="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"   # the frame-webapps folder
LOG="$ROOT/chromium-locks.log"
if flatpak ps --columns=application 2>/dev/null | grep -qx "$APP_ID"; then
  echo "$(date '+%F %T') Chromium is running; not touching locks" >> "$LOG"
  exit 0
fi
for d in "$CFG/chromium" "$CFG"/webapp-*; do
  [ -L "$d/SingletonLock" ] || continue
  rm -f "$d/SingletonLock" "$d/SingletonSocket" "$d/SingletonCookie"
  echo "$(date '+%F %T') cleared stale lock in ${d#$HOME/}" >> "$LOG"
done
exit 0
