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
    {"code": "KTR", "name": "SRM Kattankulathur (KTR)", "org": "SRM", "college": "SRM Institute of Science and Technology", "aliases": ["Kattankulathur", "SRM KTR", "SRM Kattankulathur", "ktr"], "active": True},
    {"code": "RMP", "name": "SRM Ramapuram (RMP)",       "org": "SRM", "college": "SRM Institute of Science and Technology", "aliases": ["Ramapuram", "SRM Ramapuram", "rmp"], "active": True},
    {"code": "VDP", "name": "SRM Vadapalani (VDP)",       "org": "SRM", "college": "SRM Institute of Science and Technology", "aliases": ["Vadapalani", "SRM Vadapalani", "vdp"], "active": True},
    {"code": "ESW", "name": "SRM Eswari (ESW)",           "org": "SRM", "college": "SRM Institute of Science and Technology", "aliases": ["Eswari", "SRM Eswari", "Easwari", "esw"], "active": True},
    {"code": "AP",  "name": "SRM Amaravati (AP)",         "org": "SRM", "college": "SRM Institute of Science and Technology", "aliases": ["Amaravati", "SRM AP", "SRM Amaravati", "AMT", "ap"], "active": True},
    {"code": "NCR", "name": "SRM Delhi NCR",              "org": "SRM", "college": "SRM Institute of Science and Technology", "aliases": ["NCR", "SRM Delhi NCR", "NCR Modinagar", "ncr"], "active": True},
    {"code": "SPT", "name": "SRM Sonepat (SPT)",          "org": "SRM", "college": "SRM Institute of Science and Technology", "aliases": ["Sonepat", "SRM Sonepat", "spt"], "active": True},
    {"code": "SKM", "name": "SRM Sikkim (SKM)",           "org": "SRM", "college": "SRM Institute of Science and Technology", "aliases": ["Sikkim", "SRM Sikkim", "skm"], "active": True},
    {"code": "TCY", "name": "SRM Tiruchirappalli (TCY)",   "org": "SRM", "college": "SRM Institute of Science and Technology", "aliases": ["Tiruchirappalli", "SRM Tiruchirappalli", "TCY", "tcy"], "active": True},

    # ── Amrita ──
    {"code": "ACB", "name": "Amrita Coimbatore (ACB)",      "org": "Amrita", "college": "Amrita Vishwa Vidyapeetham", "aliases": ["Coimbatore", "Amrita Coimbatore", "acb"], "active": True},
    {"code": "AKO", "name": "Amrita Kochi (AKO)",           "org": "Amrita", "college": "Amrita Vishwa Vidyapeetham", "aliases": ["Kochi", "Amrita Kochi", "ako"], "active": True},
    {"code": "AAP", "name": "Amrita Amritapuri (AAP)",      "org": "Amrita", "college": "Amrita Vishwa Vidyapeetham", "aliases": ["Amritapuri", "Amrita Amritapuri", "aap"], "active": True},
    {"code": "ABL", "name": "Amrita Bengaluru (ABL)",       "org": "Amrita", "college": "Amrita Vishwa Vidyapeetham", "aliases": ["Bengaluru", "Amrita Bengaluru", "Bangalore", "abl"], "active": True},
    {"code": "AMY", "name": "Amrita Mysuru (AMY)",          "org": "Amrita", "college": "Amrita Vishwa Vidyapeetham", "aliases": ["Mysuru", "Amrita Mysuru", "Mysore", "amy"], "active": True},
    {"code": "ACH", "name": "Amrita Chennai (ACH)",         "org": "Amrita", "college": "Amrita Vishwa Vidyapeetham", "aliases": ["Chennai", "Amrita Chennai", "ach"], "active": True},
    {"code": "AAM", "name": "Amrita Amaravati (AAM)",       "org": "Amrita", "college": "Amrita Vishwa Vidyapeetham", "aliases": ["Amaravati", "Amrita Amaravati", "aam"], "active": True},
    {"code": "AFD", "name": "Amrita Faridabad (AFD)",       "org": "Amrita", "college": "Amrita Vishwa Vidyapeetham", "aliases": ["Faridabad", "Amrita Faridabad", "afd"], "active": True},
    {"code": "ANG", "name": "Amrita Nagercoil (ANG)",       "org": "Amrita", "college": "Amrita Vishwa Vidyapeetham", "aliases": ["Nagercoil", "Amrita Nagercoil", "ang"], "active": True},
    {"code": "AHD", "name": "Amrita Haridwar (AHD)",        "org": "Amrita", "college": "Amrita Vishwa Vidyapeetham", "aliases": ["Haridwar", "Amrita Haridwar", "ahd"], "active": True},
    {"code": "AON", "name": "Amrita Online (AON)",          "org": "Amrita", "college": "Amrita Vishwa Vidyapeetham", "aliases": ["Online", "Amrita Online", "aon"], "active": True},

    # ── VIT ──
    {"code": "VLR", "name": "VIT Vellore (VLR)",            "org": "VIT",  "college": "Vellore Institute of Technology", "aliases": ["Vellore", "VIT Vellore", "vlr"], "active": True},
    {"code": "VCH", "name": "VIT Chennai (VCH)",            "org": "VIT",  "college": "Vellore Institute of Technology", "aliases": ["Chennai", "VIT Chennai", "vch"], "active": True},
    {"code": "VBP", "name": "VIT Bhopal (VBP)",             "org": "VIT",  "college": "Vellore Institute of Technology", "aliases": ["Bhopal", "VIT Bhopal", "vbp"], "active": True},
    {"code": "VAP", "name": "VIT AP Amaravati (VAP)",       "org": "VIT",  "college": "Vellore Institute of Technology", "aliases": ["VIT AP", "VIT Amaravati", "Amaravati", "vap"], "active": True},
    {"code": "VBL", "name": "VIT Bangalore (VBL)",          "org": "VIT",  "college": "Vellore Institute of Technology", "aliases": ["Bangalore", "VIT Bangalore", "Bengaluru", "vbl"], "active": True},
]

