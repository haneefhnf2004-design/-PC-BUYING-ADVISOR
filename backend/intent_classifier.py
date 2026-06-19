"""
Intent classification — determines what the user wants to do.
"""

INTENT_PATTERNS = {
    "compare": [
        "compare", "vs", "versus", "difference between", "which is better",
        "better than", "or", "against", "between"
    ],
    "recommend": [
        "recommend", "suggest", "best", "good", "top", "for gaming",
        "for programming", "for office", "for video editing", "for data science",
        "need a laptop", "looking for", "want", "buy"
    ],
    "explain": [
        "why", "explain", "how", "what makes", "reason", "tell me about",
        "describe", "clarify", "breakdown", "elaborate"
    ],
    "upgrade": [
        "upgrade", "future proof", "expand", "add more", "compatible",
        "can i upgrade", "improve", "ram upgrade", "storage upgrade"
    ],
    "budget": [
        "under", "below", "within", "affordable", "cheap", "budget",
        "lkr", "rupees", "price range", "cost"
    ],
    "general": []  # catch-all
}


def detect_intent(query: str) -> str:
    """
    Returns the primary detected intent as a string key.
    Falls back to "general" if no match.
    """
    q = query.lower()

    # Priority: compare > recommend > explain > upgrade > budget > general
    for intent_name in ["compare", "recommend", "explain", "upgrade", "budget"]:
        keywords = INTENT_PATTERNS[intent_name]
        if any(kw in q for kw in keywords):
            return intent_name

    return "general"


def extract_comparison_names(query: str) -> tuple:
    """
    Tries to extract two laptop names from a comparison query.
    Returns (name_a, name_b) or (None, None) if parsing fails.
    """
    q = query.lower()

    # Look for patterns like "X vs Y", "X versus Y", "compare X and Y"
    for delimiter in [" vs ", " versus ", " or ", " against "]:
        if delimiter in q:
            parts = q.split(delimiter, 1)
            if len(parts) == 2:
                # Remove common words
                for noise in ["compare", "between", "the"]:
                    parts = [p.replace(noise, "") for p in parts]
                a = parts[0].strip()
                b = parts[1].strip()
                if a and b:
                    return (a, b)
            break

    # Pattern: "compare X and Y"
    if "compare" in q and " and " in q:
        start_idx = q.find("compare") + len("compare")
        chunk = q[start_idx:].strip()
        if " and " in chunk:
            parts = chunk.split(" and ", 1)
            a = parts[0].strip()
            b = parts[1].strip()
            if a and b:
                return (a, b)

    return (None, None)
