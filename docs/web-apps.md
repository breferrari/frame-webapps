# Web apps with controller support on the Steam Frame

How a `frame-webapp` app works, what the tool does for you, how to troubleshoot, and what we tried that did **not**
work and why. Worked out on a Steam Frame with SteamOS 0.5.10, SteamVR 2.19.4 and Flathub Chromium 158 (November 2026),
first for Crunchyroll.

## TL;DR

A web app = **Flatpak Chromium in app mode** + its **own profile** + a **gamepad layout in Steam** + the
**frame-gamepad extension**, which reads the controller *inside the page* through the Gamepad API.
**Always launch it from the Steam library**, never from the multitasking "+" menu.

## How it works

```
Steam library → Play
  └─ apps/<Name>                              (generated launcher: name in Steam = filename)
      └─ webapps/_chromium-webapp.sh          (shared launcher)
          └─ flatpak run --filesystem=/run/udev:ro org.chromium.Chromium
                 --app=<URL> --start-fullscreen --user-data-dir=…/webapp-<Class> --load-extension=extensions/frame-gamepad
                 └─ extensions/frame-gamepad/frame-gamepad.js   (content script: polls navigator.getGamepads())

Steam Input (a new shortcut gets Steam's generic gamepad layout)
  └─ virtual "Microsoft X-Box 360 pad 0" (/dev/input/js1)  ──►  Gamepad API inside the page  ──►  scroll / focus / click / video
```

