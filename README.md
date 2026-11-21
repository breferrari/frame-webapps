# frame-webapps

Turn any website into a **Steam Frame app with controller support**: one command, and it's in your Steam library
with artwork, its own sign-in, and working sticks and buttons.

```bash
frame-webapp add "Netflix" https://www.netflix.com
```

Built and tested on a Steam Frame running SteamOS 0.5.10, SteamVR 2.19.4 and Flathub Chromium 158 (November 2026).
Sites tried so far: Crunchyroll (DRM video).

## Install

On the Frame, in Desktop Mode, open Konsole and run:

```bash
curl -fsSL https://raw.githubusercontent.com/breferrari/frame-webapps/main/install.sh | bash
```

No password, nothing system-wide, nothing restarts. See [what it changes](#what-installsh-changes).

## Use

| | |
|---|---|
| Add an app | `frame-webapp add "Name" https://site.example` or **Add Web App** in the desktop menu (asks for the name and address) |
| List | `frame-webapp list` |
| New artwork | `frame-webapp art "Name" [--icon file.png] [--color "#e50914"]` |
| Remove | `frame-webapp remove "Name"` (add `--keep-data` to keep the sign-in) |
| Update the tool | `frame-webapp update` |

Then **open the app from the Steam library**. Two things to know:

- **Artwork and icon appear after the next Steam restart.** The app works right away.
- **Don't launch it from the multitasking "+" menu.** That menu starts desktop apps, which get the laser pointer only.

### Controls

| Controller | Action |
|---|---|
| Sticks | Smooth scroll |
| D-pad | Move focus between links and buttons (in a video player: ←/→ seek 10 s, ↑/↓ volume) |
| A / B / X / Y | Click / back / play-pause / fullscreen |
| LB / RB | −10 s / +10 s |
| LT / RT | Previous/next-episode or skip-intro button if the site has one, else −30 s / +30 s |
| Laser pointer | Still works: tap **grip** to switch between laser and gamepad mode |

## Why this exists

Open a streaming site as a Chromium "web app" from the Steam library and the Frame's controllers barely work: no stick
scrolling, no buttons. Steam can't link a **Flatpak** window to its shortcut, so whatever a Steam Input layout sends
(keys, mouse wheel) never reaches the page, and Steam Input can't be turned off for the Frame's controllers.

frame-webapps **reads the controller inside the page** instead:

1. A new shortcut gets Steam's gamepad layout, so Steam feeds a virtual Xbox pad.
2. Flatpak Chromium is allowed to see it (`--filesystem=/run/udev:ro`: its gamepad backend needs the udev database).
3. A small extension, [`frame-gamepad`](webapps/extensions/frame-gamepad), polls the Gamepad API and scrolls, moves
   focus, clicks and controls the `<video>`.

It runs in Flathub Chromium, so **Widevine DRM** keeps working and DRM sites play. Each app gets its own browser
profile, so apps run side by side and stay signed in separately from your normal Chromium.

[docs/web-apps.md](docs/web-apps.md) has the details: how it works, troubleshooting, and the approaches that did
*not* work (and why).

## Limits

- **Site quirks.** Scrolling, focus and video controls are generic and act on the page directly. Sites with unusual
  players or menus may need tweaks: please open an issue with the site's address.
- **Video quality** is whatever the site gives Linux browsers (often 720p for DRM services).
- **Icons.** Some sites block automated requests, so the tool can't fetch their icon and draws a plain tile.
  Pass your own with `--icon`.
- Made for the Steam Frame. Untested on other SteamOS devices.

## What install.sh changes

Everything lives in your home folder:

| Path | What |
|---|---|
| `~/.local/share/frame-webapps/` | The tool, your apps (`apps/`), icons, logs and queued changes (`pending/`) |
| `~/.local/bin/frame-webapp` | The command (a link) |
| `~/.local/share/applications/frame-webapps-add.desktop` | The "Add Web App" menu entry |
| `~/.config/systemd/user/frame-webapps-chromium-lock.service` | At session start, clears a stale Chromium profile lock left by a restart |
| `~/.config/systemd/user/steam.service.d/frame-webapps-pending.conf` | Just before Steam starts, applies queued shortcut edits (icons, removals). Steam overwrites those files when it exits, so they can only be edited while it's stopped. Does nothing when the queue is empty |

Each app also gets a Chromium profile in `~/.var/app/org.chromium.Chromium/config/webapp-<Name>WebApp/` and a
`frame-webapp-<name>.desktop` entry (for its window icon).

**Uninstall:** remove your apps with `frame-webapp remove`, then:

```bash
systemctl --user disable frame-webapps-chromium-lock.service
rm -rf ~/.local/share/frame-webapps ~/.local/bin/frame-webapp \
       ~/.local/share/applications/frame-webapps-add.desktop \
       ~/.config/systemd/user/frame-webapps-chromium-lock.service \
       ~/.config/systemd/user/steam.service.d/frame-webapps-pending.conf
```

## What's inside

| Path | What |
|---|---|
| `bin/frame-webapp` | The command: add, list, art, remove, gui, update |
| `webapps/_chromium-webapp.sh` | Launcher: Chromium app mode, one profile per app, Widevine, stale-lock fix, udev access, extension, logs |
| `webapps/extensions/frame-gamepad/` | The controller extension (MV3 content script, no permissions, no network) |
| `webapps/launch-via-steam.sh` | Starts a shortcut *through* Steam from a `.desktop` file |
| `scripts/steam-shortcuts.py` | Lists shortcuts; sets icons, renames, removes (edits the binary `shortcuts.vdf`, refuses while Steam runs) |
| `scripts/steam-art.py` | Renders library artwork (cover, wide, hero, logo, icon) with `rsvg-convert` |
| `scripts/apply-controller-layout.py` | Assigns a layout file or Steam template to shortcuts (for repairs: new shortcuts don't need it) |
| `scripts/apply-pending-steam.sh`, `systemd/` | The queue applied before Steam starts, and the lock cleanup |

Not affiliated with Valve or any of the sites you add. Use at your own risk.

## Credits

- [coah80/frametube](https://github.com/coah80/frametube) (MIT), a YouTube TV app for the Frame, inspired the in-page gamepad approach
- [coah80/steam-frame-gamepad-mode](https://github.com/coah80/steam-frame-gamepad-mode) and
  [lostpanda85/frame-docs](https://github.com/lostpanda85/frame-docs): community notes on Frame input

## License

MIT, see [LICENSE](LICENSE).
