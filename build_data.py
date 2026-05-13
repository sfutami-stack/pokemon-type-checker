#!/usr/bin/env python3
"""Build docs/data.json for the FRLG Pokemon type matchup tool.

Fetches data from PokeAPI and produces a single static JSON consumed by the
frontend. Designed for one-shot generation; intermediate API responses are
cached under .cache/ so re-runs are fast and friendly to PokeAPI.

Scope (per spec):
  - Kanto 151 (IDs 1-151), included unconditionally.
  - All Gen 2 obtainable in FRLG: IDs 161-251 (everything except the Johto
    starter lines 152-160, which require trade from Colosseum/XD events).
    This covers wild Sevii encounters, Kanto-line evolutions (Crobat,
    Bellossom, Steelix, etc.), trade evolutions, Eevee branches
    (Espeon/Umbreon), baby breeding products (Pichu, Tyrogue, Elekid...),
    and the roaming/static legendaries (Raikou/Entei/Suicune/Lugia/Ho-Oh).
    Encounter data on PokeAPI is incomplete for FRLG (e.g. Hoothoot,
    Sunkern, Sudowoodo are wild in-game but absent), so we don't gate on
    it here.
  - FRLG event-distribution Gen 3 (4 species): 380 Latias / 381 Latios
    (Eon Ticket -> Southern Island), 385 Jirachi (Colosseum / Pokemon
    Channel bonus disc), 386 Deoxys (Aurora Ticket -> Birth Island).
    Other Gen 3 mons (Kyogre/Groudon/Rayquaza etc.) are R/S/E distribution
    and intentionally excluded.
  - Abilities are reconstructed to Gen 3 state by applying PokeAPI's
    past_abilities overrides on top of the current ability list, then
    dropping hidden slots (added in Gen 5) and any slot that resolves to
    None for Gen 3. This handles Gengar (Levitate -> Cursed Body in Gen 7),
    Pidgey (Tangled Feet added in Gen 4), and similar reassignments.
"""

import json
import re
import sys
import time
from pathlib import Path

import pykakasi
import requests

ROOT = Path(__file__).resolve().parent
CACHE_DIR = ROOT / ".cache"
OUTPUT = ROOT / "docs" / "data.json"
SW_PATH = ROOT / "docs" / "service-worker.js"
KATAKANA_READINGS = ROOT / "katakana_readings.json"
POKEAPI = "https://pokeapi.co/api/v2"
HEADERS = {"User-Agent": "frlg-type-tool/1.0 (personal use)"}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


# --- Type metadata (Italian display + official-ish colors) ---------------
TYPES = {
    "normal":   {"it": "NORMALE",    "color": "#A8A77A", "text": "white"},
    "fighting": {"it": "LOTTA",      "color": "#C22E28", "text": "white"},
    "flying":   {"it": "VOLANTE",    "color": "#A98FF3", "text": "white"},
    "poison":   {"it": "VELENO",     "color": "#A33EA1", "text": "white"},
    "ground":   {"it": "TERRA",      "color": "#E2BF65", "text": "white"},
    "rock":     {"it": "ROCCIA",     "color": "#B6A136", "text": "white"},
    "bug":      {"it": "COLEOTTERO", "color": "#A6B91A", "text": "white"},
    "ghost":    {"it": "SPETTRO",    "color": "#735797", "text": "white"},
    "steel":    {"it": "ACCIAIO",    "color": "#B7B7CE", "text": "white"},
    "fire":     {"it": "FUOCO",      "color": "#EE8130", "text": "white"},
    "water":    {"it": "ACQUA",      "color": "#6390F0", "text": "white"},
    "grass":    {"it": "ERBA",       "color": "#7AC74C", "text": "white"},
    "electric": {"it": "ELETTRO",    "color": "#F7D02C", "text": "black"},
    "psychic":  {"it": "PSICO",      "color": "#F95587", "text": "white"},
    "ice":      {"it": "GHIACCIO",   "color": "#96D9D6", "text": "white"},
    "dragon":   {"it": "DRAGO",      "color": "#6F35FC", "text": "white"},
    "dark":     {"it": "BUIO",       "color": "#705746", "text": "white"},
}


