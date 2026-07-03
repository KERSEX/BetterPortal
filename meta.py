# Metadaten: Spiel-Zuordnung, Kategorien, Elemente, Swapper-Kombinationen
from skydata import RAW

GAMES = {
    1: "Spyro's Adventure",
    2: "Giants",
    3: "Swap Force",
    4: "Trap Team",
    5: "SuperChargers",
    6: "Imaginators",
}

ELEMENTS = [
    "Luft", "Erde", "Feuer", "Wasser", "Magie",
    "Tech", "Leben", "Untot", "Licht", "Dunkelheit", "Kaos",
]

# Element pro Basis-ID (nur Charaktere; Items/Fahrzeuge haben keins)
_ELEMENT_BY_ID = {
    # Spyro's Adventure (0-32)
    0: "Luft", 1: "Luft", 2: "Luft", 3: "Luft",
    4: "Erde", 5: "Erde", 6: "Erde", 7: "Erde",
    8: "Feuer", 9: "Feuer", 10: "Feuer", 11: "Feuer",
    12: "Wasser", 13: "Wasser", 14: "Wasser", 15: "Wasser",
    16: "Magie", 17: "Magie", 18: "Magie", 23: "Magie", 28: "Magie",
    19: "Tech", 20: "Tech", 21: "Tech", 22: "Tech",
    24: "Leben", 25: "Leben", 26: "Leben", 27: "Leben",
    29: "Untot", 30: "Untot", 31: "Untot", 32: "Untot",
    # Alte Legendaeren (eigene IDs)
    404: "Erde", 416: "Magie", 419: "Tech", 430: "Untot",
    # Giants (100-115)
    100: "Luft", 101: "Luft", 102: "Erde", 103: "Erde",
    104: "Feuer", 105: "Feuer", 106: "Wasser", 107: "Wasser",
    108: "Magie", 109: "Magie", 110: "Tech", 111: "Tech",
    112: "Leben", 113: "Leben", 114: "Untot", 115: "Untot",
    # Fallen (Trap Team, Element nach ID)
    210: "Magie", 211: "Wasser", 212: "Luft", 213: "Untot", 214: "Tech",
    215: "Feuer", 216: "Erde", 217: "Leben", 218: "Dunkelheit", 219: "Licht",
    220: "Kaos",
    # Trap Team (450-485)
    450: "Luft", 451: "Luft", 452: "Luft", 453: "Luft",
    454: "Erde", 455: "Erde", 456: "Erde", 457: "Erde",
    458: "Feuer", 459: "Feuer", 460: "Feuer", 461: "Feuer",
    462: "Wasser", 463: "Wasser", 464: "Wasser", 465: "Wasser",
    466: "Magie", 467: "Magie", 468: "Magie", 469: "Magie",
    470: "Tech", 471: "Tech", 472: "Tech", 473: "Tech",
    474: "Leben", 475: "Leben", 476: "Leben", 477: "Leben",
    478: "Untot", 479: "Untot", 480: "Untot", 481: "Untot",
    482: "Licht", 483: "Licht", 484: "Dunkelheit", 485: "Dunkelheit",
    # Minis / Sidekicks
    502: "Erde", 503: "Magie", 504: "Untot", 505: "Erde", 506: "Luft",
    507: "Feuer", 508: "Luft", 509: "Feuer", 510: "Tech", 514: "Wasser",
    519: "Tech", 526: "Leben", 540: "Leben", 541: "Wasser", 542: "Magie",
    543: "Untot",
    # Imaginators-Senseis (601-631, unsichere ausgelassen)
    601: "Wasser", 602: "Erde", 603: "Untot", 604: "Leben",
    607: "Luft", 608: "Feuer", 609: "Leben", 610: "Tech",
    611: "Dunkelheit", 612: "Feuer", 613: "Erde", 614: "Untot",
    615: "Magie", 616: "Magie", 617: "Dunkelheit", 618: "Dunkelheit",
    619: "Licht", 620: "Feuer", 621: "Leben", 622: "Luft",
    624: "Licht", 625: "Tech", 626: "Tech", 628: "Luft",
    629: "Wasser", 630: "Leben", 631: "Tech",
    # Swap Force Kern-Figuren (3000-3015)
    3000: "Luft", 3001: "Luft", 3002: "Erde", 3003: "Erde",
    3004: "Feuer", 3005: "Feuer", 3006: "Leben", 3007: "Leben",
    3008: "Magie", 3009: "Magie", 3010: "Tech", 3011: "Tech",
    3012: "Untot", 3013: "Untot", 3014: "Wasser", 3015: "Wasser",
    # SuperChargers-Charaktere
    3400: "Untot", 3401: "Tech", 3402: "Magie", 3406: "Luft",
    3411: "Erde", 3412: "Feuer", 3413: "Luft", 3414: "Tech",
    3415: "Leben", 3416: "Erde", 3417: "Untot", 3420: "Magie",
    3421: "Feuer", 3422: "Wasser", 3425: "Wasser", 3426: "Licht",
    3427: "Dunkelheit", 3428: "Leben",
}

