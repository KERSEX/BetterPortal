# BetterPortal - komfortable Skylanders-Verwaltung fuer RPCS3
# Start: python main.py  (oder start.bat)
import itertools
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import threading
import webbrowser
import winsound
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

import rpcs3_inject as inj
from meta import DB, GAMES, SWAPPERS, ELEMENTS, display_name
from sky_file import create_sky_bytes, parse_sky

BASE_DIR = Path(__file__).resolve().parent
LIB_DIR = BASE_DIR / "Bibliothek"
PORTAL_DIR = BASE_DIR / "Portal"
LOADOUTS_FILE = BASE_DIR / "loadouts.json"
STATE_FILE = BASE_DIR / "portal_state.json"
HOTSWAP_FILE = BASE_DIR / "hotswap.json"
SETTINGS_FILE = BASE_DIR / "settings.json"
DEFAULT_MODIFIER = "ctrl+shift"  # Hotkeys: Strg+Shift+F1..F9 (aenderbar in hotswap.json)

_inject_lock = threading.Lock()  # nur eine UI-Automation zur Zeit
_busy_lock = threading.Lock()
_inject_active = 0  # laufende/wartende Injektionen (fuer die Blink-Anzeige)

NUM_SLOTS = 8  # wie RPCS3s Skylanders-Manager
SKY_EXTS = {".sky", ".bin", ".dmp", ".dump"}
SLOT_RE = re.compile(r"^(\d{2}) - .*$")

ENTRY_BY_KEY = {(e["id"], e["var"]): e for e in DB}

app = Flask(__name__)


class ApiError(Exception):
    pass


@app.errorhandler(ApiError)
def _api_error(err):
    return jsonify({"ok": False, "error": str(err)}), 400


def _ensure_dirs():
    LIB_DIR.mkdir(exist_ok=True)
    PORTAL_DIR.mkdir(exist_ok=True)


def _sanitize(name):
    return re.sub(r'[<>:"/\\|?*]', "", name).strip()


def _load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _save_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# Bekannte Sammlung neben RPCS3 automatisch als Quelle anbieten
DEFAULT_EXTRA_LIBRARY = Path(r"D:\Programme\Emulatoren\ps3\SkylandersFigures")


def _lib_sources():
    """Alle Bibliotheks-Quellen: (relpath-Praefix, Wurzelordner, Anzeigename)."""
    sources = [("", LIB_DIR, "")]
    for i, p in enumerate(_settings().get("extra_libraries", []), start=1):
        root = Path(p)
        sources.append((f"@{i}:", root, root.name))
    return sources


def _lib_path(relpath):
    """Relativen Bibliothekspfad sicher aufloesen (kein Ausbruch aus der Quelle)."""
    for prefix, root, _label in _lib_sources():
        if prefix and relpath.startswith(prefix):
            p = (root / relpath[len(prefix):]).resolve()
            if not str(p).startswith(str(root.resolve())):
                raise ApiError("Ungueltiger Pfad.")
            return p
    p = (LIB_DIR / relpath).resolve()
    if not str(p).startswith(str(LIB_DIR.resolve())):
        raise ApiError("Ungueltiger Pfad.")
    return p


def _file_info(path, relpath):
    parsed = parse_sky(path)
    sky_id, sky_var = parsed if parsed else (None, None)
    entry = ENTRY_BY_KEY.get((sky_id, sky_var), {})
    return {
        "relpath": relpath,
        "filename": path.name,
        "folder": str(Path(relpath).parent) if str(Path(relpath).parent) != "." else "",
        "id": sky_id,
        "var": sky_var,
        "display": display_name(sky_id, sky_var) if parsed else path.stem,
        "element": entry.get("element"),
        "category": entry.get("category"),
        "mtime": path.stat().st_mtime,
    }


def _scan_library():
    _ensure_dirs()
    files = []
    for prefix, root, label in _lib_sources():
        if not root.exists():
            continue
        for p in sorted(root.rglob("*")):
            if not (p.is_file() and p.suffix.lower() in SKY_EXTS):
                continue
            rel = str(p.relative_to(root))
            info = _file_info(p, prefix + rel)
            folder = str(Path(rel).parent)
            folder = "" if folder == "." else folder
            if label:
                info["folder"] = f"{label} / {folder}" if folder else label
            else:
                info["folder"] = folder
            info["source"] = label or "Bibliothek"
            files.append(info)
    return files


