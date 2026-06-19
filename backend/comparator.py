"""
Laptop comparison engine — scores two laptops against each other
weighted by use-case priorities.
"""
import pandas as pd

# ── GPU tier scoring ──────────────────────────────────────────────────────────
GPU_TIERS = {
    # NVIDIA RTX 40-series
    "rtx 4090": 10, "rtx 4080": 9, "rtx 4070 ti": 9, "rtx 4070": 8,
    "rtx 4060 ti": 7, "rtx 4060": 7,
    # NVIDIA RTX 30-series
    "rtx 3080 ti": 9, "rtx 3080": 8, "rtx 3070 ti": 8, "rtx 3070": 7,
    "rtx 3060": 6, "rtx 3050 ti": 5, "rtx 3050": 5,
    # NVIDIA GTX
    "gtx 1660": 4, "gtx 1650": 3,
    # AMD
    "rx 7900": 10, "rx 7800": 9, "rx 7700": 8, "rx 7600": 7,
    "rx 6800": 8, "rx 6700": 7, "rx 6600": 6, "rx 6500": 4,
    # Apple
    "m3 max": 9, "m3 pro": 8, "m3": 7, "m2 max": 8, "m2 pro": 7, "m2": 6,
    "m1 max": 7, "m1 pro": 6, "m1": 5,
    # Integrated
    "iris xe": 2, "intel uhd": 1, "integrated": 1,
}

# ── Use-case weight profiles ──────────────────────────────────────────────────
USE_CASE_WEIGHTS = {
    "gaming": {
        "gpu": 0.35, "cpu": 0.25, "ram": 0.20, "storage": 0.10, "value": 0.10
    },
    "video editing": {
        "ram": 0.30, "cpu": 0.25, "gpu": 0.20, "storage": 0.15, "value": 0.10
    },
    "programming": {
        "cpu": 0.30, "ram": 0.30, "storage": 0.20, "value": 0.15, "gpu": 0.05
    },
    "data science": {
        "ram": 0.35, "cpu": 0.30, "storage": 0.20, "gpu": 0.10, "value": 0.05
    },
    "office": {
        "value": 0.30, "ram": 0.25, "cpu": 0.20, "storage": 0.15, "gpu": 0.10
    },
    "student": {
        "value": 0.35, "ram": 0.20, "cpu": 0.20, "storage": 0.15, "gpu": 0.10
    },
    "general": {
        "cpu": 0.25, "ram": 0.25, "value": 0.25, "storage": 0.15, "gpu": 0.10
    },
}


def _gpu_score(gpu: str) -> float:
    if not gpu or str(gpu).lower() in ("nan", "none", ""):
        return 1.0
    g = str(gpu).lower()
    for key, score in GPU_TIERS.items():
        if key in g:
            return float(score)
    return 3.0  # unknown discrete GPU


def _cpu_tier(cpu: str) -> int:
    c = str(cpu).lower()
    if any(k in c for k in ["i9", "ryzen 9", "ultra 9", "m3 max", "m2 max", "m1 max"]):
        return 4
    if any(k in c for k in ["i7", "ryzen 7", "ultra 7", "m3 pro", "m2 pro", "m1 pro"]):
        return 3
    if any(k in c for k in ["i5", "ryzen 5", "ultra 5", "m3", "m2", "m1"]):
        return 2
    if any(k in c for k in ["i3", "ryzen 3", "celeron", "pentium", "n-series"]):
        return 1
    return 2  # default


def _normalise(value: float, min_val: float, max_val: float) -> float:
    if max_val == min_val:
        return 0.5
    return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))


def score_laptop(row: dict, weights: dict, ref_max: dict) -> float:
    """Score a single laptop dict against a set of weights."""
    ram     = float(row.get("RAM", 0) or 0)
    storage = float(row.get("Storage", 0) or 0)
    price   = float(row.get("Price_LKR", 1) or 1)
    gpu     = str(row.get("GPU", ""))
    cpu     = str(row.get("CPU", ""))

    scores = {
        "cpu":     _normalise(_cpu_tier(cpu),    1, 4),
        "ram":     _normalise(ram,               0, ref_max["ram"]),
        "storage": _normalise(storage,           0, ref_max["storage"]),
        "gpu":     _normalise(_gpu_score(gpu),   1, 10),
        "value":   _normalise(1_000_000 / max(price, 1), 0, ref_max["value"]),
    }

    total = sum(weights.get(k, 0) * v for k, v in scores.items())
    return round(total, 4)


