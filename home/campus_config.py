"""
Centralized Campus Configuration — single source of truth for all campuses.

HOW TO ADD A NEW CAMPUS:
────────────────────────
1. Add an entry to the CAMPUSES list below with:
   - code:      short unique code (e.g. "XYZ")
   - name:      full display name (e.g. "XYZ University Main Campus")
   - org:       organization name (e.g. "XYZ University")
   - aliases:   list of alternate names/codes for search (e.g. ["xyz", "XYZ Main"])
   - active:    True/False — set False to soft-disable without deleting
2. Add any legacy mappings to LEGACY_CAMPUS_MAP if old DB values need translation.
3. That's it. All dropdowns, validators, display helpers, and API filters pick it up
   automatically — no other files need changes.
"""

from __future__ import annotations

from typing import Optional

# ──────────────────────────────────────────────
# MASTER CAMPUS LIST
# ──────────────────────────────────────────────

CAMPUSES = [
    # ── SRM ──
    {"code": "KTR", "name": "Kattankulathur (KTR)", "org": "SRM", "aliases": ["Kattankulathur", "SRM KTR", "SRM Kattankulathur", "ktr"], "active": True},
    {"code": "RMP", "name": "Ramapuram (RMP)",       "org": "SRM", "aliases": ["Ramapuram", "SRM Ramapuram", "rmp"], "active": True},
    {"code": "VDP", "name": "Vadapalani (VDP)",       "org": "SRM", "aliases": ["Vadapalani", "SRM Vadapalani", "vdp"], "active": True},
    {"code": "ESW", "name": "Eswari (ESW)",           "org": "SRM", "aliases": ["Eswari", "SRM Eswari", "Easwari", "esw"], "active": True},
    {"code": "AP",  "name": "Amaravati (AP)",         "org": "SRM", "aliases": ["Amaravati", "SRM AP", "SRM Amaravati", "AMT", "ap"], "active": True},
    {"code": "NCR", "name": "Delhi NCR",              "org": "SRM", "aliases": ["NCR", "SRM Delhi NCR", "NCR Modinagar", "ncr"], "active": True},
    {"code": "SPT", "name": "Sonepat (SPT)",          "org": "SRM", "aliases": ["Sonepat", "SRM Sonepat", "spt"], "active": True},
    {"code": "SKM", "name": "Sikkim (SKM)",           "org": "SRM", "aliases": ["Sikkim", "SRM Sikkim", "skm"], "active": True},

    # ── Amrita ──
    {"code": "ACB", "name": "Amrita Coimbatore (ACB)",      "org": "Amrita", "aliases": ["Coimbatore", "Amrita Coimbatore", "acb"], "active": True},
    {"code": "AKO", "name": "Amrita Kochi (AKO)",           "org": "Amrita", "aliases": ["Kochi", "Amrita Kochi", "ako"], "active": True},
    {"code": "AAP", "name": "Amrita Amritapuri (AAP)",      "org": "Amrita", "aliases": ["Amritapuri", "Amrita Amritapuri", "aap"], "active": True},
    {"code": "ABL", "name": "Amrita Bengaluru (ABL)",       "org": "Amrita", "aliases": ["Bengaluru", "Amrita Bengaluru", "Bangalore", "abl"], "active": True},
    {"code": "AMY", "name": "Amrita Mysuru (AMY)",          "org": "Amrita", "aliases": ["Mysuru", "Amrita Mysuru", "Mysore", "amy"], "active": True},
    {"code": "ACH", "name": "Amrita Chennai (ACH)",         "org": "Amrita", "aliases": ["Chennai", "Amrita Chennai", "ach"], "active": True},
    {"code": "AAM", "name": "Amrita Amaravati (AAM)",       "org": "Amrita", "aliases": ["Amaravati", "Amrita Amaravati", "aam"], "active": True},
    {"code": "AFD", "name": "Amrita Faridabad (AFD)",       "org": "Amrita", "aliases": ["Faridabad", "Amrita Faridabad", "afd"], "active": True},
    {"code": "ANG", "name": "Amrita Nagercoil (ANG)",       "org": "Amrita", "aliases": ["Nagercoil", "Amrita Nagercoil", "ang"], "active": True},
    {"code": "AHD", "name": "Amrita Haridwar (AHD)",        "org": "Amrita", "aliases": ["Haridwar", "Amrita Haridwar", "ahd"], "active": True},
    {"code": "AON", "name": "Amrita Online (AON)",          "org": "Amrita", "aliases": ["Online", "Amrita Online", "aon"], "active": True},

    # ── VIT ──
    {"code": "VLR", "name": "VIT Vellore (VLR)",            "org": "VIT",  "aliases": ["Vellore", "VIT Vellore", "vlr"], "active": True},
    {"code": "VCH", "name": "VIT Chennai (VCH)",            "org": "VIT",  "aliases": ["Chennai", "VIT Chennai", "vch"], "active": True},
    {"code": "VBP", "name": "VIT Bhopal (VBP)",             "org": "VIT",  "aliases": ["Bhopal", "VIT Bhopal", "vbp"], "active": True},
    {"code": "VAP", "name": "VIT AP Amaravati (VAP)",       "org": "VIT",  "aliases": ["VIT AP", "VIT Amaravati", "Amaravati", "vap"], "active": True},
    {"code": "VBL", "name": "VIT Bangalore (VBL)",          "org": "VIT",  "aliases": ["Bangalore", "VIT Bangalore", "Bengaluru", "vbl"], "active": True},
]

