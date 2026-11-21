#!/usr/bin/env python3
"""Talk to the running Steam client through its local debugging port, to change the library without a restart.

Steam's interface is a web page; on the Steam Frame its debugging port listens on 127.0.0.1:8080. Through it we call
the same functions the interface itself uses (SteamClient.Apps.AddShortcut, RemoveShortcut, SetShortcutIcon,
SetCustomArtworkForApp). When the port isn't reachable, callers fall back to editing files before Steam's next start.

  steamcef.py available
  steamcef.py eval "<javascript>"

Only the standard library is used: a minimal WebSocket client for the Chrome DevTools protocol.
"""
import base64, json, os, socket, struct, sys, urllib.request
from pathlib import Path

PORT = 8080
ART_KINDS = {"cover": 0, "hero": 1, "logo": 2, "wide": 3}   # eAssetType values of SetCustomArtworkForApp


class SteamUnavailable(Exception):
    pass


def _target():
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=3) as r:
            targets = json.load(r)
    except (OSError, ValueError) as e:
        raise SteamUnavailable(f"Steam's interface isn't reachable: {e}") from None
    for t in targets:
        if t.get("title") == "SharedJSContext" and t.get("webSocketDebuggerUrl"):
            return t["webSocketDebuggerUrl"].split(f":{PORT}", 1)[1]
    raise SteamUnavailable("Steam's interface isn't ready yet.")


def available():
    try:
        _target()
        return True
    except SteamUnavailable:
        return False


def steam_eval(expression, timeout=20):
    """Evaluate JavaScript in Steam's shared context and return its value (promises are awaited)."""
    path = _target()
    try:
        s = socket.create_connection(("127.0.0.1", PORT), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        s.sendall((f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{PORT}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                   f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = s.recv(4096)
            if not chunk:
                raise SteamUnavailable("Steam closed the connection.")
            buf += chunk
        if b" 101 " not in buf.split(b"\r\n", 1)[0]:
            raise SteamUnavailable("Steam refused the connection.")
        buf = buf.split(b"\r\n\r\n", 1)[1]

        msg = json.dumps({"id": 1, "method": "Runtime.evaluate",
                          "params": {"expression": expression, "returnByValue": True, "awaitPromise": True}}).encode()
        n, mask = len(msg), os.urandom(4)
        head = b"\x81" + (bytes([0x80 | n]) if n < 126 else b"\xfe" + struct.pack(">H", n) if n < 65536
                          else b"\xff" + struct.pack(">Q", n))
        masked = bytes(a ^ b for a, b in zip(msg, mask * (n // 4 + 1)))
        s.sendall(head + mask + masked)

        def need(count):
            nonlocal buf
            while len(buf) < count:
                chunk = s.recv(65536)
                if not chunk:
                    raise SteamUnavailable("Steam closed the connection.")
                buf += chunk
            out, buf = buf[:count], buf[count:]
            return out

        text = b""
        while True:
            b0, b1 = need(2)
            size = b1 & 0x7f
            if size == 126:
                size = struct.unpack(">H", need(2))[0]
            elif size == 127:
                size = struct.unpack(">Q", need(8))[0]
            payload = need(size)
            if b0 & 0x0f in (0, 1):   # text frame or its continuation
                text += payload
                if b0 & 0x80:
                    reply, text = json.loads(text), b""
                    if reply.get("id") == 1:
                        result = reply.get("result", {})
                        if "exceptionDetails" in result:
                            detail = result["exceptionDetails"].get("exception", {}).get("description", "error")
                            raise SteamUnavailable(f"Steam reported an error: {detail.splitlines()[0]}")
                        return result.get("result", {}).get("value")
    except (OSError, ValueError, struct.error) as e:
        raise SteamUnavailable(f"Talking to Steam failed: {e}") from None
    finally:
        try:
            s.close()
        except Exception:
            pass


def _call(function, *args):
    return steam_eval(f"SteamClient.Apps.{function}({', '.join(json.dumps(a) for a in args)})")


def add_shortcut(name, exe):
    """Add a non-Steam shortcut and return its appid."""
    appid = _call("AddShortcut", name, str(exe), str(Path(exe).parent), "")
    if not isinstance(appid, int):
        raise SteamUnavailable("Steam didn't return an app id for the new shortcut.")
    _call("SetShortcutName", appid, name)   # AddShortcut may derive the name from the file; make sure it is ours
    return appid


def remove_shortcut(appid):
    _call("RemoveShortcut", int(appid))


def set_icon(appid, path):
    _call("SetShortcutIcon", int(appid), str(path))


def set_artwork(appid, path, kind):
    """Show an image as the app's artwork right away. kind: cover, wide, hero or logo. PNG or JPEG."""
    data = Path(path).read_bytes()
    fmt = "png" if data[:4] == b"\x89PNG" else "jpg"
    _call("SetCustomArtworkForApp", int(appid), base64.b64encode(data).decode(), fmt, ART_KINDS[kind])


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "available":
        print("yes" if available() else "no")
    elif len(sys.argv) == 3 and sys.argv[1] == "eval":
        try:
            print(json.dumps(steam_eval(sys.argv[2]), indent=1))
        except SteamUnavailable as e:
            sys.exit(str(e))
    else:
        sys.exit(__doc__)