def _display_winner(laptop_a: dict, laptop_b: dict) -> str:
    """Larger screen size wins on Display dimension."""
    try:
        sa = float(str(laptop_a.get("Screen", 0) or 0).split()[0])
        sb = float(str(laptop_b.get("Screen", 0) or 0).split()[0])
    except (ValueError, TypeError):
        return "tie"
    if sa > sb:  return "A"
    if sb > sa:  return "B"
    return "tie"


def _price_winner(laptop_a: dict, laptop_b: dict) -> str:
    """Lower price wins on Price dimension."""
    try:
        pa = float(laptop_a.get("Price_LKR", 0) or 0)
        pb = float(laptop_b.get("Price_LKR", 0) or 0)
    except (ValueError, TypeError):
        return "tie"
    if pa < pb:  return "A"
    if pb < pa:  return "B"
    return "tie"


def compare_two(laptop_a: dict, laptop_b: dict, use_case: str = "general") -> dict:
    """
    Compare two laptops and return scores, winner, category breakdown, and pros/cons.
    Now includes Display and Price in the per-dimension breakdown for the UI.
    """
    uc = use_case.lower().strip()
    weights = USE_CASE_WEIGHTS.get(uc, USE_CASE_WEIGHTS["general"])

    # Reference max values for normalisation
    ref_max = {
        "ram":     max(float(laptop_a.get("RAM", 1) or 1),     float(laptop_b.get("RAM", 1) or 1)),
        "storage": max(float(laptop_a.get("Storage", 1) or 1), float(laptop_b.get("Storage", 1) or 1)),
        "value":   1_000_000 / min(
            float(laptop_a.get("Price_LKR", 1) or 1),
            float(laptop_b.get("Price_LKR", 1) or 1)
        ),
    }

    score_a = score_laptop(laptop_a, weights, ref_max)
    score_b = score_laptop(laptop_b, weights, ref_max)

    near_tie = abs(score_a - score_b) < 0.05
    winner = "tie" if near_tie else ("A" if score_a > score_b else "B")

    # Per-category advantage flags (scored dimensions)
    def _cat_winner(cat):
        sa = score_laptop(laptop_a, {cat: 1.0}, ref_max)
        sb = score_laptop(laptop_b, {cat: 1.0}, ref_max)
        if sa > sb:  return "A"
        if sb > sa:  return "B"
        return "tie"

    category_breakdown = {
        cat: _cat_winner(cat) for cat in ["cpu", "ram", "storage", "gpu", "value"]
    }

    # Add display and price as visual-only dimensions
    category_breakdown["display"] = _display_winner(laptop_a, laptop_b)
    category_breakdown["price"]   = _price_winner(laptop_a, laptop_b)

    pros_a, cons_a, pros_b, cons_b = [], [], [], []
    labels = {"cpu": "CPU", "ram": "RAM", "storage": "Storage", "gpu": "GPU",
              "value": "Value for Money", "display": "Display", "price": "Price"}
    for cat, cat_winner in category_breakdown.items():
        label = labels.get(cat, cat.upper())
        if cat_winner == "A":
            pros_a.append(label)
            cons_b.append(label)
        elif cat_winner == "B":
            pros_b.append(label)
            cons_a.append(label)

    return {
        "score_a":             score_a,
        "score_b":             score_b,
        "winner":              winner,
        "near_tie":            near_tie,
        "use_case":            uc,
        "weights":             weights,
        "category_breakdown":  category_breakdown,
        "pros_a":              pros_a,
        "cons_a":              cons_a,
        "pros_b":              pros_b,
        "cons_b":              cons_b,
    }