def _find_in_library(sky_id, sky_var):
    """Vorhandene Bibliotheksdatei mit gleicher ID/Variante wiederverwenden (Spielstand!)."""
    for info in _scan_library():
        if info["id"] == sky_id and info["var"] == sky_var:
            return info
    return None


def _create_in_library(sky_id, sky_var):
    _ensure_dirs()
    entry = ENTRY_BY_KEY.get((sky_id, sky_var))
    folder = LIB_DIR / _sanitize(entry["game"]) if entry else LIB_DIR
    folder.mkdir(exist_ok=True)
    base = _sanitize(display_name(sky_id, sky_var))
    dest = folder / f"{base}.sky"
    n = 2
    while dest.exists():
        dest = folder / f"{base} ({n}).sky"
        n += 1
    dest.write_bytes(create_sky_bytes(sky_id, sky_var))
    return _file_info(dest, str(dest.relative_to(LIB_DIR)))


def _portal_state():
    return {int(k): v for k, v in _load_json(STATE_FILE, {}).items()}


def _set_portal_state(state):
    _save_json(STATE_FILE, {str(k): v for k, v in state.items()})


def _portal_files():
    """Slot -> Dateipfad im Portal-Ordner."""
    _ensure_dirs()
    slots = {}
    for p in PORTAL_DIR.iterdir():
        if p.is_file() and p.suffix.lower() in SKY_EXTS:
            m = SLOT_RE.match(p.stem)
            if m:
                slot = int(m.group(1)) - 1
                if 0 <= slot < NUM_SLOTS:
                    slots[slot] = p
    return slots


def _clear_slot(slot):
    files = _portal_files()
    if slot in files:
        try:
            os.remove(files[slot])
        except PermissionError:
            raise ApiError(
                f"Slot {slot + 1} ist gerade in RPCS3 geladen (Datei gesperrt). "
                "Erst im RPCS3-Portal 'Clear' druecken oder das Spiel schliessen."
            )
    state = _portal_state()
    state.pop(slot, None)
    _set_portal_state(state)


def _assign_slot(slot, lib_info):
    src = _lib_path(lib_info["relpath"])
    if not src.exists():
        raise ApiError(f"Bibliotheksdatei fehlt: {lib_info['relpath']}")
    _clear_slot(slot)
    dest = PORTAL_DIR / f"{slot + 1:02d} - {_sanitize(lib_info['display'])}.sky"
    try:
        os.link(src, dest)  # Hardlink: Portal & Bibliothek teilen sich die Datei
    except OSError:
        shutil.copy2(src, dest)
    state = _portal_state()
    state[slot] = {"relpath": lib_info["relpath"], "id": lib_info["id"], "var": lib_info["var"]}
    _set_portal_state(state)


def _free_slots():
    used = set(_portal_files().keys())
    return [s for s in range(NUM_SLOTS) if s not in used]


# ---- Platzierungs-Modi (Solo-Spieler-Schema mit festen Slots) ----
CAT_TOP = "Swapper (Oberteil)"
CAT_BOTTOM = "Swapper (Unterteil)"
ITEM_CATS = {"Falle", "Magisches Item", "Fahrzeug", "Abenteuer/Erweiterung", "Trophaee"}
ITEM_SLOT = 2  # Slot 3: geteilt fuer Fallen/Items/Fahrzeuge


def _slot_category(slot):
    """Kategorie der aktuell im Slot liegenden Figur (aus dem Portal-Status)."""
    st = _portal_state().get(slot)
    if not st or st.get("id") is None:
        return None
    entry = ENTRY_BY_KEY.get((st["id"], st["var"]))
    return entry.get("category") if entry else None