# --- Gen 3 type chart (attacker -> defender -> multiplier) ---------------
# Only non-1.0 cells listed; everything else is 1.0. Differs from current:
#   Ghost -> Steel = 0.5 and Dark -> Steel = 0.5 (Steel resisted both in
#   Gen 2-5; that resistance was removed in Gen 6).
# Fairy is omitted entirely (introduced in Gen 6).
GEN3_OVERRIDES = {
    "normal":   {"ghost": 0, "rock": 0.5, "steel": 0.5},
    "fighting": {"normal": 2, "ice": 2, "rock": 2, "dark": 2, "steel": 2,
                 "flying": 0.5, "poison": 0.5, "bug": 0.5, "psychic": 0.5,
                 "ghost": 0},
    "flying":   {"fighting": 2, "bug": 2, "grass": 2,
                 "rock": 0.5, "steel": 0.5, "electric": 0.5},
    "poison":   {"grass": 2,
                 "poison": 0.5, "ground": 0.5, "rock": 0.5, "ghost": 0.5,
                 "steel": 0},
    "ground":   {"poison": 2, "rock": 2, "steel": 2, "fire": 2, "electric": 2,
                 "bug": 0.5, "grass": 0.5,
                 "flying": 0},
    "rock":     {"flying": 2, "bug": 2, "fire": 2, "ice": 2,
                 "fighting": 0.5, "ground": 0.5, "steel": 0.5},
    "bug":      {"grass": 2, "psychic": 2, "dark": 2,
                 "fighting": 0.5, "flying": 0.5, "poison": 0.5,
                 "ghost": 0.5, "steel": 0.5, "fire": 0.5},
    "ghost":    {"ghost": 2, "psychic": 2,
                 "dark": 0.5, "steel": 0.5,
                 "normal": 0},
    "steel":    {"rock": 2, "ice": 2,
                 "steel": 0.5, "fire": 0.5, "water": 0.5, "electric": 0.5},
    "fire":     {"bug": 2, "steel": 2, "grass": 2, "ice": 2,
                 "rock": 0.5, "fire": 0.5, "water": 0.5, "dragon": 0.5},
    "water":    {"ground": 2, "rock": 2, "fire": 2,
                 "water": 0.5, "grass": 0.5, "dragon": 0.5},
    "grass":    {"ground": 2, "rock": 2, "water": 2,
                 "flying": 0.5, "poison": 0.5, "bug": 0.5, "steel": 0.5,
                 "fire": 0.5, "grass": 0.5, "dragon": 0.5},
    "electric": {"flying": 2, "water": 2,
                 "grass": 0.5, "electric": 0.5, "dragon": 0.5,
                 "ground": 0},
    "psychic":  {"fighting": 2, "poison": 2,
                 "psychic": 0.5, "steel": 0.5,
                 "dark": 0},
    "ice":      {"flying": 2, "ground": 2, "grass": 2, "dragon": 2,
                 "steel": 0.5, "fire": 0.5, "water": 0.5, "ice": 0.5},
    "dragon":   {"dragon": 2,
                 "steel": 0.5},
    "dark":     {"ghost": 2, "psychic": 2,
                 "fighting": 0.5, "dark": 0.5, "steel": 0.5},
}


# Abilities that change effective type matchups in Gen 3.
# negates: incoming attacks of this type become 0x.
# halves:  incoming attacks of these types are halved (post-chart).
SPECIAL_ABILITIES = {
    "levitate":     {"negates": "ground"},
    "volt-absorb":  {"negates": "electric"},
    "water-absorb": {"negates": "water"},
    "flash-fire":   {"negates": "fire"},
    "thick-fat":    {"halves": ["fire", "ice"]},
}


def build_type_chart():
    chart = {}
    for atk in TYPES:
        chart[atk] = {dfn: GEN3_OVERRIDES.get(atk, {}).get(dfn, 1)
                      for dfn in TYPES}
    return chart


# --- Cached HTTP fetch ---------------------------------------------------
def _cache_path(url):
    safe = url.replace("https://", "").replace("/", "_").replace(":", "_")
    return CACHE_DIR / f"{safe}.json"


