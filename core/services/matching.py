"""
Compatibility matching engine.

Score(u, v) = Σ(w_f · sim_f(u_f, v_f)) / Σ(w_f)

Weights (sum = 1.0):
  budget        0.35
  destinations  0.25
  style         0.20
  duration      0.12
  accommodation 0.08
"""

WEIGHTS = {
    "budget": 0.35,
    "destinations": 0.25,
    "style": 0.20,
    "duration": 0.12,
    "accommodation": 0.08,
}

BUDGET_TIERS = ["economy", "mid", "luxury"]
DURATION_TIERS = ["weekend", "week", "twoweeks", "extended"]


def _ordinal_sim(val_a: str, val_b: str, tiers: list) -> float:
    """Exact = 1.0, adjacent = 0.5, two apart = 0.0."""
    try:
        dist = abs(tiers.index(val_a) - tiers.index(val_b))
    except ValueError:
        return 0.0
    return 1.0 if dist == 0 else (0.5 if dist == 1 else 0.0)


def _jaccard_sim(set_a: list, set_b: list) -> float:
    """Jaccard similarity for destination overlap."""
    a, b = set(set_a), set(set_b)
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _style_sim(style_a: str, style_b: str) -> float:
    if style_a == style_b:
        return 1.0
    if style_a == "mixed" or style_b == "mixed":
        return 0.6
    return 0.0


def compute_compatibility(pref_a: dict, pref_b: dict) -> float:
    """Return a score in [0, 1] between two user preference dicts."""
    sims = {
        "budget": _ordinal_sim(pref_a.get("budget", "mid"), pref_b.get("budget", "mid"), BUDGET_TIERS),
        "destinations": _jaccard_sim(pref_a.get("destinations", []), pref_b.get("destinations", [])),
        "style": _style_sim(pref_a.get("style", "mixed"), pref_b.get("style", "mixed")),
        "duration": _ordinal_sim(pref_a.get("duration", "week"), pref_b.get("duration", "week"), DURATION_TIERS),
        "accommodation": 1.0 if pref_a.get("accommodation") == pref_b.get("accommodation") else 0.0,
    }
    weighted_sum = sum(WEIGHTS[k] * v for k, v in sims.items())
    return round(weighted_sum, 3)


def get_ranked_matches(current_user, limit: int = 20, threshold: float = 0.0):
    """
    Return a list of (User, score) tuples ranked by compatibility,
    excluding users already acted on.
    """
    from django.contrib.auth.models import User
    from core.models import MatchAction, Profile

    try:
        my_profile = current_user.profile
    except Profile.DoesNotExist:
        return []

    # Users already acted on
    acted_ids = set(
        MatchAction.objects.filter(actor=current_user).values_list("target_id", flat=True)
    )
    acted_ids.add(current_user.pk)

    candidates = (
        User.objects.exclude(pk__in=acted_ids)
        .select_related("profile")
        .filter(profile__onboarding_complete=True)
    )

    my_pref = my_profile.preference_dict
    results = []
    for user in candidates:
        try:
            score = compute_compatibility(my_pref, user.profile.preference_dict)
        except Exception:
            score = 0.0
        if score >= threshold:
            results.append((user, score))

    results.sort(key=lambda x: x[1], reverse=True)
    return results[:limit]