def _auto_place(info):
    """Zielslot nach Platzierungs-Modus bestimmen.
    Gibt (slot, extra_clears) zurueck - extra_clears = Slots, die mitgeleert werden
    (z. B. uebriges Unterteil, wenn eine normale Figur den Swapper ersetzt)."""
    mode = _settings().get("placement", "p1")
    if mode == "free":
        free = _free_slots()
        if not free:
            raise ApiError("Alle 8 Slots sind belegt - erst einen Slot leeren.")
        return free[0], []

    base = 0 if mode == "p1" else 3  # P1: Slots 1+2, P2: Slots 4+5
    cat = info.get("category") or ""
    if cat in ITEM_CATS:
        return ITEM_SLOT, []
    if cat == CAT_BOTTOM:
        return base + 1, []
    # Normale Figur oder Oberteil -> Spieler-Hauptslot
    extra = []
    if cat != CAT_TOP and _slot_category(base + 1) == CAT_BOTTOM:
        extra.append(base + 1)  # halber Swapper wuerde uebrig bleiben -> mitleeren
    return base, extra


def _place_figure(info):
    """Figur nach Modus platzieren, gibt (slot, aktionen fuer Auto-Inject) zurueck."""
    slot, extra = _auto_place(info)
    for s in extra:
        _clear_slot(s)
    _assign_slot(slot, info)
    actions = [("clear", s) for s in extra]
    act = _load_action(slot)
    if act:
        actions.append(act)
    return slot, actions


def _portal_slots():
    files = _portal_files()
    state = _portal_state()
    slots = []
    for i in range(NUM_SLOTS):
        if i in files:
            p = files[i]
            parsed = parse_sky(p)
            sky_id, sky_var = parsed if parsed else (None, None)
            entry = ENTRY_BY_KEY.get((sky_id, sky_var), {})
            slots.append({
                "slot": i,
                "filename": p.name,
                "id": sky_id,
                "var": sky_var,
                "display": display_name(sky_id, sky_var) if parsed else p.stem,
                "element": entry.get("element"),
                "category": entry.get("category"),
                "relpath": (state.get(i) or {}).get("relpath"),
            })
        else:
            slots.append(None)
    return slots


# ------------------------------------------------------------------ Routen

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/data")
def api_data():
    return jsonify({
        "games": GAMES,
        "elements": ELEMENTS,
        "figures": DB,
        "swappers": SWAPPERS,
        "paths": {"library": str(LIB_DIR), "portal": str(PORTAL_DIR)},
        "num_slots": NUM_SLOTS,
    })


@app.route("/api/library")
def api_library():
    sources = [{"path": str(root), "label": label or "Bibliothek", "removable": bool(prefix)}
               for prefix, root, label in _lib_sources()]
    return jsonify({"ok": True, "files": _scan_library(), "sources": sources})


@app.route("/api/library/sources", methods=["POST"])
def api_library_sources():
    d = request.get_json(force=True)
    s = _settings()
    extras = s.get("extra_libraries", [])
    if d.get("add"):
        p = Path(d["add"].strip().strip('"'))
        if not p.is_dir():
            raise ApiError(f"Ordner nicht gefunden: {p}")
        if str(p) not in extras and p.resolve() != LIB_DIR.resolve():
            extras.append(str(p))
    if d.get("remove"):
        extras = [e for e in extras if e != d["remove"]]
    s["extra_libraries"] = extras
    _set_settings(s)
    return jsonify({"ok": True})


@app.route("/api/library/create", methods=["POST"])
def api_library_create():
    d = request.get_json(force=True)
    info = _create_in_library(int(d["id"]), int(d["var"]))
    return jsonify({"ok": True, "file": info})


@app.route("/api/library/delete", methods=["POST"])
def api_library_delete():
    d = request.get_json(force=True)
    p = _lib_path(d["relpath"])
    if not p.exists():
        raise ApiError("Datei nicht gefunden.")
    try:
        os.remove(p)
    except PermissionError:
        raise ApiError("Datei ist gesperrt (evtl. in RPCS3 geladen).")
    return jsonify({"ok": True})


@app.route("/api/portal")
def api_portal():
    return jsonify({"ok": True, "slots": _portal_slots()})


@app.route("/api/portal/assign", methods=["POST"])
def api_portal_assign():
    d = request.get_json(force=True)
    p = _lib_path(d["relpath"])
    if not p.exists():
        raise ApiError("Bibliotheksdatei nicht gefunden.")
    info = _file_info(p, d["relpath"])
    slot = d.get("slot")
    if slot is None:
        slot, actions = _place_figure(info)
    else:
        _assign_slot(int(slot), info)
        actions = [a for a in [_load_action(int(slot))] if a]
    _auto_inject(actions)
    return jsonify({"ok": True, "slot": slot, "slots": _portal_slots()})


