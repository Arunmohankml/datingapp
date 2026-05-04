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
# BAD WORD LIST  (English + transliterated Tamil/Hindi abuse/sexual/hate terms)
# ─────────────────────────────────────────────────────────────────────────────
BAD_WORDS = {
    # English profanity / sexual
    "fuck", "fucked", "fucker", "fucking", "fuk", "f*ck", "f**k",
    "shit", "bullshit", "shithead", "bastard", "bitch", "bitches",
    "asshole", "ass", "arse", "dick", "dicks", "cock", "cocks",
    "pussy", "pussies", "cunt", "slut", "whore", "hoe", "hoes",
    "nigger", "nigga", "faggot", "fag", "retard", "retarded",
    "rape", "raped", "rapist", "molest", "molested", "pedophile",
    "penis", "vagina", "boob", "boobs", "tit", "tits", "nude", "nudes",
    "naked", "sex", "sexy", "sexting", "porn", "porno", "pornography",
    "masturbate", "masturbation", "horny", "boner", "blowjob",
    "handjob", "threesome", "gangbang", "lust", "lusty",
    "prostitute", "escort", "hookup", "hook-up", "one night stand",
    # Hate / threats
    "kill", "killing", "murder", "terrorist", "terrorism", "suicide",
    "bomb", "explode", "shoot", "shooter", "hang", "lynch", "die bitch",
    "kys", "kill yourself", "go kill",
    # Transliterated Tamil abuse
    "punda", "pundai", "thevdiya", "thevidiya", "myiru", "otha", "oothu",
    "sunni", "koothi", "soothu", "naaiku", "naaye", "pottai", "kena",
    "sakkadam", "oombu", "oombu", "kaai", "lavada", "lavde", "lavdya",
    # Transliterated Hindi abuse
    "madarchod", "behenchod", "chutiya", "chut", "lund", "gaand",
    "bhosdike", "bhosdi", "randi", "suar", "harami", "haramzada",
    "kamina", "kamini", "sala", "saali", "kutte", "kamine",
    # Variations / leet speak patterns handled by normalize()
}

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


def _normalize(text: str) -> str:
    """Lowercase, strip accents, remove punctuation/spaces for comparison."""
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _word_set(text: str) -> set:
    return set(_normalize(text).split())


# ─────────────────────────────────────────────────────────────────────────────
# 1. BAD WORD FILTER
# ─────────────────────────────────────────────────────────────────────────────
def check_bad_words(text: str):
    """
    Returns (True, matched_word) if bad content found, else (False, '').
    Uses word-boundary matching and leet-speak normalization.
    """
    norm = _normalize(text)
    words = norm.split()

    # Direct word check
    for word in words:
        if word in BAD_WORDS:
            return True, word

    # Substring check for compounds (e.g. "what_the_fuck")
    for bw in BAD_WORDS:
        if len(bw) > 4 and bw in norm:
            return True, bw

    # Leet-speak: replace common substitutions and re-check
    leet = norm.replace("0", "o").replace("1", "i").replace("3", "e").replace("@", "a").replace("$", "s")
    for word in leet.split():
        if word in BAD_WORDS:
            return True, word

    return False, ""


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
