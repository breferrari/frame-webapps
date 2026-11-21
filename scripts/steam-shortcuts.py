#!/usr/bin/env python3
"""Read/edit Steam non-Steam shortcuts (binary userdata/<id>/config/shortcuts.vdf).

  steam-shortcuts.py list                                     (safe any time; tab-separated: appid, name, exe, icon)
  steam-shortcuts.py set-icon "<App name>" /path/icon.png     (Steam must NOT be running)
  steam-shortcuts.py rename "<old name>" "<new name>"        (Steam must NOT be running)
  steam-shortcuts.py remove-exe /path/to/launcher            (Steam must NOT be running)

Steam reads shortcuts.vdf only at startup and rewrites it on exit, so edits are refused while Steam runs.
Queue them instead in the pending/ folder (applied by apply-pending-steam.sh just before Steam's next start).
The parser round-trips byte-identically.
"""
import os, struct, subprocess, sys

BASE = os.path.expanduser("~/.local/share/Steam/userdata")


def parse(buf, i=0):
    out = []
    while True:
        t = buf[i]; i += 1
        if t == 0x08:
            return out, i
        j = buf.index(b"\0", i); key = buf[i:j].decode("utf-8", "replace"); i = j + 1
        if t == 0x00:
            val, i = parse(buf, i)
        elif t == 0x01:
            j = buf.index(b"\0", i); val = buf[i:j].decode("utf-8", "replace"); i = j + 1
        elif t == 0x02:
            val = struct.unpack_from("<I", buf, i)[0]; i += 4
        else:
            raise ValueError(f"unknown type {t:#x} at {i}")
        out.append([t, key, val])


def dump(items):
    b = bytearray()
    for t, k, v in items:
        b += bytes([t]) + k.encode() + b"\0"
        b += (dump(v) + b"\x08") if t == 0x00 else (v.encode() + b"\0") if t == 0x01 else struct.pack("<I", v)
    return bytes(b)


def field(entry, key, value=None, t=0x01):
    for item in entry:
        if item[1].lower() == key.lower():
            if value is not None:
                item[0], item[2] = t, value
            return item[2]
    if value is not None:
        entry.append([t, key, value])
    return None


def files():
    if not os.path.isdir(BASE):
        return
    for uid in sorted(os.listdir(BASE)):
        p = os.path.join(BASE, uid, "config", "shortcuts.vdf")
        if os.path.exists(p):
            d = open(p, "rb").read()
            j = d.index(b"\0", 1)
            root, _ = parse(d, j + 1)
            yield p, d[: j + 1], root


def steam_running():
    return subprocess.run(["pgrep", "-x", "steam"], capture_output=True).returncode == 0


def save(p, head, root):
    with open(p + ".bak", "wb") as bak:   # backup of the version before this edit
        bak.write(open(p, "rb").read())
    tmp = p + ".tmp"
    open(tmp, "wb").write(head + dump(root) + b"\x08\x08")
    os.replace(tmp, p)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "list":
        for p, _, root in files():
            for _, _, e in root:
                print("\t".join(str(field(e, k) or "") for k in ("appid", "AppName", "Exe", "icon")))
        return
    if cmd not in ("set-icon", "rename", "remove-exe"):
        sys.exit(__doc__)
    if steam_running():
        sys.exit("Steam is running; refusing (it would overwrite shortcuts.vdf). Queue the change in the pending/ folder.")
    if cmd == "set-icon":
        name, icon = sys.argv[2], os.path.abspath(sys.argv[3])
        if not os.path.exists(icon):
            sys.exit(f"no such icon: {icon}")
        for p, head, root in files():
            hit = [e for _, _, e in root if (field(e, "AppName") or "").lower() == name.lower()]
            if hit:
                for e in hit:
                    field(e, "icon", icon)
                save(p, head, root)
                print(f"icon set for {name!r}: {icon}")
                return
        sys.exit(f"no shortcut named {name!r}")
    if cmd == "rename":   # appid, art and icon are kept: they're keyed by appid
        old, new = sys.argv[2], sys.argv[3]
        for p, head, root in files():
            hit = [e for _, _, e in root if (field(e, "AppName") or "").lower() == old.lower()]
            if hit:
                for e in hit:
                    field(e, "AppName", new)
                save(p, head, root)
                print(f"renamed {old!r} -> {new!r}")
                return
        print(f"no shortcut named {old!r} (already renamed?)")
        return
    if cmd == "remove-exe":   # remove the shortcut(s) whose Exe is this launcher; fine if it's already gone
        exe = sys.argv[2]
        for p, head, root in files():
            keep = [item for item in root if (field(item[2], "Exe") or "").strip('"') != exe]
            if len(keep) != len(root):
                for n, item in enumerate(keep):   # entries are keyed "0", "1", ...: renumber
                    item[1] = str(n)
                save(p, head, keep)
                print(f"removed shortcut for {exe}")
                return
        print(f"no shortcut for {exe} (already removed?)")


if __name__ == "__main__":
    main()