@app.route("/api/portal/create", methods=["POST"])
def api_portal_create():
    """Figur direkt ins Portal: vorhandene Bibliotheksdatei nutzen oder neu erstellen."""
    d = request.get_json(force=True)
    sky_id, sky_var = int(d["id"]), int(d["var"])
    info = _find_in_library(sky_id, sky_var) or _create_in_library(sky_id, sky_var)
    slot = d.get("slot")
    if slot is None:
        slot, actions = _place_figure(info)
    else:
        _assign_slot(int(slot), info)
        actions = [a for a in [_load_action(int(slot))] if a]
    _auto_inject(actions)
    return jsonify({"ok": True, "slot": slot, "slots": _portal_slots()})


@app.route("/api/portal/clear", methods=["POST"])
def api_portal_clear():
    d = request.get_json(force=True)
    slot = d.get("slot")
    if slot is None:
        cleared = list(_portal_files().keys())
        for s in cleared:
            _clear_slot(s)
        _auto_inject([("clear", s) for s in cleared])
    else:
        _clear_slot(int(slot))
        _auto_inject([("clear", int(slot))])
    return jsonify({"ok": True, "slots": _portal_slots()})


@app.route("/api/swapper", methods=["POST"])
def api_swapper():
    """Swapper-Kombi: Ober- und Unterteil erzeugen/wiederverwenden und in 2 Slots legen."""
    d = request.get_json(force=True)
    top = d["top"]
    bottom = d["bottom"]
    mode = _settings().get("placement", "p1")
    if mode == "free":
        free = _free_slots()
        if len(free) < 2:
            raise ApiError("Es werden 2 freie Slots gebraucht - erst Slots leeren.")
        targets = free[:2]
    else:
        base = 0 if mode == "p1" else 3
        targets = [base, base + 1]  # ueberschreibt die Spieler-Slots

    slots_used = []
    for part, slot in ((top, targets[0]), (bottom, targets[1])):
        sky_id, sky_var = int(part["id"]), int(part["var"])
        info = _find_in_library(sky_id, sky_var) or _create_in_library(sky_id, sky_var)
        _assign_slot(slot, info)
        slots_used.append(slot)

    _auto_inject([a for a in (_load_action(s) for s in slots_used) if a])
    return jsonify({"ok": True, "slots_used": slots_used, "slots": _portal_slots()})


@app.route("/api/loadouts", methods=["GET"])
def api_loadouts():
    return jsonify({"ok": True, "loadouts": _load_json(LOADOUTS_FILE, {})})


@app.route("/api/loadouts/save", methods=["POST"])
def api_loadouts_save():
    d = request.get_json(force=True)
    name = (d.get("name") or "").strip()
    if not name:
        raise ApiError("Name fehlt.")
    entries = []
    for s in _portal_slots():
        if s:
            entries.append({"slot": s["slot"], "relpath": s["relpath"],
                            "id": s["id"], "var": s["var"], "display": s["display"]})
    if not entries:
        raise ApiError("Das Portal ist leer - nichts zu speichern.")
    loadouts = _load_json(LOADOUTS_FILE, {})
    loadouts[name] = entries
    _save_json(LOADOUTS_FILE, loadouts)
    return jsonify({"ok": True, "loadouts": loadouts})


def _entry_info(e):
    """Loadout-/Hot-Swap-Eintrag zu einer Bibliotheksdatei aufloesen (notfalls neu erstellen)."""
    if e.get("relpath"):
        try:
            p = _lib_path(e["relpath"])
        except ApiError:
            p = None
        if p and p.exists():
            return _file_info(p, e["relpath"]), False
    if e.get("id") is not None:
        info = _find_in_library(e["id"], e["var"]) or _create_in_library(e["id"], e["var"])
        return info, True
    return None, False