def fetch(url):
    CACHE_DIR.mkdir(exist_ok=True)
    cp = _cache_path(url)
    if cp.exists():
        return json.loads(cp.read_text(encoding="utf-8"))
    last_err = None
    for attempt in range(3):
        try:
            r = SESSION.get(url, timeout=30)
            r.raise_for_status()
            data = r.json()
            cp.write_text(json.dumps(data), encoding="utf-8")
            return data
        except (requests.RequestException, ValueError) as e:
            last_err = e
            print(f"  retry {url} ({e})", file=sys.stderr)
            time.sleep(1 + attempt)
    raise RuntimeError(f"fetch failed: {url}: {last_err}")


# --- Helpers -------------------------------------------------------------
def kata_to_hira(s):
    out = []
    for c in s:
        # Katakana block ァ (30A1) .. ヶ (30F6) -> hiragana
        if "ァ" <= c <= "ヶ":
            out.append(chr(ord(c) - 0x60))
        else:
            out.append(c)
    return "".join(out)


def japanese_name(species):
    """Pokemon display name. Prefer ja-Hrkt, fall back to ja."""
    name_jhrkt = None
    name_ja = None
    for n in species["names"]:
        lang = n["language"]["name"]
        if lang == "ja-Hrkt":
            name_jhrkt = n["name"]
        elif lang == "ja":
            name_ja = n["name"]
    return name_jhrkt or name_ja


def english_name(species):
    """Pokemon English display name from species.names (language='en')."""
    for n in species["names"]:
        if n["language"]["name"] == "en":
            return n["name"]
    return None


# Ordered preference for ability flavor text. FRLG-era first, then nearby
# Gen 3 games, then progressively newer. The wording on these abilities is
# stable enough that newer-game text is fine when no Gen 3 text exists.
_VG_PREFERENCE = [
    "firered-leafgreen", "ruby-sapphire", "emerald", "colosseum", "xd",
    "diamond-pearl", "platinum", "heartgold-soulsilver",
    "black-white", "black-2-white-2",
    "x-y", "omega-ruby-alpha-sapphire",
    "sun-moon", "ultra-sun-ultra-moon",
    "lets-go-pikachu-lets-go-eevee",
    "sword-shield", "scarlet-violet",
]

# Daughter (small kid) can't read kanji yet, so strip every kanji from the
# ability descriptions. Note: PokeAPI's "ja-Hrkt" flavor text isn't actually
# pure kana — it still ships kanji like 触 / 相手 / 状態. So we always run the
# chosen text through pykakasi and replace each kanji-bearing token with its
# hiragana reading. Hiragana stays as hiragana; katakana words like タイプ /
# マグマ / シェル are intentionally preserved (the user wants the kana style
# kept for technical / loanword vocabulary).
_KANJI_RE = re.compile(r"[㐀-䶿一-鿿豈-﫿]")
_KAKASI = pykakasi.kakasi()


def _strip_kanji(text):
    if not _KANJI_RE.search(text):
        return text
    out = []
    for item in _KAKASI.convert(text):
        orig = item["orig"]
        out.append(item["hira"] if _KANJI_RE.search(orig) else orig)
    return "".join(out)


def japanese_ability_text(ability):
    # Bucket flavor text by version_group, separately for ja-Hrkt (preferred)
    # and ja (fallback). Within each language, the first entry per
    # version_group wins.
    by_vg_hrkt = {}
    by_vg_ja = {}
    for ft in ability["flavor_text_entries"]:
        lang = ft["language"]["name"]
        vg = ft.get("version_group", {}).get("name", "")
        if lang == "ja-Hrkt":
            by_vg_hrkt.setdefault(vg, ft["flavor_text"])
        elif lang == "ja":
            by_vg_ja.setdefault(vg, ft["flavor_text"])

    chosen = None
    # 1) Best ja-Hrkt by version-group preference.
    for vg in _VG_PREFERENCE:
        if vg in by_vg_hrkt:
            chosen = by_vg_hrkt[vg]
            break
    # 2) Best ja by version-group preference.
    if chosen is None:
        for vg in _VG_PREFERENCE:
            if vg in by_vg_ja:
                chosen = by_vg_ja[vg]
                break
    # 3) Any ja-Hrkt then any ja.
    if chosen is None and by_vg_hrkt:
        chosen = next(iter(by_vg_hrkt.values()))
    if chosen is None and by_vg_ja:
        chosen = next(iter(by_vg_ja.values()))
    # 4) Fall back to English short_effect.
    if chosen is None:
        for e in ability["effect_entries"]:
            if e["language"]["name"] == "en":
                return e.get("short_effect", "").strip()
        return ""

    return _strip_kanji(_clean(chosen))


