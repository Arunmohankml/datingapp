"""
home/moderation.py
──────────────────
Confession moderation engine for SRM Sparks.
Handles: bad words, near-duplicate detection, name detection, rate limiting.
"""

import re
import unicodedata
from django.utils import timezone
from datetime import timedelta

# ─────────────────────────────────────────────────────────────────────────────
# 1. ADVANCED BAD WORD FILTER TECHNOLOGY
# ─────────────────────────────────────────────────────────────────────────────

BLOCKED_WORDS = [
    # User provided words
    "fuck", "fucking", "fucker", "fucked", "fk", "fuk", "fck",
    "shit", "shitty", "bullshit",
    "ass", "asshole", "bitch", "bitches", "bastard",
    "dick", "cock", "pussy", "cunt", "slut", "whore",
    "sex", "sexy", "horny", "nude", "nudes", "porn",
    "boobs", "boob", "tits", "tit", "butt",
    "motherfucker", "mf", "wtf", "damn",
    # Transliterated Tamil abuse
    "punda", "pundai", "thevdiya", "thevidiya", "myiru", "otha", "oothu",
    "sunni", "koothi", "soothu", "naaiku", "naaye", "pottai", "kena",
    "sakkadam", "oombu", "kaai", "lavada", "lavde", "lavdya",
    # Transliterated Hindi abuse
    "madarchod", "behenchod", "chutiya", "chut", "lund", "gaand",
    "bhosdike", "bhosdi", "randi", "suar", "harami", "haramzada",
    "kamina", "kamini", "sala", "saali", "kutte", "kamine",
]

STRICT_WORDS = {"ass", "sex", "tit", "butt", "fk", "mf", "wtf"}

LEET_MAP = str.maketrans({
    "0": "o",
    "1": "i",
    "!": "i",
    "3": "e",
    "4": "a",
    "@": "a",
    "5": "s",
    "$": "s",
    "7": "t",
    "+": "t",
    "8": "b",
})


def normalize_text_tech(text: str) -> str:
    text = text.lower().translate(LEET_MAP)
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text


def remove_repeats(text: str) -> str:
    return re.sub(r"(.)\1+", r"\1", text)


def compact_text(text: str) -> str:
    text = normalize_text_tech(text)
    text = re.sub(r"[^a-z]", "", text)
    return remove_repeats(text)


def normalized_words(text: str) -> list[str]:
    text = normalize_text_tech(text)
    text = re.sub(r"[^a-z\s]", " ", text)
    words = text.split()
    return [remove_repeats(word) for word in words]