| Piece | Where | Why it's needed |
|---|---|---|
| App launcher | `apps/<Name>` | Written by `frame-webapp add`. The **filename is the Steam name**. Sets `WEBAPP_EXTENSIONS=frame-gamepad` (or, in TV mode, `WEBAPP_EXTENSIONS=frame-gamepad-tv WEBAPP_TV=1`) and calls the shared launcher with `<WindowClass> <URL>` |
| Shared launcher | `webapps/_chromium-webapp.sh` | Per-app profile, Widevine seeding, stale-lock cleanup, udev access, loads extensions, writes logs |
| Per-app profile | `~/.var/app/org.chromium.Chromium/config/webapp-<Class>/` | Flatpak Chromium instances can't hand over to each other (private `/tmp`), so a shared profile gives "Profile error occurred". Separate profiles run side by side. Sign in once per app |
| Widevine (DRM) | copied from `…/config/chromium/WidevineCdm` on first run | Netflix, Crunchyroll etc. need it. Chromium re-registers the copy automatically |
| `--filesystem=/run/udev:ro` | launcher | Chromium's Linux gamepad backend needs the udev database (`ID_INPUT_JOYSTICK`), which the Flatpak sandbox lacks. Without it the Gamepad API sees no controller |
| frame-gamepad-tv extension | `webapps/extensions/frame-gamepad-tv/` | TV mode only: turns the controller into remote-control keys (arrows, Enter, Escape, media keys) for TV interfaces such as `youtube.com/tv`. Its log lines start with `[frame-gamepad-tv]` |
| frame-gamepad extension | `webapps/extensions/frame-gamepad/` | Reads the controller in the page and acts on the DOM and `<video>` directly. MV3 content script, no permissions, no network |
| Gamepad layout in Steam | Steam's default for a new shortcut (`controller_generic_gamepad_joystick.vdf`) | Steam only feeds the virtual Xbox pad when the app has a **gamepad** layout. Key/mouse layouts never reach a Flatpak window (see below). If you changed an app's layout, switch it back to a Gamepad template |
| Stale-lock cleanup | launcher + `frame-webapps-chromium-lock.service` | A session restart kills Chromium and leaves a lock (`frame-2`, PID 2 in the sandbox) that blocks the next start |
| Artwork and icon | `scripts/steam-art.py`, `scripts/steam-shortcuts.py`, `icons/` | Library art (gradient in the site's colour, with its icon and name) and the shortcut's `icon` field |
| Desktop entry | `~/.local/share/applications/frame-webapp-<name>.desktop` | Window icon (`StartupWMClass=<Class>`). Its Exec goes **through Steam** (`launch-via-steam.sh <appid>`) |

### Controls (frame-gamepad)

| Controller | Action |
|---|---|
| Sticks | Smooth scroll (either stick) |
| D-pad | Move focus (spatial, blue outline). In the player: ←/→ seek ±10 s, ↑/↓ volume |
| A | Click the focused item |
| B | Exit fullscreen → otherwise browser back |
| X | Play / pause |
| Y | Fullscreen the player |
| LB / RB | −10 s / +10 s |
| LT / RT | "Previous/next episode" or "Skip intro/credits" button if present, else −30 s / +30 s |

**Two modes (SteamVR, exclusive):** **gamepad mode** = everything above works. **Laser mode** = point and click,
and the pointing stick scrolls (laser scroll arrives as small wheel events, which the extension boosts ×6). **Tap grip** to switch.

## What `frame-webapp add` does

`frame-webapp add "Netflix" https://www.netflix.com` runs these steps (you can do them by hand to debug):

1. **Launcher:** writes `apps/Netflix`, a two-line script that calls `webapps/_chromium-webapp.sh NetflixWebApp <url>`
   with `WEBAPP_EXTENSIONS=frame-gamepad`.
2. **Icon and colour:** downloads the page, reads its icon links, web manifest and `theme-color`, and picks the largest
   usable icon (PNG, JPEG, SVG or ICO). With no theme colour it takes the icon's dominant colour. Sites that block
   automated requests get a plain tile; pass `--icon` and `--color` to choose your own.
3. **Adds it to Steam, live:** `SteamClient.Apps.AddShortcut(...)` through Steam's local interface (see below), which
   returns the new appid.
4. **Artwork:** `scripts/steam-art.py` renders cover, wide, hero, logo and icon into `userdata/<id>/config/grid/`, and
   `SetCustomArtworkForApp` makes the running Steam show them.
5. **Shortcut icon:** `SetShortcutIcon`, live.
6. **Desktop entry:** `~/.local/share/applications/frame-webapp-netflix.desktop` with `StartupWMClass=NetflixWebApp`
   (window icon) and `Exec=…/launch-via-steam.sh <appid>`.

No controller layout step is needed: a new shortcut already gets Steam's gamepad layout.

With `--controller native` the launcher is written without `WEBAPP_EXTENSIONS=frame-gamepad`. The page then reads the
virtual Xbox pad itself through the Gamepad API (still thanks to the gamepad layout and the udev access), which is what
game streaming sites expect. The navigation extension would otherwise scroll and press "back" during play.

`frame-webapp remove` deletes the launcher, desktop entry, icon, artwork and (unless `--keep-data`) the Chromium
profile, and removes the shortcut with `RemoveShortcut`. If the app is open, it is closed first.

### Steam's local interface

Steam's interface is a web page, and on the Frame its debugging port listens on `127.0.0.1:8080`. `scripts/steamcef.py`
connects to the `SharedJSContext` page (Chrome DevTools protocol over a WebSocket, standard library only) and calls the
functions the interface itself uses: `SteamClient.Apps.AddShortcut`, `RemoveShortcut`, `SetShortcutIcon` and
`SetCustomArtworkForApp(appid, base64, "png"|"jpg", type)` with type 0 = cover, 1 = hero, 2 = logo, 3 = wide.
That is why nothing needs a Steam restart. Steam has to be running: if the port isn't reachable, `add` and `remove`
stop with a message and change nothing.

Editing Steam's files instead doesn't work while Steam runs: it rewrites `shortcuts.vdf` and its controller configs
from memory when it exits. `steamos-add-to-steam` can add a shortcut to a running Steam, but artwork and icons would
then only show after a restart, and `SetShortcutIcon` did not load the image on a shortcut added that way.

## The Web Apps manager

`frame-webapp manager` (the "Web Apps" entry in Steam) starts a small HTTP server inside the same process and shows
`manager/index.html` in the usual Chromium app-mode setup, with the `frame-gamepad` extension, so the page is driven
with the D-pad and A like any other web app. It calls the same code as `add` and `remove`.

- The server binds to `127.0.0.1` on a free port and stops when the window closes.
- Every API request needs a token created at launch (passed to the page in its address) and the right `Host` and
  `Origin`, so other pages in a browser and other devices on the network can't use it.
- On first launch it runs `frame-webapp setup` if the command or the background unit is missing, so any way of
  getting the files onto the Frame ends in the same state.
- `manager/catalogue.json` lists the known sites (name, address, colour, `"controller": "native"` where needed, and
  `"tv": "<address>"` for a site with a TV interface).
- **TV mode.** An app whose site has a TV interface keeps both addresses in its launcher (`# site-url:`, `# tv-url:`).
  `frame-webapp tv "Name" on|off` and the manager's TV mode button rewrite the launcher for one or the other; the
  Steam entry, artwork and profile stay. In TV mode the shared launcher adds a TV user agent (`WEBAPP_TV=1`).
- **Extensions.** `frame-webapp extensions "Name"` opens the app's profile as a normal Chromium window (window class
  `FrameWebAppsStore`) on the Chrome Web Store. The app's launcher closes such a window if it is still open, because
  two Chromium instances can't share a profile.