# Legacy DB value → canonical code mapping
# Old SRM campus names stored in the database that need to map to current codes
LEGACY_CAMPUS_MAP = {
    "Kattankulathur (KTR)": "KTR",
    "KTR Campus":             "KTR",
    "NCR Campus":             "NCR",
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


def get_campus_names_by_org(org: str) -> list:
    """Return all canonical campus names for a given org (case-insensitive)."""
    org_lower = org.lower()
    return [c["name"] for c in CAMPUSES if c["org"].lower() == org_lower]


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


# ── SEO URL slugs (used for /campus/<slug>/ landing pages) ──

CAMPUS_SEO_SLUGS = {
    "KTR": "srm-ktr",
    "RMP": "srm-ramapuram",
    "VDP": "srm-vadapalani",
    "ESW": "srm-eswari",
    "AP": "srm-amaravati",
    "NCR": "srm-delhi-ncr",
    "SPT": "srm-sonepat",
    "SKM": "srm-sikkim",
    "TCY": "srm-tiruchirappalli",
    "ACB": "amrita-coimbatore",
    "AKO": "amrita-kochi",
    "AAP": "amrita-amritapuri",
    "ABL": "amrita-bengaluru",
    "AMY": "amrita-mysuru",
    "ACH": "amrita-chennai",
    "AAM": "amrita-amaravati",
    "AFD": "amrita-faridabad",
    "ANG": "amrita-nagercoil",
    "AHD": "amrita-haridwar",
    "AON": "amrita-online",
    "VLR": "vit-vellore",
    "VCH": "vit-chennai",
    "VBP": "vit-bhopal",
    "VAP": "vit-amaravati",
    "VBL": "vit-bangalore",
}

ORG_SEO_SLUGS = {
    "srm": "SRM",
    "vit": "VIT",
    "amrita": "Amrita",
}

_SEO_SLUG_TO_CAMPUS = {v: _CODE_MAP[k.lower()] for k, v in CAMPUS_SEO_SLUGS.items()}


def get_campus_seo_slug(campus: dict) -> str:
    """Return the SEO-friendly URL slug for a campus dict."""
    return CAMPUS_SEO_SLUGS.get(campus["code"], f"{campus['org'].lower()}-{campus['code'].lower()}")


def get_campus_by_seo_slug(slug: str) -> Optional[dict]:
    """Lookup a campus by its SEO slug (e.g. 'srm-ktr', 'vit-vellore')."""
    if not slug:
        return None
    return _SEO_SLUG_TO_CAMPUS.get(slug.lower().strip())


def get_org_by_seo_slug(slug: str) -> Optional[str]:
    """Return org name ('SRM', 'VIT', 'Amrita') for an org landing slug, or None."""
    if not slug:
        return None
    return ORG_SEO_SLUGS.get(slug.lower().strip())


def get_campuses_by_org(org: str) -> list:
    """Return active campus dicts for an organization."""
    org_lower = org.lower()
    return [c for c in _ACTIVE_CAMPUSES if c["org"].lower() == org_lower]