def _apply_loadout(name, best_effort=False):
    """Portal auf ein Loadout umstellen. best_effort: gesperrte Slots ueberspringen."""
    entries = _load_json(LOADOUTS_FILE, {}).get(name)
    if entries is None:
        raise ApiError(f"Loadout '{name}' nicht gefunden.")
    blocked = []
    for s in list(_portal_files().keys()):
        try:
            _clear_slot(s)
        except ApiError:
            if not best_effort:
                raise
            blocked.append(s)
    recreated = []
    for e in entries:
        if e["slot"] in blocked:
            continue
        info, was_recreated = _entry_info(e)
        if info:
            if was_recreated:
                recreated.append(e.get("display") or "?")
            _assign_slot(e["slot"], info)
    return {"recreated": recreated, "blocked": [b + 1 for b in blocked]}


@app.route("/api/loadouts/apply", methods=["POST"])
def api_loadouts_apply():
    d = request.get_json(force=True)
    result = _apply_loadout(d.get("name"))
    _auto_inject(_sync_actions_full())
    return jsonify({"ok": True, "recreated": result["recreated"], "slots": _portal_slots()})


@app.route("/api/loadouts/delete", methods=["POST"])
def api_loadouts_delete():
    d = request.get_json(force=True)
    loadouts = _load_json(LOADOUTS_FILE, {})
    loadouts.pop(d.get("name"), None)
    _save_json(LOADOUTS_FILE, loadouts)
    return jsonify({"ok": True, "loadouts": loadouts})


# ------------------------------------------------------------------ Hot-Swap

_hotswap_seq = itertools.count(1)
_last_event = None  # letztes Hotkey-Ereignis fuer die Web-UI


def _hotswap_cfg():
    cfg = _load_json(HOTSWAP_FILE, {})
    cfg.setdefault("modifier", DEFAULT_MODIFIER)
    cfg.setdefault("bindings", {})
    return cfg


def _trigger_hotswap(key):
    """Hot-Swap-Platz ausfuehren. Gibt eine Ergebnis-Meldung zurueck."""
    binding = _hotswap_cfg()["bindings"].get(str(key))
    if not binding:
        raise ApiError(f"Hot-Swap F{key} ist nicht belegt.")

    if binding["type"] == "loadout":
        result = _apply_loadout(binding["name"], best_effort=True)
        msg = f"Loadout „{binding['name']}“ geladen."
        if result["blocked"]:
            slots = ", ".join(map(str, result["blocked"]))
            msg += f" Slot(s) {slots} sind in RPCS3 gesperrt und wurden uebersprungen."
        return {"message": msg, "blocked": result["blocked"]}

    # Einzelfigur -> Slot nach Platzierungs-Modus (P1/P2 ueberschreibt, Frei = naechster)
    info, _ = _entry_info(binding)
    if info is None:
        raise ApiError("Figur konnte nicht aufgeloest werden.")
    slot, _actions = _place_figure(info)
    return {"message": f"{info['display']} → Slot {slot + 1}", "blocked": []}


def _beep(ok, warning=False):
    try:
        if not ok:
            winsound.Beep(220, 220)
            winsound.Beep(220, 220)
        elif warning:
            winsound.Beep(587, 180)
        else:
            winsound.Beep(880, 110)
            winsound.Beep(1175, 110)
    except RuntimeError:
        pass


def _hotkey_fire(key):
    global _last_event
    try:
        result = _trigger_hotswap(key)
        _beep(True, warning=bool(result["blocked"]))
        _last_event = {"seq": next(_hotswap_seq), "ok": True, "message": result["message"]}
        _auto_inject(_sync_actions_full())
    except Exception as e:  # noqa - Hotkey-Thread darf nie sterben
        _beep(False)
        _last_event = {"seq": next(_hotswap_seq), "ok": False, "message": str(e)}
    print(f"[Hot-Swap F{key}] {_last_event['message']}")


def _start_hotkeys():
    try:
        import keyboard
    except ImportError:
        print("Hinweis: Paket 'keyboard' fehlt - globale Hotkeys deaktiviert (pip install keyboard).")
        return
    mod = _hotswap_cfg()["modifier"]
    for i in range(1, 10):
        keyboard.add_hotkey(f"{mod}+f{i}", _hotkey_fire, args=(i,))
    print(f"Globale Hotkeys aktiv: {mod}+F1..F9 (funktionieren auch waehrend RPCS3 laeuft)")


