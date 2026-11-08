"""
Greedy debt-simplification algorithm.

Given a dict of {user_id: net_balance} where Σ(balances) ≈ 0:
  positive net_balance → others owe this user
  negative net_balance → this user owes others

Returns a list of transfer dicts: {from_user, to_user, amount}
The algorithm produces at most n-1 transfers for n members.
"""

EPSILON = 0.005


def compute_settlement(balances: dict) -> list:
    """
    Args:
        balances: dict mapping user_id (int) → net_balance (float/Decimal)
    Returns:
        list of {"from_user": id, "to_user": id, "amount": float}
    """
    creditors = []  # [(user_id, amount_owed_to_them)]
    debtors = []    # [(user_id, amount_they_owe)]

    for uid, bal in balances.items():
        bal = float(bal)
        if bal > EPSILON:
            creditors.append([uid, bal])
        elif bal < -EPSILON:
            debtors.append([uid, -bal])

    creditors.sort(key=lambda x: x[1], reverse=True)
    debtors.sort(key=lambda x: x[1], reverse=True)

    transfers = []
    ci, di = 0, 0

    while ci < len(creditors) and di < len(debtors):
        cred_id, credit = creditors[ci]
        debt_id, debt = debtors[di]
        amount = min(credit, debt)
        transfers.append({
            "from_user": debt_id,
            "to_user": cred_id,
            "amount": round(amount, 2),
        })
        creditors[ci][1] -= amount
        debtors[di][1] -= amount
        if creditors[ci][1] < EPSILON:
            ci += 1
        if debtors[di][1] < EPSILON:
            di += 1

    return transfers


def compute_group_settlement(group):
    """Convenience wrapper: takes a TripGroup and returns transfers with User objects."""
    from core.models import BalanceLedger
    from django.contrib.auth.models import User

    ledger = BalanceLedger.objects.filter(group=group).select_related("user")
    balances = {entry.user_id: float(entry.net_balance) for entry in ledger}

    raw = compute_settlement(balances)

    user_map = {u.pk: u for u in User.objects.filter(pk__in=balances.keys())}
    result = []
    for t in raw:
        result.append({
            "from_user": user_map.get(t["from_user"]),
            "to_user": user_map.get(t["to_user"]),
            "amount": t["amount"],
        })
    return result