def _clean(text):
    return text.replace("\n", " ").replace("\f", " ").replace("　", " ").strip()


# Reconstruct each Pokemon's Gen 3 ability slots.
#
# PokeAPI's `abilities` field reflects the *current* assignment. Hidden
# abilities (slot 3) didn't exist until Gen 5, and a handful of Pokemon had
# their regular ability changed in later gens (e.g. Gengar: Levitate ->
# Cursed Body in Gen 7; Pidgey gained Tangled Feet in Gen 4).
#
# `past_abilities` records per-slot overrides that applied in earlier
# generations. Each entry's `generation` is the latest gen for which that
# override held. We collect every entry whose generation >= Gen 3, layer
# them onto the current slot map, then drop None-or-hidden slots.
_GEN_NUM = {
    "generation-i": 1, "generation-ii": 2, "generation-iii": 3,
    "generation-iv": 4, "generation-v": 5, "generation-vi": 6,
    "generation-vii": 7, "generation-viii": 8, "generation-ix": 9,
}


def gen3_types(poke):
    """Pokemon types as of Gen 3.

    PokeAPI's `types` is current (Gen 9). Several Pokemon were retconned to
    Fairy in Gen 6 (Clefairy, Jigglypuff, Mr. Mime, Snubbull, Cleffa,
    Togepi, ...). past_types records the older typing; we take the earliest
    past entry whose generation >= 3.
    """
    candidates = []
    for entry in (poke.get("past_types") or []):
        gen = _GEN_NUM.get(entry["generation"]["name"], 99)
        if gen >= 3:
            candidates.append((gen, entry["types"]))
    if candidates:
        candidates.sort()
        types = candidates[0][1]
    else:
        types = poke["types"]
    return [t["type"]["name"] for t in sorted(types, key=lambda x: x["slot"])]


def gen3_ability_keys(poke):
    slots = {}  # slot -> (ability_key_or_None, is_hidden)
    for a in poke["abilities"]:
        ab = a["ability"]["name"] if a.get("ability") else None
        slots[a["slot"]] = (ab, a["is_hidden"])
    for entry in (poke.get("past_abilities") or []):
        gen = _GEN_NUM.get(entry["generation"]["name"], 99)
        if gen < 3:
            continue
        for a in entry["abilities"]:
            ab = a["ability"]["name"] if a.get("ability") else None
            slots[a["slot"]] = (ab, a["is_hidden"])
    out = []
    for slot in sorted(slots):
        ab, hidden = slots[slot]
        if ab is None or hidden:
            continue
        out.append(ab)
    return out


def japanese_ability_name(ability):
    name = None
    for n in ability["names"]:
        if n["language"]["name"] == "ja-Hrkt":
            return n["name"]
        if n["language"]["name"] == "ja":
            name = n["name"]
    return name or ability["name"]


# --- Main build ----------------------------------------------------------
def load_katakana_readings():
    """Hand-curated English -> Katakana map for pronunciation display.

    Keys are exact English Pokemon names as returned by PokeAPI (case +
    punctuation preserved, e.g. 'Mr. Mime', 'Ho-Oh', 'Farfetch’d').
    Missing keys are not a build error; the affected Pokemon get an empty
    `name_en_katakana` and the frontend falls back to hiding the reading.
    """
    if not KATAKANA_READINGS.exists():
        print(f"  WARN: {KATAKANA_READINGS} not found; "
              "name_en_katakana will be empty for all Pokemon",
              file=sys.stderr)
        return {}
    return json.loads(KATAKANA_READINGS.read_text(encoding="utf-8"))