@app.route("/api/hotswap")
def api_hotswap():
    cfg = _hotswap_cfg()
    return jsonify({"ok": True, "modifier": cfg["modifier"], "bindings": cfg["bindings"]})


@app.route("/api/hotswap/set", methods=["POST"])
def api_hotswap_set():
    d = request.get_json(force=True)
    key = str(d["key"])
    if key not in [str(i) for i in range(1, 10)]:
        raise ApiError("Ungueltiger Hot-Swap-Platz.")
    cfg = _hotswap_cfg()
    cfg["bindings"][key] = d["binding"]
    _save_json(HOTSWAP_FILE, cfg)
    return jsonify({"ok": True, "bindings": cfg["bindings"]})


@app.route("/api/hotswap/clear", methods=["POST"])
def api_hotswap_clear():
    d = request.get_json(force=True)
    cfg = _hotswap_cfg()
    cfg["bindings"].pop(str(d.get("key")), None)
    _save_json(HOTSWAP_FILE, cfg)
    return jsonify({"ok": True, "bindings": cfg["bindings"]})


@app.route("/api/hotswap/trigger", methods=["POST"])
def api_hotswap_trigger():
    d = request.get_json(force=True)
    result = _trigger_hotswap(d.get("key"))
    _auto_inject(_sync_actions_full())
    return jsonify({"ok": True, "message": result["message"], "slots": _portal_slots()})


@app.route("/api/hotswap/status")
def api_hotswap_status():
    return jsonify({"ok": True, "event": _last_event})


# ------------------------------------------------------------------ RPCS3 starten

RPCS3_DEFAULT_EXE = Path(r"D:\Programme\Emulatoren\ps3\rpcs3.exe")


def _rpcs3_exe():
    p = _settings().get("rpcs3_path")
    if p and Path(p).exists():
        return Path(p)
    return RPCS3_DEFAULT_EXE if RPCS3_DEFAULT_EXE.exists() else None


def _parse_sfo(path):
    """PARAM.SFO minimal parsen (TITLE, TITLE_ID)."""
    try:
        data = Path(path).read_bytes()
        if data[:4] != b"\x00PSF":
            return {}
        key_start, data_start, count = struct.unpack_from("<III", data, 8)
        out = {}
        for i in range(count):
            ko, fmt, dlen, _dmax, do = struct.unpack_from("<HHIII", data, 0x14 + i * 16)
            key_end = data.index(b"\x00", key_start + ko)
            key = data[key_start + ko:key_end].decode("utf-8", "ignore")
            raw = data[data_start + do:data_start + do + dlen]
            if fmt in (0x0204, 0x0004):
                out[key] = raw.rstrip(b"\x00").decode("utf-8", "ignore")
        return out
    except (OSError, ValueError, struct.error):
        return {}


def _yaml_lines(path):
    """Einfache 'Key: Wert'-Zeilen aus RPCS3-YAML-Dateien (ohne echte YAML-Lib)."""
    entries = {}
    try:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if ": " in line and not line.startswith("#"):
                k, v = line.split(": ", 1)
                entries[k.strip()] = v.strip().strip('"')
    except OSError:
        pass
    return entries


def _rpcs3_games():
    """Installierte Skylanders-Spiele finden (games.yml + dev_hdd0)."""
    exe = _rpcs3_exe()
    if not exe:
        return []
    root = exe.parent
    candidates = []  # (spielordner, eboot)

    for _tid, gpath in _yaml_lines(root / "config" / "games.yml").items():
        gdir = Path(gpath)
        candidates.append((gdir / "PS3_GAME", gdir / "PS3_GAME" / "USRDIR" / "EBOOT.BIN"))

    hdd = _yaml_lines(root / "config" / "vfs.yml").get("/dev_hdd0/", "")
    hdd_dir = Path(hdd.replace("$(EmulatorDir)", str(root) + os.sep)) if hdd else root / "dev_hdd0"
    game_dir = hdd_dir / "game"
    if game_dir.is_dir():
        for d in game_dir.iterdir():
            candidates.append((d, d / "USRDIR" / "EBOOT.BIN"))

    games, seen = [], set()
    for gdir, eboot in candidates:
        sfo = _parse_sfo(gdir / "PARAM.SFO")
        title = sfo.get("TITLE", "")
        tid = sfo.get("TITLE_ID", "")
        if "skylander" not in title.lower() or not eboot.exists() or tid in seen:
            continue
        seen.add(tid)
        icon = gdir / "ICON0.PNG"
        games.append({
            "title": title.replace("\n", " "),
            "title_id": tid,
            "boot": str(eboot),
            "icon": str(icon) if icon.exists() else None,
        })
    return sorted(games, key=lambda g: (_series_order(g["title"]), g["title"]))