# Legacy DB value → canonical code mapping
# Old SRM campus names stored in the database that need to map to current codes
LEGACY_CAMPUS_MAP = {
    "Kattankulathur (KTR)": "KTR",
    "Ramapuram (RMP)":     "RMP",
    "Ramapuram":           "RMP",
    "Vadapalani (VDP)":    "VDP",
    "Vadapalani":          "VDP",
    "Eswari (ESW)":        "ESW",
    "Delhi NCR":           "NCR",
    "NCR Modinagar":       "NCR",
    "Tiruchirappalli (TCY)": "TCY",
    "Tiruchirappalli":     "TCY",
    "Amaravati (AMT)":     "AP",
    "SRM AP":              "AP",
    "Sikkim (SKM)":        "SKM",
    "Sonepat (SPT)":       "SPT",
    "AMT":                 "AP",
}

# ── Build lookup structures ──
_CODE_MAP = {}
_NAME_MAP = {}
_ALIAS_MAP = {}
_OPTIONS = []
_ACTIVE_CAMPUSES = []

for c in CAMPUSES:
    _CODE_MAP[c["code"].lower()] = c
    _NAME_MAP[c["name"].lower()] = c
    _OPTIONS.append((c["name"], c["name"]))
    if c["active"]:
        _ACTIVE_CAMPUSES.append(c)
    for alias in c["aliases"]:
        _ALIAS_MAP[alias.lower()] = c


# ── Public helpers ──


def get_campus_by_code(code: str) -> Optional[dict]:
    """Lookup a campus by its short code (e.g. 'KTR', 'VCH'). Case-insensitive."""
    if not code:
        return None
    c = _CODE_MAP.get(code.lower().strip())
    if c:
        return c
    # Try legacy mapping
    mapped = LEGACY_CAMPUS_MAP.get(code.strip())
    if mapped:
        return _CODE_MAP.get(mapped.lower())
    return None


def get_campus_by_name(name: str) -> Optional[dict]:
    """Lookup a campus by its full name (e.g. 'Kattankulathur (KTR)'). Case-insensitive."""
    if not name:
        return None
    c = _NAME_MAP.get(name.lower().strip())
    if c:
        return c
    # Try aliases
    return _ALIAS_MAP.get(name.lower().strip())


def get_campus_by_alias(text: str) -> Optional[dict]:
    """Lookup a campus by code, name, or alias. Supports partial matching for search."""
    if not text:
        return None
    t = text.lower().strip()
    c = _CODE_MAP.get(t) or _ALIAS_MAP.get(t) or _NAME_MAP.get(t)
    if c:
        return c
    for entry in CAMPUSES:
        if t in entry["code"].lower():
            return entry
        if t in entry["name"].lower():
            return entry
        for alias in entry["aliases"]:
            if t in alias.lower():
                return entry
    # Try legacy
    mapped = LEGACY_CAMPUS_MAP.get(text.strip())
    if mapped:
        return _CODE_MAP.get(mapped.lower())
    return None


def is_valid_campus(code_or_name: str) -> bool:
    """Check whether the given code or name corresponds to a known (active) campus."""
    return get_campus_by_alias(code_or_name) is not None


def get_campus_options(include_inactive: bool = False) -> list:
    """Return list of (value, label) tuples suitable for Django ChoiceField / Select."""
    src = CAMPUSES if include_inactive else _ACTIVE_CAMPUSES
    return [(c["name"], c["name"]) for c in src]


def get_campus_short_options(include_inactive: bool = False) -> list:
    """Return list of (code, label) tuples."""
    src = CAMPUSES if include_inactive else _ACTIVE_CAMPUSES
    return [(c["code"], f"{c['org']} {c['code']}") for c in src]


def get_campus_display_map() -> dict:
    """Return {full_name: short_code} mapping for database values."""
    m = {}
    for c in CAMPUSES:
        m[c["name"]] = c["code"]
    m.update(LEGACY_CAMPUS_MAP)
    return m


def get_all_campuses(include_inactive: bool = False) -> list:
    """Return the full campus list (each entry is a dict)."""
    return CAMPUSES if include_inactive else _ACTIVE_CAMPUSES


def get_org_groups() -> dict:
    """Return campuses grouped by organization: {'SRM': [...], 'VIT': [...], 'Amrita': [...]}"""
    groups = {}
    for c in CAMPUSES:
        groups.setdefault(c["org"], []).append(c)
    return groups


def get_campus_search_results(query: str) -> list:
    """Search campuses by code, name, or alias. Returns matching campus dicts."""
    if not query:
        return _ACTIVE_CAMPUSES
    q = query.lower().strip()
    results = []
    for c in _ACTIVE_CAMPUSES:
        if q in c["code"].lower():
            results.append(c)
        elif q in c["name"].lower():
            results.append(c)
        elif any(q in a.lower() for a in c["aliases"]):
            results.append(c)
    return results
