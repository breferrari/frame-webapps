#!/usr/bin/env python3
"""List Steam's non-Steam shortcuts (binary userdata/<id>/config/shortcuts.vdf).

  steam-shortcuts.py            tab-separated: appid, name, exe, icon

Read-only. Changes go through the running Steam (see steamcef.py), which then rewrites this file itself.
"""
import os, struct

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


def field(entry, key):
    for item in entry:
        if item[1].lower() == key.lower():
            return item[2]
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


def main():
    for _, _, root in files():
        for _, _, e in root:
            print("\t".join(str(field(e, k) or "") for k in ("appid", "AppName", "Exe", "icon")))


if __name__ == "__main__":
    main()