# Reihenfolge der Serie (Release-Reihenfolge), nicht alphabetisch
_SERIES_KEYWORDS = ["spyro", "giants", "swap", "trap", "supercharger", "imaginator"]


def _series_order(title):
    t = title.lower()
    for i, kw in enumerate(_SERIES_KEYWORDS):
        if kw in t:
            return i
    return len(_SERIES_KEYWORDS)


@app.route("/api/rpcs3/games")
def api_rpcs3_games():
    exe = _rpcs3_exe()
    return jsonify({"ok": True, "exe": str(exe) if exe else None, "games": _rpcs3_games()})


@app.route("/api/rpcs3/icon/<title_id>")
def api_rpcs3_icon(title_id):
    for g in _rpcs3_games():
        if g["title_id"] == title_id and g["icon"]:
            return send_file(g["icon"], mimetype="image/png")
    return "", 404


@app.route("/api/rpcs3/launch", methods=["POST"])
def api_rpcs3_launch():
    d = request.get_json(force=True)
    exe = _rpcs3_exe()
    if not exe:
        raise ApiError("rpcs3.exe nicht gefunden (Pfad in settings.json unter 'rpcs3_path' setzen).")
    if inj.available() and inj.rpcs3_running():
        raise ApiError("RPCS3 läuft bereits.")
    game = next((g for g in _rpcs3_games() if g["boot"] == d.get("boot")), None)
    if not game:
        raise ApiError("Spiel nicht gefunden.")
    subprocess.Popen([str(exe), game["boot"]], cwd=str(exe.parent))
    return jsonify({"ok": True, "message": f"RPCS3 startet mit {game['title']}…"})


# ------------------------------------------------------------------ RPCS3 Auto-Inject

def _settings():
    s = _load_json(SETTINGS_FILE, {})
    s.setdefault("auto_inject", False)
    s.setdefault("placement", "p1")  # p1 | p2 | free
    if "extra_libraries" not in s:
        # Vorhandene Sammlung neben RPCS3 einmalig automatisch einbinden
        s["extra_libraries"] = [str(DEFAULT_EXTRA_LIBRARY)] if DEFAULT_EXTRA_LIBRARY.exists() else []
        _save_json(SETTINGS_FILE, s)
    return s


def _set_settings(s):
    _save_json(SETTINGS_FILE, s)


EMPTY_SLOT_LABELS = {"", "None", "Keine"}


def _load_action(slot):
    """('load', slot, pfad, anzeigename) fuer einen belegten Slot."""
    p = _portal_files().get(slot)
    if not p:
        return None
    st = _portal_state().get(slot) or {}
    name = display_name(st.get("id"), st.get("var")) if st.get("id") is not None else None
    return ("load", slot, str(p), name)


def _report_event(ok, message):
    global _last_event
    _last_event = {"seq": next(_hotswap_seq), "ok": ok, "message": message}