def main():
    # Kanto 151 + all FRLG-obtainable Gen 2 (everything except Johto starters)
    # + FRLG event-distribution Gen 3 (Latias/Latios/Jirachi/Deoxys).
    pokemon_ids = (
        list(range(1, 152))
        + list(range(161, 252))
        + [380, 381, 385, 386]
    )
    print(f"Total Pokemon to fetch: {len(pokemon_ids)}")

    katakana_map = load_katakana_readings()
    print(f"Katakana readings loaded: {len(katakana_map)} entries")
    katakana_unused = set(katakana_map.keys())

    pokemon_out = []
    ability_keys = set()

    for i, pid in enumerate(pokemon_ids, 1):
        species = fetch(f"{POKEAPI}/pokemon-species/{pid}")
        poke = fetch(f"{POKEAPI}/pokemon/{pid}")
        name_ja = japanese_name(species)
        if not name_ja:
            print(f"  WARN: no Japanese name for id {pid}", file=sys.stderr)
            continue
        name_en = english_name(species)
        if not name_en:
            print(f"  WARN: no English name for id {pid}", file=sys.stderr)
        name_en_katakana = katakana_map.get(name_en or "", "")
        if name_en and not name_en_katakana:
            print(f"  WARN: no katakana reading for {name_en!r} (id {pid})",
                  file=sys.stderr)
        katakana_unused.discard(name_en)

        types = gen3_types(poke)

        abilities = gen3_ability_keys(poke)
        ability_keys.update(abilities)

        pokemon_out.append({
            "id": pid,
            "name_ja": name_ja,
            "name_hira": kata_to_hira(name_ja),
            "name_en": name_en,
            "name_en_katakana": name_en_katakana,
            "types": types,
            "abilities": abilities,
        })
        if i % 25 == 0 or i == len(pokemon_ids):
            print(f"  Pokemon {i}/{len(pokemon_ids)} processed")

    if katakana_unused:
        print(f"  WARN: {len(katakana_unused)} katakana key(s) in "
              f"{KATAKANA_READINGS.name} did not match any Pokemon: "
              f"{sorted(katakana_unused)}", file=sys.stderr)

    print(f"Building ability dictionary ({len(ability_keys)} unique)...")
    abilities_out = {}
    for key in sorted(ability_keys):
        ab = fetch(f"{POKEAPI}/ability/{key}")
        entry = {
            "name_ja": japanese_ability_name(ab),
            "desc_ja": japanese_ability_text(ab),
        }
        if key in SPECIAL_ABILITIES:
            entry.update(SPECIAL_ABILITIES[key])
        abilities_out[key] = entry

    generated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    output = {
        "version": "1.0.0",
        "generated_at": generated_at,
        "types": TYPES,
        "type_chart": build_type_chart(),
        "pokemon": sorted(pokemon_out, key=lambda p: p["id"]),
        "abilities": abilities_out,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT}")
    print(f"  pokemon: {len(pokemon_out)}")
    print(f"  abilities: {len(abilities_out)}")

    bump_service_worker_version(generated_at)


def bump_service_worker_version(generated_at):
    """Rewrite the CACHE_VERSION constant in docs/service-worker.js.

    The SW caches static assets (HTML/JS/CSS/icons) under this name and
    drops any cache that doesn't match on activate. Bumping it on every
    rebuild forces installed PWAs to discard the stale shell cache the
    next time they hit the network — without us having to remember to
    bump anything by hand.

    data.json itself is fetched network-first inside the SW (see
    docs/service-worker.js), so its updates ship without needing the
    version to roll. We still bump on every build so any incidental
    change to the shell (a new ability listed, a tweaked CSS file, etc.)
    propagates correctly.
    """
    if not SW_PATH.exists():
        print(f"  WARN: {SW_PATH} not found, skipping SW version bump",
              file=sys.stderr)
        return
    new_version = "frlg-" + generated_at.replace(":", "-")
    sw_text = SW_PATH.read_text(encoding="utf-8")
    sw_new, n = re.subn(
        r"const CACHE_VERSION = '[^']*';",
        f"const CACHE_VERSION = '{new_version}';",
        sw_text,
        count=1,
    )
    if n != 1:
        print("  WARN: CACHE_VERSION line not found in service-worker.js; "
              "the SW will keep serving the old shell cache",
              file=sys.stderr)
        return
    if sw_new == sw_text:
        return  # version already current (e.g. rebuild within same second)
    SW_PATH.write_text(sw_new, encoding="utf-8")
    print(f"Bumped SW CACHE_VERSION -> {new_version}")


if __name__ == "__main__":
    main()
