#!/usr/bin/env python3
"""Fetch library artwork from SteamGridDB (https://www.steamgriddb.com) with your own API key.

  steamgriddb.py search "Netflix"                 list matching entries (id, name)
  steamgriddb.py fetch <game id> <appid> <grid>   download cover, wide, hero, logo and icon into a Steam grid folder

The key comes from $STEAMGRIDDB_KEY or ~/.config/frame-webapps/steamgriddb-key (see `frame-webapp key`).
Get a free key at https://www.steamgriddb.com/profile/preferences (sign in, then the API section). It is never written to logs.
Endpoints and parameters follow SteamGridDB's OpenAPI description (https://www.steamgriddb.com/static/openapi.yml).
"""
import json, os, re, sys, urllib.error, urllib.parse, urllib.request
from pathlib import Path

API = "https://www.steamgriddb.com/api/v2"
KEY_FILE = Path.home() / ".config/frame-webapps/steamgriddb-key"
MAX_BYTES = 20_000_000

# What to ask for per kind of artwork, and the file name Steam expects in userdata/<id>/config/grid/.
KINDS = {
    "cover": ("/grids/game/{id}",  {"dimensions": "600x900,660x930,342x482", "mimes": "image/png,image/jpeg"}, "{appid}p"),
    "wide":  ("/grids/game/{id}",  {"dimensions": "920x430,460x215", "mimes": "image/png,image/jpeg"}, "{appid}"),
    "hero":  ("/heroes/game/{id}", {"mimes": "image/png,image/jpeg"}, "{appid}_hero"),
    "logo":  ("/logos/game/{id}",  {"mimes": "image/png"}, "{appid}_logo"),
    "icon":  ("/icons/game/{id}",  {"mimes": "image/png"}, "{appid}_icon"),
}


class SGDBError(Exception):
    pass


def load_key():
    key = os.environ.get("STEAMGRIDDB_KEY", "").strip()
    if not key and KEY_FILE.is_file():
        key = KEY_FILE.read_text().strip()
    return key or None


def api(path, key, params=None):
    url = API + path + ("?" + urllib.parse.urlencode(params, safe=",/") if params else "")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}", "User-Agent": "frame-webapps",
                                               "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            body = json.loads(r.read(5_000_000))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise SGDBError("SteamGridDB rejected the API key. Check it with:  frame-webapp key") from None
        if e.code == 404:
            return []
        if e.code == 429:
            raise SGDBError("SteamGridDB says too many requests. Try again in a minute.") from None
        raise SGDBError(f"SteamGridDB answered with an error ({e.code}).") from None
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise SGDBError(f"Couldn't reach SteamGridDB: {e}") from None
    if not isinstance(body, dict) or not body.get("success"):
        return []
    return body.get("data") or []


def search(term, key):
    """Entries matching a name: [{'id': 123, 'name': 'Netflix', 'verified': True, ...}, ...]."""
    return [g for g in api("/search/autocomplete/" + urllib.parse.quote(term, safe=""), key)
            if isinstance(g, dict) and "id" in g]


def pick_game(name, games):
    """The entry whose name is the same as ours (ignoring case and punctuation), verified ones first. None if unsure."""
    norm = lambda s: re.sub(r"[^a-z0-9]", "", str(s).lower())
    same = [g for g in games if norm(g.get("name")) == norm(name)]
    same.sort(key=lambda g: not g.get("verified"))
    return same[0] if same else None


def image_ext(data):
    if data[:4] == b"\x89PNG":
        return "png"
    if data[:2] == b"\xff\xd8":
        return "jpg"
    return None


def fetch_art(game_id, appid, grid_dir, key, kinds=None):
    """Download the best-scored image of each kind into grid_dir. Returns {kind: path} for what was saved."""
    grid_dir = Path(grid_dir)
    grid_dir.mkdir(parents=True, exist_ok=True)
    saved = {}
    for kind, (path, params, name) in KINDS.items():
        if kinds and kind not in kinds:
            continue
        items = api(path.format(id=int(game_id)), key, {**params, "types": "static", "nsfw": "false", "humor": "false"})
        items = [i for i in items if isinstance(i, dict) and str(i.get("url", "")).startswith("https://")]
        if kind == "icon":   # the largest icon, then the best-scored
            items.sort(key=lambda i: (-(i.get("width") or 0), -(i.get("score") or 0)))
        else:
            items.sort(key=lambda i: -(i.get("score") or 0))
        for item in items[:3]:   # a few tries in case a download fails or isn't an image we can use
            try:
                req = urllib.request.Request(item["url"], headers={"User-Agent": "frame-webapps"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    data = r.read(MAX_BYTES + 1)
            except (urllib.error.URLError, OSError):
                continue
            ext = image_ext(data)
            if not ext or len(data) > MAX_BYTES:
                continue
            base = name.format(appid=appid)
            for old in ("png", "jpg", "jpeg"):   # Steam must not find two files for the same slot
                f = grid_dir / f"{base}.{old}"
                if f.exists():
                    f.unlink()
            out = grid_dir / f"{base}.{ext}"
            out.write_bytes(data)
            saved[kind] = out
            break
    return saved


def main():
    key = load_key()
    if not key:
        sys.exit("No SteamGridDB key. Set one with:  frame-webapp key <key>")
    try:
        if len(sys.argv) == 3 and sys.argv[1] == "search":
            for g in search(sys.argv[2], key):
                print(f"{g['id']}\t{g.get('name', '')}{'  (verified)' if g.get('verified') else ''}")
        elif len(sys.argv) == 5 and sys.argv[1] == "fetch":
            for kind, path in fetch_art(sys.argv[2], sys.argv[3], sys.argv[4], key).items():
                print(f"{kind}: {path}")
        else:
            sys.exit(__doc__)
    except SGDBError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
