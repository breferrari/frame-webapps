#!/usr/bin/env python3
"""Give non-Steam shortcuts a specific Steam Input layout for the Steam Frame controllers (SteamFrameVirtual).

  apply-controller-layout.py <layout.vdf> <app folder name> [<app folder name> ...]     (Steam must NOT be running)
  apply-controller-layout.py --template=<template.vdf> <app> [<app> ...]                (use one of Steam's templates,
        e.g. controller_switch_pro_gamepad_joystick.vdf from controller_base/templates/, instead of a custom file)

The app folder name is Steam's lowercase shortcut name (e.g. "youtube", "crunchyroll"). For each app:
  - copies <layout.vdf> to  Steam Controller Configs/<account>/config/<app>/SteamFrameVirtual.vdf  (old file -> .bak-<date>)
  - sets "<app>" { "autosave" "1" } in configset_SteamFrameVirtual.vdf, so Steam uses that file.
Steam keeps these in memory and rewrites them on exit, so run this before Steam starts (apply-pending-steam.sh does that).
"""
import glob, os, re, shutil, subprocess, sys, time

if subprocess.run(["pgrep", "-x", "steam"], capture_output=True).returncode == 0:
    sys.exit("Steam is running; refusing (it would overwrite the controller config). Queue it in the pending/ folder/")
layout, apps = sys.argv[1], [a.lower() for a in sys.argv[2:]]
template = layout[len("--template="):] if layout.startswith("--template=") else None
if template and not os.path.exists(os.path.expanduser(f"~/.local/share/Steam/controller_base/templates/{template}")):
    sys.exit(f"no such Steam template: {template}")
stamp = time.strftime("%Y%m%d-%H%M%S")
for cfg in glob.glob(os.path.expanduser("~/.local/share/Steam/steamapps/common/Steam Controller Configs/*/config")):
    cset = os.path.join(cfg, "configset_SteamFrameVirtual.vdf")
    text = open(cset).read() if os.path.exists(cset) else '"controller_config"\n{\n}\n'
    shutil.copy2(cset, f"{cset}.bak-{stamp}") if os.path.exists(cset) else None
    for app in apps:
        d = os.path.join(cfg, app); os.makedirs(d, exist_ok=True)
        dst = os.path.join(d, "SteamFrameVirtual.vdf")
        if os.path.exists(dst):
            shutil.copy2(dst, f"{dst}.bak-{stamp}")
            if template:
                os.remove(dst)   # so Steam uses the template, not an old autosave
        if template:
            entry = f'\t"{app}"\n\t{{\n\t\t"template"\t\t"{template}"\n\t}}\n'
        else:
            shutil.copy2(layout, dst)
            entry = f'\t"{app}"\n\t{{\n\t\t"autosave"\t\t"1"\n\t}}\n'
        # replace or add the app's entry in the configset
        pat = re.compile(r'\t"%s"\s*\{[^{}]*\}\n' % re.escape(app), re.I)
        if pat.search(text):
            text = pat.sub(entry, text, count=1)
        else:
            text = text.rstrip().rstrip("}") + entry + "}\n"
        print(f"layout for {app!r}: {'template ' + template if template else dst}")
    open(cset, "w").write(text)
    print("configset updated:", cset)