def check_bad_words(message: str) -> dict:
    """
    Advanced detection using compact text comparison and normalized word sets.
    Returns: {"safe": bool, "detected": list, "status": str}
    """
    compact = compact_text(message)
    words = normalized_words(message)

    detected = []

    for bad_word in BLOCKED_WORDS:
        clean_bad = compact_text(bad_word)

        if clean_bad in STRICT_WORDS:
            # For short/strict words, only flag if it's a standalone word
            if clean_bad in words:
                detected.append(bad_word)
        else:
            # For others, check both standalone and substring (compact)
            if clean_bad in words or clean_bad in compact:
                detected.append(bad_word)

    detected = sorted(set(detected))

    return {
        "safe": len(detected) == 0,
        "detected": detected,
        "status": "verified" if len(detected) == 0 else "warning"
    }


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS FOR DUPLICATE DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Compatible normalization for duplicate detection."""
    return normalize_text_tech(text)


def _word_set(text: str) -> set:
    """Compatible word set for Jaccard similarity."""
    return set(normalized_words(text))


# Common Indian first names for name-detection heuristic
COMMON_NAMES = {
    "arun", "arjun", "ajay", "akash", "aman", "aditya", "anand", "ankit",
    "ankita", "ananya", "anjali", "aishwarya", "bharath", "bala",
    "charan", "deepak", "divya", "dinesh", "dhanush", "ganesh",
    "harish", "hari", "ismail", "ishaan", "jagan", "jayesh", "karthik",
    "kavya", "krishna", "keerthi", "kumar", "lakshmi", "lavanya",
    "manoj", "meera", "mohan", "mugil", "nithya", "nithin", "nisha",
    "pooja", "priya", "priyanka", "rahul", "rajan", "rajesh", "ram",
    "ramya", "ranjith", "ravi", "rohith", "sai", "santhosh", "sandhya",
    "saranya", "selvam", "senthil", "shiva", "shruti", "siddharth",
    "sneha", "subash", "sudha", "suresh", "swetha", "tamil", "thiru",
    "usha", "venkat", "vijay", "vikram", "vinoth", "vishal", "yuvan",
}


# ─────────────────────────────────────────────────────────────────────────────
# 2. DUPLICATE / NEAR-DUPLICATE DETECTION
# ─────────────────────────────────────────────────────────────────────────────
def check_duplicate(text: str, fingerprint: str, user=None) -> bool:
    """
    Returns True if a near-identical confession exists from the same
    fingerprint (or user) in the last 24 hours.
    Jaccard similarity >= 0.70 => duplicate.
    """
    from .models import Confession

    since = timezone.now() - timedelta(hours=24)
    qs = Confession.objects.filter(created_at__gte=since)

    if fingerprint:
        qs = qs.filter(poster_fingerprint=fingerprint)
    elif user and user.is_authenticated:
        qs = qs.filter(user=user)
    else:
        return False

    new_words = _word_set(text)
    if not new_words:
        return False

    for c in qs.only("content")[:20]:  # check last 20 for performance
        existing_words = _word_set(c.content)
        if not existing_words:
            continue
        intersection = len(new_words & existing_words)
        union = len(new_words | existing_words)
        similarity = intersection / union if union else 0
        if similarity >= 0.70:
            return True

    return False


# ─────────────────────────────────────────────────────────────────────────────
# 3. NAME MENTION DETECTION
# ─────────────────────────────────────────────────────────────────────────────
_FULL_NAME_PATTERN = re.compile(
    r"\b([A-Z][a-z]{2,})\s+([A-Z][a-z]{2,})\b"  # "First Last" capitalized pair
)

def check_name_mention(text: str) -> bool:
    """
    Returns True if confession likely mentions a real person by name.
    Strategy:
    1. "First Last" capitalized pattern (two consecutive Title Case words)
    2. Known common name followed by a second word (e.g. "Ranjith anna")
    """
    # Pattern 1: two consecutive title-case words = probable full name
    if _FULL_NAME_PATTERN.search(text):
        return True

    # Pattern 2: known first name standalone in middle of sentence
    words = text.lower().split()
    for i, w in enumerate(words):
        clean = re.sub(r"[^a-z]", "", w)
        if clean in COMMON_NAMES and i > 0:  # not the very first word (some sentences start with "Kavya is...")
            # Only flag if there's context around it (not just a name alone)
            if len(words) >= 5:
                return True

    return False


# ─────────────────────────────────────────────────────────────────────────────
# 4. RATE LIMITING
# ─────────────────────────────────────────────────────────────────────────────
RATE_LIMIT_COUNT = 3       # max confessions
RATE_LIMIT_MINUTES = 10    # per N minutes


def check_rate_limit(fingerprint: str, ip: str = "") -> tuple:
    """
    Returns (allowed: bool, retry_after_seconds: int).
    Checks fingerprint; if not available, falls back to IP.
    """
    from .models import ConfessionRateLimit

    since = timezone.now() - timedelta(minutes=RATE_LIMIT_MINUTES)
    identifier = fingerprint or ip

    if not identifier:
        return True, 0

    recent = ConfessionRateLimit.objects.filter(
        identifier=identifier,
        submitted_at__gte=since
    ).order_by("submitted_at")

    count = recent.count()
    if count >= RATE_LIMIT_COUNT:
        oldest = recent.first()
        retry_at = oldest.submitted_at + timedelta(minutes=RATE_LIMIT_MINUTES)
        wait = max(0, int((retry_at - timezone.now()).total_seconds()))
        return False, wait

    return True, 0


def record_rate_limit(fingerprint: str, ip: str = ""):
    """Record a new submission for rate limiting."""
    from .models import ConfessionRateLimit

    identifier = fingerprint or ip
    if identifier:
        ConfessionRateLimit.objects.create(identifier=identifier)

    # Cleanup old records (> 24h) to keep table lean
    ConfessionRateLimit.objects.filter(
        submitted_at__lt=timezone.now() - timedelta(hours=24)
    ).delete()


# ─────────────────────────────────────────────────────────────────────────────
# 5. SHADOW BAN CHECK
# ─────────────────────────────────────────────────────────────────────────────
def check_shadow_ban(fingerprint: str) -> bool:
    """Returns True if fingerprint is shadow-banned (soft silent ban)."""
    from .models import BannedIdentifier
    if not fingerprint:
        return False
    return BannedIdentifier.objects.filter(
        fingerprint=fingerprint, is_shadow_ban=True
    ).exists()
