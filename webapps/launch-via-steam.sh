#!/bin/bash
# Launch a non-Steam shortcut THROUGH Steam (theater + its Steam Input layout), for desktop/"+" menu entries.
#   launch-via-steam.sh <shortcut appid>      e.g. 3434073834 (see scripts/steam-shortcuts.py list)
# gameid = appid<<32 | 0x02000000 (verified against Steam's console_log). A direct "steam steam://..." Exec line
# is hidden from the Frame's multitasking "+" menu, so .desktop entries call this script instead.
APPID="$1"
GAMEID=$(python3 -I -c "import sys; print((int(sys.argv[1]) << 32) | 0x02000000)" "$APPID")   # bash math overflows (signed 64-bit)
exec steam "steam://rungameid/$GAMEID"