def _run_inject(actions):
    """actions: ('load', slot, pfad, name) / ('clear', slot). Laeuft im Hintergrund-Thread.
    Liest RPCS3s aktuellen Stand und ueberspringt, was schon passt."""
    def worker():
        global _inject_active
        with _busy_lock:
            _inject_active += 1
        try:
            _worker_body()
        finally:
            with _busy_lock:
                _inject_active -= 1

    def _worker_body():
        with _inject_lock:
            try:
                if not inj.available():
                    _report_event(False, "pywinauto fehlt - Auto-Inject nicht moeglich.")
                    return
                if not inj.rpcs3_running():
                    _report_event(False, "RPCS3 laeuft nicht - Figuren liegen bereit, aber nicht geladen.")
                    return
                mgr = inj.open_manager()
                current = inj.read_slots(mgr)

                def cur(slot):
                    return current[slot] if slot < len(current) else ""

                loaded = 0
                for act in actions:
                    if act[0] == "load" and act[2]:
                        slot, path, name = act[1], act[2], act[3]
                        if name and cur(slot) == name:
                            continue  # schon die richtige Figur geladen
                        inj.inject_slot(slot, path)
                        loaded += 1
                    elif act[0] == "clear":
                        if cur(act[1]) not in EMPTY_SLOT_LABELS:
                            inj.clear_slot(act[1])
                if loaded:
                    _report_event(True, f"In RPCS3 geladen ✓ ({loaded} Figur(en) live im Spiel).")
                else:
                    _report_event(True, "RPCS3 ist bereits aktuell ✓")
            except Exception as e:  # noqa - Thread darf nie sterben
                _report_event(False, f"RPCS3-Inject fehlgeschlagen: {e}")
    threading.Thread(target=worker, daemon=True).start()


def _auto_inject(actions):
    """Nur ausfuehren, wenn der Nutzer Auto-Inject aktiviert hat."""
    if _settings().get("auto_inject") and inj.available():
        _run_inject(actions)


def _sync_actions_full():
    """Aktionen, um RPCS3 exakt an das aktuelle Portal anzugleichen (Sync-Button/Loadouts)."""
    files = _portal_files()
    actions = []
    for i in range(NUM_SLOTS):
        if i in files:
            act = _load_action(i)
            if act:
                actions.append(act)
        else:
            actions.append(("clear", i))
    return actions


@app.route("/api/inject/status")
def api_inject_status():
    return jsonify({
        "ok": True,
        "available": inj.available(),
        "rpcs3_running": inj.available() and inj.rpcs3_running(),
        "auto_inject": _settings().get("auto_inject", False),
        "busy": _inject_active > 0,
        "placement": _settings().get("placement", "p1"),
    })


@app.route("/api/placement", methods=["POST"])
def api_placement():
    d = request.get_json(force=True)
    mode = d.get("mode")
    if mode not in ("p1", "p2", "free"):
        raise ApiError("Ungueltiger Platzierungs-Modus.")
    s = _settings()
    s["placement"] = mode
    _set_settings(s)
    return jsonify({"ok": True, "placement": mode})


@app.route("/api/inject/settings", methods=["POST"])
def api_inject_settings():
    d = request.get_json(force=True)
    s = _settings()
    s["auto_inject"] = bool(d.get("auto_inject"))
    _set_settings(s)
    return jsonify({"ok": True, "auto_inject": s["auto_inject"]})


@app.route("/api/inject/now", methods=["POST"])
def api_inject_now():
    """Aktuelles Portal manuell nach RPCS3 spiegeln (unabhaengig vom Auto-Inject-Schalter)."""
    if not inj.available():
        raise ApiError("Paket 'pywinauto' fehlt - bitte 'pip install pywinauto'.")
    if not inj.rpcs3_running():
        raise ApiError("RPCS3 laeuft nicht.")
    _run_inject(_sync_actions_full())
    return jsonify({"ok": True, "message": "Übertrage aktuelles Portal an RPCS3…"})


@app.route("/api/open", methods=["POST"])
def api_open():
    d = request.get_json(force=True)
    _ensure_dirs()
    target = PORTAL_DIR if d.get("which") == "portal" else LIB_DIR
    os.startfile(str(target))  # noqa - Windows only
    return jsonify({"ok": True})


def _lan_ip():
    """Lokale IP im Heimnetz ermitteln (fuer den Handy-Zugriff)."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return None


if __name__ == "__main__":
    _ensure_dirs()
    _start_hotkeys()
    port = 5177
    if "--no-browser" not in sys.argv:
        threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    print(f"BetterPortal laeuft auf http://127.0.0.1:{port}")
    ip = _lan_ip()
    if ip:
        print(f"Im Heimnetz (Handy/Tablet): http://{ip}:{port}")
    # 0.0.0.0 = auch aus dem WLAN erreichbar (Handy im gleichen Netz)
    app.run(host="0.0.0.0", port=port, debug=False)
