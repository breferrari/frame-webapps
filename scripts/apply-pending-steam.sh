#!/bin/bash
# Runs as ExecStartPre of steam.service (drop-in: ~/.config/systemd/user/steam.service.d/frame-webapps-pending.conf),
# i.e. just BEFORE Steam starts, after it has written its files on exit. Steam rewrites shortcuts.vdf and its
# controller configs from memory when it exits, so edits made while it runs are lost. Queued edits applied here stick,
# and nothing has to be restarted to queue them.
#
# Pending files in pending/ (each deleted once applied; with none, this does nothing):
#   shortcut-removals   lines "/path/to/launcher|"                 -> removes the shortcut whose Exe is that launcher
#   shortcut-renames    lines "Old name|New name"                  -> renames a shortcut
#   shortcut-icons      lines "App name|/path/icon.png"            -> sets each shortcut's icon field
#   controller-layouts  lines "/path/layout.vdf|app1 app2 ..." or "--template=<Steam template>|app ..." -> sets those apps' layout
ROOT="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"   # the frame-webapps folder
PENDING="$ROOT/pending"
S="$ROOT/scripts"
mkdir -p "$ROOT/logs"
LOG="$ROOT/logs/steam-pending.log"

run_queue() {   # run_queue <file> <command per line...>
  local f="$PENDING/$1" ok=1; shift
  [ -f "$f" ] || return 0
  echo "=== $(date '+%F %T') pending: $(basename "$f") (applied before Steam start)"
  while IFS='|' read -r a b; do
    [ -n "$a" ] || continue
    case "$a" in \#*) continue;; esac
    "$@" "$a" "$b" || ok=0
  done < "$f"
  [ "$ok" = 1 ] && rm -f "$f" || echo "some entries failed; keeping $(basename "$f") for the next start"
}

removal() { python3 -I "$S/steam-shortcuts.py" remove-exe "$1"; }
rename()  { python3 -I "$S/steam-shortcuts.py" rename "$1" "$2"; }
icon()    { python3 -I "$S/steam-shortcuts.py" set-icon "$1" "$2"; }
layout()  { python3 -I "$S/apply-controller-layout.py" "$1" $2; }

{
  run_queue shortcut-removals removal
  run_queue shortcut-renames rename
  run_queue shortcut-icons icon
  run_queue controller-layouts layout
} >> "$LOG" 2>&1
exit 0