- **Updates.** On opening, the manager runs `git fetch` in the background and compares `VERSION` in
  `bin/frame-webapp` with the one on GitHub. "Update now" runs `git pull --ff-only` and `frame-webapp setup`, then
  the manager starts again in the same process as the new version. Installs without git don't check.

## Troubleshooting

| Symptom | Look at | Likely cause |
|---|---|---|
| No controller at all, only the laser | `~/.local/share/Steam/logs/console_log.txt`: "Loaded Config … App ID <appid>" | Launched from "+" (desktop app → no gamepad layout), or the layout isn't a gamepad template |
| Controller ignored | `logs/<Class>-chromium.log` in the install folder: `[frame-gamepad] … loaded` and `… pad …` lines | No `loaded` = extension not loaded. `loaded` but no `pad` line after pressing a button = the Gamepad API sees no controller (udev flag, layout). Set `DEBUG = true` in `frame-gamepad.js` to log every press |
| Buttons work, pointing stick doesn't scroll | same log with `DEBUG`, look for `wheel` lines | Controller is in gamepad mode: tap grip for laser mode, or scroll with either stick in gamepad mode |
| "Profile error occurred" ×N | `flatpak ps` | Two Chromiums on one profile. Use per-app profiles; close strays |
| "Profile in use" after a restart | `…/webapp-<Class>/SingletonLock` | Stale lock. Cleared automatically at session start and app start |
| Video won't play | Chromium log ("robustness", EME errors) | Widevine. Check `…/webapp-<Class>/WidevineCdm/latest-component-updated-widevine-cdm` points into the profile |
| Black square / "?" icon | `scripts/steam-shortcuts.py` | Empty `icon` field, or a window that doesn't match its `.desktop` `StartupWMClass` |

## What did NOT work (and why), so nobody repeats it

1. **Steam Input templates on the web app** (Web Browser, WASD+mouse, edited layouts): replacing the layout lost the pointer, and
   the keys/wheel never reached the page.
2. **"Disable Steam Input"**: not possible. Steam always enables Steam Input for Steam-made controllers, the Frame's included (read from Steam's UI code).
3. **Empty layout like the desktop's** (`controller_base/empty.vdf`): the desktop's stick scrolling comes from SteamVR's *desktop view*.
   Apps in theater don't get it.
4. **Keys/wheel layout + forcing Chromium to X11** (`--ozone-platform=x11`): still nothing. Steam links windows to apps via the X11
   property `STEAM_GAME`, normally set by its overlay library (`LD_PRELOAD`), which the **Flatpak sandbox blocks**. Steam then gives the
   untagged window a fallback generic-gamepad layout (seen as **App 5095552** in console_log).
5. **Tagging the window ourselves** with `xprop -set STEAM_GAME`: Steam doesn't pass `SteamAppId`/`SteamGameId` to the launcher, so
   there was no ID to set (and the window wasn't where expected).
6. **An Electron wrapper**: stock Electron has **no Widevine**, so DRM sites fail.
7. **Laser-hand stick scroll in theater**: SteamVR binds it (`vrcompositor_bindings_frame_controller.json` → `scroll`), but for app
   panels it rarely reaches the app (SteamVR-for-Linux #1000). No setting forwards it.
8. **"+" (multitasking) menu entries that launch through Steam**: hidden. That menu lists desktop apps only.

**Key insight:** don't rely on Steam delivering input to the window. Read the controller
*inside* the app (Gamepad API) and act there. Steam reliably feeds the virtual Xbox pad when the app has a gamepad layout.

## References
- FrameTube (YouTube TV app for the Frame, MIT), which inspired the in-page gamepad approach: https://github.com/coah80/frametube
- Community notes: https://github.com/coah80/steam-frame-gamepad-mode · https://github.com/lostpanda85/frame-docs
- Valve: https://partner.steamgames.com/doc/steamhardware/steamframe/input · SteamVR-for-Linux issues #1000, #1009