# Die 16 Swap-Force-Swapper: Index -> (Namensteil oben, Namensteil unten, Element, Swap-Zone unten)
# Unterteil-ID = 1000 + Index, Oberteil-ID = 2000 + Index
SWAP_BASES = {
    0: ("Boom", "Jet", "Luft", "Rakete"),
    1: ("Free", "Ranger", "Luft", "Wirbeln"),
    2: ("Rubble", "Rouser", "Erde", "Graben"),
    3: ("Doom", "Stone", "Erde", "Wirbeln"),
    4: ("Blast", "Zone", "Feuer", "Rakete"),
    5: ("Fire", "Kraken", "Feuer", "Huepfen"),
    6: ("Stink", "Bomb", "Leben", "Schleichen"),
    7: ("Grilla", "Drilla", "Leben", "Graben"),
    8: ("Hoot", "Loop", "Magie", "Teleport"),
    9: ("Trap", "Shadow", "Magie", "Schleichen"),
    10: ("Magna", "Charge", "Tech", "Tempo"),
    11: ("Spy", "Rise", "Tech", "Klettern"),
    12: ("Night", "Shift", "Untot", "Teleport"),
    13: ("Rattle", "Shake", "Untot", "Huepfen"),
    14: ("Freeze", "Blade", "Wasser", "Tempo"),
    15: ("Wash", "Buckler", "Wasser", "Klettern"),
}

MOVE_ICONS = {
    "Rakete": "🚀", "Wirbeln": "🌀", "Graben": "⛏️", "Huepfen": "🦘",
    "Schleichen": "👣", "Teleport": "✨", "Tempo": "⚡", "Klettern": "🧗",
}


def _base_game(sid):
    """Herkunftsspiel anhand der Basis-ID."""
    if sid <= 32 or 200 <= sid <= 207 or 300 <= sid <= 305 or 400 <= sid <= 449:
        return 1
    if sid <= 115 or sid in (208, 209):
        return 2
    if 210 <= sid <= 233 or 306 <= sid <= 308 or 450 <= sid <= 499 or 502 <= sid <= 599:
        return 4
    if 601 <= sid <= 699:
        return 6
    if 1000 <= sid <= 3399:
        return 3
    if 3400 <= sid <= 3599:
        return 5
    return 1


def _category(sid):
    if 1000 <= sid <= 1015:
        return "Swapper (Unterteil)"
    if 2000 <= sid <= 2015:
        return "Swapper (Oberteil)"
    if 210 <= sid <= 220:
        return "Falle"
    if 200 <= sid <= 209 or 230 <= sid <= 233 or 3200 <= sid <= 3204:
        return "Magisches Item"
    if 300 <= sid <= 308 or 3300 <= sid <= 3303:
        return "Abenteuer/Erweiterung"
    if 3220 <= sid <= 3241:
        return "Fahrzeug"
    if 3500 <= sid <= 3503:
        return "Trophaee"
    if 502 <= sid <= 543:
        return "Mini"
    return "Figur"


def _games_for(sid, var, category):
    """In welchen Spielen ist die Figur nutzbar?"""
    base = _base_game(sid)
    # Varianten-Generation steckt im obersten Nibble der Varianten-ID
    # (0=Original, 1=Giants, 2=Swap Force, 3=Trap Team, 4=SuperChargers)
    gen = (var >> 12) & 0xF
    if 1 <= gen <= 4:
        base = max(base, gen + 1)
    # Kategorien, die nur in ihrem eigenen Spiel funktionieren
    if category == "Falle":
        return [4]
    if category in ("Fahrzeug", "Trophaee"):
        return [5]
    if base == 6:
        return [6]
    return list(range(base, 7))


def _element_for(sid):
    if 1000 <= sid <= 1015 or 2000 <= sid <= 2015:
        return SWAP_BASES[sid % 1000][2]
    return _ELEMENT_BY_ID.get(sid)


def build_db():
    db = []
    for sid, var, name in RAW:
        cat = _category(sid)
        games = _games_for(sid, var, cat)
        db.append({
            "id": sid,
            "var": var,
            "name": name,
            "category": cat,
            "element": _element_for(sid),
            "games": games,
            "game": GAMES[games[0]],
        })
    return db


def build_swappers():
    """Swapper-Liste inkl. aller Varianten fuer Ober- und Unterteile."""
    by_id = {}
    for sid, var, name in RAW:
        by_id.setdefault(sid, []).append({"var": var, "name": name})

    swappers = []
    for idx, (top_part, bottom_part, element, move) in SWAP_BASES.items():
        swappers.append({
            "index": idx,
            "name": f"{top_part} {bottom_part}",
            "name_top": top_part,
            "name_bottom": bottom_part,
            "element": element,
            "move": move,
            "move_icon": MOVE_ICONS[move],
            "top_id": 2000 + idx,
            "bottom_id": 1000 + idx,
            "tops": sorted(by_id.get(2000 + idx, []), key=lambda e: e["var"]),
            "bottoms": sorted(by_id.get(1000 + idx, []), key=lambda e: e["var"]),
        })
    return swappers


DB = build_db()
SWAPPERS = build_swappers()
NAME_BY_KEY = {(e["id"], e["var"]): e["name"] for e in DB}


def display_name(sky_id, sky_var):
    name = NAME_BY_KEY.get((sky_id, sky_var))
    if name:
        return name
    # Unbekannte Variante: auf Basis-Variante zurueckfallen
    base = NAME_BY_KEY.get((sky_id, 0))
    if base:
        return f"{base} (Var. {sky_var:#06x})"
    return f"Unbekannt (ID {sky_id}, Var. {sky_var:#06x})"
