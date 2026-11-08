import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_GET

from .forms import (
    GroupCreateForm,
    OnboardingForm,
    SignUpForm,
    ExpenseForm,
    ActivityForm,
)
from .models import (
    BalanceLedger,
    DirectMessage,
    Expense,
    ExpenseAllocation,
    GroupMember,
    ItineraryActivity,
    ItineraryDay,
    MatchAction,
    Message,
    Profile,
    TripGroup,
)
from .services.matching import get_ranked_matches, compute_compatibility
from .services.settlement import compute_group_settlement


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "home.html")


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            Profile.objects.create(user=user)
            login(request, user)
            return redirect("onboarding")
    else:
        form = SignUpForm()
    return render(request, "auth/signup.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("home")


# ---------------------------------------------------------------------------
# Onboarding
# ---------------------------------------------------------------------------

@login_required
def onboarding(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        form = OnboardingForm(request.POST, instance=profile)
        if form.is_valid():
            p = form.save(commit=False)
            p.destinations = request.POST.getlist("destinations")
            p.travel_months = [int(m) for m in request.POST.getlist("travel_months") if m.isdigit()]
            p.onboarding_complete = True
            p.save()
            messages.success(request, "Profile saved! Here are your travel matches.")
            return redirect("match_feed")
    else:
        form = OnboardingForm(instance=profile)
    return render(request, "auth/onboarding.html", {"form": form})


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@login_required
def dashboard(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if not profile.onboarding_complete:
        return redirect("onboarding")

    my_groups = TripGroup.objects.filter(memberships__user=request.user).distinct()
    recent_matches = [(u, round(s * 100, 1)) for u, s in get_ranked_matches(request.user, limit=3)]

    # Mutual matches
    i_liked  = set(MatchAction.objects.filter(actor=request.user, action="like").values_list("target_id", flat=True))
    liked_me = set(MatchAction.objects.filter(target=request.user, action="like").values_list("actor_id", flat=True))
    mutual_ids = i_liked & liked_me

    mutual_users_qs = User.objects.filter(pk__in=mutual_ids).select_related("profile")
    mutual_with_scores = []
    my_pref = profile.preference_dict
    for u in mutual_users_qs:
        try:
            sc = round(compute_compatibility(my_pref, u.profile.preference_dict) * 100, 1)
        except Exception:
            sc = 0.0
        mutual_with_scores.append((u, sc))
    mutual_with_scores.sort(key=lambda x: x[1], reverse=True)

    unread_dm_count = DirectMessage.objects.filter(recipient=request.user, read=False).count()

    return render(request, "dashboard.html", {
        "profile": profile,
        "my_groups": my_groups,
        "recent_matches": recent_matches,
        "mutual_with_scores": mutual_with_scores[:6],
        "mutual_count": len(mutual_ids),
        "unread_dm_count": unread_dm_count,
        "groups_count": my_groups.count(),
    })


# ---------------------------------------------------------------------------
# Match feed
# ---------------------------------------------------------------------------

@login_required
def match_feed(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if not profile.onboarding_complete:
        return redirect("onboarding")
    ranked = [(u, round(s * 100, 1)) for u, s in get_ranked_matches(request.user, limit=20)]
    return render(request, "matches/match_feed.html", {"ranked": ranked, "profile": profile})


@login_required
@require_POST
def match_action(request, user_id):
    action = request.POST.get("action")
    if action not in ("like", "pass"):
        return JsonResponse({"error": "Invalid action"}, status=400)

    target = get_object_or_404(User, pk=user_id)
    if target == request.user:
        return JsonResponse({"error": "Cannot act on yourself"}, status=400)

    profile, _       = Profile.objects.get_or_create(user=request.user)
    target_profile, _ = Profile.objects.get_or_create(user=target)
    score = compute_compatibility(profile.preference_dict, target_profile.preference_dict)

    MatchAction.objects.update_or_create(
        actor=request.user, target=target,
        defaults={"action": action, "score": score},
    )

    # Detect mutual match
    is_mutual = False
    if action == "like":
        is_mutual = MatchAction.objects.filter(actor=target, target=request.user, action="like").exists()

    return JsonResponse({
        "ok": True,
        "action": action,
        "target": target.username,
        "mutual": is_mutual,
        "target_id": target.pk,
    })


@login_required
def mutual_matches(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if not profile.onboarding_complete:
        return redirect("onboarding")

    i_liked  = set(MatchAction.objects.filter(actor=request.user, action="like").values_list("target_id", flat=True))
    liked_me = set(MatchAction.objects.filter(target=request.user, action="like").values_list("actor_id", flat=True))
    mutual_ids = i_liked & liked_me

    mutual_users_qs = User.objects.filter(pk__in=mutual_ids).select_related("profile")
    my_pref = profile.preference_dict
    result = []
    for u in mutual_users_qs:
        try:
            sc = round(compute_compatibility(my_pref, u.profile.preference_dict) * 100, 1)
        except Exception:
            sc = 0.0
        unread = DirectMessage.objects.filter(sender=u, recipient=request.user, read=False).count()
        # Latest DM for preview
        latest_dm = DirectMessage.objects.filter(
            Q(sender=request.user, recipient=u) | Q(sender=u, recipient=request.user)
        ).order_by("-sent_at").first()
        result.append({"user": u, "score": sc, "unread": unread, "latest_dm": latest_dm})

    result.sort(key=lambda x: x["score"], reverse=True)
    return render(request, "matches/mutual_matches.html", {"mutual_matches": result})


@login_required
def profile_view(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        form = OnboardingForm(request.POST, instance=profile)
        if form.is_valid():
            p = form.save(commit=False)
            p.destinations = request.POST.getlist("destinations")
            p.travel_months = [int(m) for m in request.POST.getlist("travel_months") if m.isdigit()]
            p.onboarding_complete = True
            p.save()
            messages.success(request, "Travel preferences updated.")
            return redirect("profile")
    else:
        form = OnboardingForm(instance=profile)
    return render(request, "auth/profile.html", {"form": form, "profile": profile})


# ---------------------------------------------------------------------------
# Direct Messages
# ---------------------------------------------------------------------------

@login_required
def dm_inbox(request):
    sent_to       = DirectMessage.objects.filter(sender=request.user).values_list("recipient_id", flat=True)
    received_from = DirectMessage.objects.filter(recipient=request.user).values_list("sender_id", flat=True)
    partner_ids   = set(list(sent_to) + list(received_from))

    conversations = []
    for pid in partner_ids:
        try:
            partner = User.objects.select_related("profile").get(pk=pid)
        except User.DoesNotExist:
            continue
        latest = DirectMessage.objects.filter(
            Q(sender=request.user, recipient=partner) | Q(sender=partner, recipient=request.user)
        ).order_by("-sent_at").first()
        unread = DirectMessage.objects.filter(sender=partner, recipient=request.user, read=False).count()
        conversations.append({"partner": partner, "latest": latest, "unread": unread})

    conversations.sort(key=lambda x: x["latest"].sent_at if x["latest"] else datetime.min, reverse=True)
    return render(request, "messages/inbox.html", {"conversations": conversations})


@login_required
def dm_conversation(request, user_id):
    other_user = get_object_or_404(User, pk=user_id)

    # Only mutual matches can DM each other
    i_liked   = MatchAction.objects.filter(actor=request.user, target=other_user, action="like").exists()
    they_liked = MatchAction.objects.filter(actor=other_user, target=request.user, action="like").exists()
    if not (i_liked and they_liked):
        messages.error(request, "You can only message mutual matches.")
        return redirect("mutual_matches")

    # Mark incoming messages as read
    DirectMessage.objects.filter(sender=other_user, recipient=request.user, read=False).update(read=True)

    msgs = DirectMessage.objects.filter(
        Q(sender=request.user, recipient=other_user) | Q(sender=other_user, recipient=request.user)
    ).order_by("sent_at")

    try:
        their_profile = other_user.profile
    except Profile.DoesNotExist:
        their_profile = None

    return render(request, "messages/conversation.html", {
        "other_user": other_user,
        "their_profile": their_profile,
        "messages_list": msgs,
    })


@login_required
@require_POST
def dm_send(request, user_id):
    other_user = get_object_or_404(User, pk=user_id)
    i_liked    = MatchAction.objects.filter(actor=request.user, target=other_user, action="like").exists()
    they_liked = MatchAction.objects.filter(actor=other_user, target=request.user, action="like").exists()
    if not (i_liked and they_liked):
        return JsonResponse({"error": "Not a mutual match"}, status=403)

    body = request.POST.get("body", "").strip()
    if not body:
        return JsonResponse({"error": "Empty message"}, status=400)
    if len(body) > 2000:
        return JsonResponse({"error": "Message too long"}, status=400)

    msg = DirectMessage.objects.create(sender=request.user, recipient=other_user, body=body)
    return JsonResponse({"ok": True, "message": msg.to_dict()})


@login_required
def dm_poll(request, user_id):
    other_user = get_object_or_404(User, pk=user_id)
    since_id   = int(request.GET.get("since", 0))

    msgs = DirectMessage.objects.filter(
        Q(sender=request.user, recipient=other_user) | Q(sender=other_user, recipient=request.user),
        pk__gt=since_id,
    ).order_by("sent_at")

    msgs.filter(sender=other_user).update(read=True)
    return JsonResponse({"messages": [m.to_dict() for m in msgs]})


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------

@login_required
def group_list(request):
    my_groups  = TripGroup.objects.filter(memberships__user=request.user).distinct()
    all_groups = TripGroup.objects.exclude(memberships__user=request.user).distinct()
    return render(request, "groups/group_list.html", {
        "my_groups": my_groups,
        "all_groups": all_groups,
    })


@login_required
def group_create(request):
    if request.method == "POST":
        form = GroupCreateForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            group.owner = request.user
            group.save()
            GroupMember.objects.create(group=group, user=request.user, role="owner")
            messages.success(request, f'Group "{group.name}" created!')
            return redirect("group_detail", pk=group.pk)
    else:
        form = GroupCreateForm()
    return render(request, "groups/group_form.html", {"form": form, "action": "Create"})


@login_required
def group_detail(request, pk):
    group      = get_object_or_404(TripGroup, pk=pk)
    membership = GroupMember.objects.filter(group=group, user=request.user).first()
    is_member  = membership is not None
    is_owner   = group.owner == request.user

    members        = GroupMember.objects.filter(group=group).select_related("user")
    itinerary_days = ItineraryDay.objects.filter(group=group).prefetch_related("activities__assignee")
    expenses       = Expense.objects.filter(group=group).select_related("paid_by").order_by("-created_at")
    balances       = {b.user: b.net_balance for b in BalanceLedger.objects.filter(group=group).select_related("user")}
    settlement     = compute_group_settlement(group) if is_member else []

    return render(request, "groups/group_detail.html", {
        "group": group,
        "membership": membership,
        "is_member": is_member,
        "is_owner": is_owner,
        "members": members,
        "itinerary_days": itinerary_days,
        "expenses": expenses,
        "balances": balances,
        "settlement": settlement,
        "expense_form": ExpenseForm(group=group),
        "activity_form": ActivityForm(group=group),
    })


@login_required
@require_POST
def group_join(request, pk):
    group = get_object_or_404(TripGroup, pk=pk)
    code  = request.POST.get("invite_code", "").strip()
    if group.member_count >= group.max_members:
        messages.error(request, "This group is full.")
        return redirect("group_list")
    if code != group.invite_code:
        messages.error(request, "Invalid invite code.")
        return redirect("group_list")
    GroupMember.objects.get_or_create(group=group, user=request.user, defaults={"role": "member"})
    messages.success(request, f'You joined "{group.name}"!')
    return redirect("group_detail", pk=group.pk)


@login_required
@require_POST
def group_leave(request, pk):
    group = get_object_or_404(TripGroup, pk=pk)
    if group.owner == request.user:
        messages.error(request, "Owners cannot leave their group.")
        return redirect("group_detail", pk=pk)
    GroupMember.objects.filter(group=group, user=request.user).delete()
    messages.success(request, f'You left "{group.name}".')
    return redirect("group_list")


@login_required
@require_POST
def group_invite(request, pk):
    group = get_object_or_404(TripGroup, pk=pk)
    if group.owner != request.user:
        return JsonResponse({"error": "Only the owner can invite."}, status=403)
    username = request.POST.get("username", "").strip()
    try:
        invitee = User.objects.get(username=username)
    except User.DoesNotExist:
        messages.error(request, f'User "{username}" not found.')
        return redirect("group_detail", pk=pk)
    if group.member_count >= group.max_members:
        messages.error(request, "Group is full.")
        return redirect("group_detail", pk=pk)
    _, created = GroupMember.objects.get_or_create(group=group, user=invitee, defaults={"role": "member"})
    if created:
        messages.success(request, f"{username} added to the group.")
    else:
        messages.info(request, f"{username} is already a member.")
    return redirect("group_detail", pk=pk)


@login_required
@require_POST
def group_remove_member(request, pk, user_id):
    group  = get_object_or_404(TripGroup, pk=pk)
    if group.owner != request.user:
        messages.error(request, "Only the owner can remove members.")
        return redirect("group_detail", pk=pk)
    target = get_object_or_404(User, pk=user_id)
    if target == group.owner:
        messages.error(request, "Cannot remove the group owner.")
        return redirect("group_detail", pk=pk)
    GroupMember.objects.filter(group=group, user=target).delete()
    messages.success(request, f"{target.username} removed.")
    return redirect("group_detail", pk=pk)


# ---------------------------------------------------------------------------
# Chat (AJAX polling)
# ---------------------------------------------------------------------------

@login_required
def chat_messages(request, pk):
    group = get_object_or_404(TripGroup, pk=pk)
    if not GroupMember.objects.filter(group=group, user=request.user).exists():
        return JsonResponse({"error": "Forbidden"}, status=403)
    since_id = int(request.GET.get("since", 0))
    msgs = Message.objects.filter(group=group, pk__gt=since_id).select_related("sender")[:100]
    return JsonResponse({"messages": [m.to_dict() for m in msgs]})


@login_required
@require_POST
def chat_send(request, pk):
    group = get_object_or_404(TripGroup, pk=pk)
    if not GroupMember.objects.filter(group=group, user=request.user).exists():
        return JsonResponse({"error": "Forbidden"}, status=403)
    body = request.POST.get("body", "").strip()
    if not body:
        return JsonResponse({"error": "Empty message"}, status=400)
    if len(body) > 2000:
        return JsonResponse({"error": "Message too long"}, status=400)
    msg = Message.objects.create(group=group, sender=request.user, body=body)
    return JsonResponse({"ok": True, "message": msg.to_dict()})


# ---------------------------------------------------------------------------
# Itinerary
# ---------------------------------------------------------------------------

@login_required
@require_POST
def itinerary_add_day(request, pk):
    group = get_object_or_404(TripGroup, pk=pk)
    if not GroupMember.objects.filter(group=group, user=request.user).exists():
        return JsonResponse({"error": "Forbidden"}, status=403)
    last_day   = ItineraryDay.objects.filter(group=group).order_by("-day_number").first()
    day_number = (last_day.day_number + 1) if last_day else 1
    day_date_str = request.POST.get("date", "")
    day_date = None
    if day_date_str:
        try:
            day_date = date.fromisoformat(day_date_str)
        except ValueError:
            pass
    title = request.POST.get("title", f"Day {day_number}")
    day   = ItineraryDay.objects.create(group=group, day_number=day_number, date=day_date, title=title)
    return JsonResponse({"ok": True, "day_id": day.pk, "day_number": day.day_number, "title": day.title})


@login_required
@require_POST
def itinerary_add_activity(request, pk, day_id):
    group = get_object_or_404(TripGroup, pk=pk)
    day   = get_object_or_404(ItineraryDay, pk=day_id, group=group)
    if not GroupMember.objects.filter(group=group, user=request.user).exists():
        return JsonResponse({"error": "Forbidden"}, status=403)
    name = request.POST.get("name", "").strip()
    if not name:
        return JsonResponse({"error": "Activity name required"}, status=400)
    start_time = end_time = None
    try:
        from datetime import time as dtime
        s = request.POST.get("start_time", "")
        e = request.POST.get("end_time", "")
        if s: start_time = dtime.fromisoformat(s)
        if e: end_time   = dtime.fromisoformat(e)
    except ValueError:
        pass
    assignee_id = request.POST.get("assignee_id")
    assignee = None
    if assignee_id:
        try:
            assignee = User.objects.get(pk=int(assignee_id))
        except (User.DoesNotExist, ValueError):
            pass
    last_order = ItineraryActivity.objects.filter(day=day).order_by("-order").first()
    order      = (last_order.order + 1) if last_order else 0
    activity   = ItineraryActivity.objects.create(
        day=day, name=name, start_time=start_time, end_time=end_time,
        location_name=request.POST.get("location_name", ""),
        notes=request.POST.get("notes", ""), assignee=assignee, order=order,
    )
    return JsonResponse({"ok": True, "activity": activity.to_dict()})


@login_required
@require_POST
def itinerary_delete_activity(request, pk, activity_id):
    group    = get_object_or_404(TripGroup, pk=pk)
    activity = get_object_or_404(ItineraryActivity, pk=activity_id, day__group=group)
    if not GroupMember.objects.filter(group=group, user=request.user).exists():
        return JsonResponse({"error": "Forbidden"}, status=403)
    activity.delete()
    return JsonResponse({"ok": True})


@login_required
@require_POST
def itinerary_reorder(request, pk):
    group = get_object_or_404(TripGroup, pk=pk)
    if not GroupMember.objects.filter(group=group, user=request.user).exists():
        return JsonResponse({"error": "Forbidden"}, status=403)
    try:
        data       = json.loads(request.body)
        ordered_ids = data.get("ordered_ids", [])
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    for idx, aid in enumerate(ordered_ids):
        ItineraryActivity.objects.filter(pk=aid, day__group=group).update(order=idx)
    return JsonResponse({"ok": True})


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------

@login_required
@require_POST
def expense_create(request, pk):
    group = get_object_or_404(TripGroup, pk=pk)
    if not GroupMember.objects.filter(group=group, user=request.user).exists():
        return JsonResponse({"error": "Forbidden"}, status=403)
    try:
        description     = request.POST.get("description", "").strip()
        amount          = Decimal(request.POST.get("amount", "0"))
        currency        = request.POST.get("currency", "USD").strip().upper()[:3]
        expense_date    = date.fromisoformat(request.POST.get("expense_date", str(date.today())))
        split_type      = request.POST.get("split_type", "equal")
        paid_by_id      = int(request.POST.get("paid_by_id", request.user.pk))
        paid_by         = User.objects.get(pk=paid_by_id)
        category        = request.POST.get("category", "").strip()
    except (InvalidOperation, ValueError, User.DoesNotExist) as e:
        return JsonResponse({"error": str(e)}, status=400)

    member_ids = [m.user_id for m in GroupMember.objects.filter(group=group)]

    if split_type == "equal":
        share  = amount / len(member_ids)
        splits = {uid: share for uid in member_ids}
    elif split_type == "exact":
        splits = {}
        for uid in member_ids:
            try:
                splits[uid] = Decimal(request.POST.get(f"amount_{uid}", "0"))
            except InvalidOperation:
                splits[uid] = Decimal("0")
    elif split_type == "percentage":
        splits = {}
        for uid in member_ids:
            pct = Decimal(request.POST.get(f"pct_{uid}", "0"))
            splits[uid] = amount * pct / 100
    else:
        return JsonResponse({"error": "Invalid split type"}, status=400)

    split_sum = sum(splits.values())
    if abs(split_sum - amount) > Decimal("0.02"):
        return JsonResponse({"error": f"Split amounts ({split_sum}) must sum to total ({amount})"}, status=400)

    with transaction.atomic():
        expense = Expense.objects.create(
            group=group, paid_by=paid_by, description=description,
            amount=amount, currency=currency, expense_date=expense_date,
            split_type=split_type, category=category,
        )
        for uid, owed in splits.items():
            ExpenseAllocation.objects.create(expense=expense, user_id=uid, amount_owed=owed)
            delta = (amount - owed) if uid == paid_by.pk else -owed
            ledger, _ = BalanceLedger.objects.get_or_create(group=group, user_id=uid, defaults={"net_balance": 0})
            ledger.net_balance = Decimal(str(ledger.net_balance)) + delta
            ledger.save()

    return JsonResponse({"ok": True, "expense_id": expense.pk})


@login_required
@require_POST
def expense_delete(request, pk, expense_id):
    group   = get_object_or_404(TripGroup, pk=pk)
    expense = get_object_or_404(Expense, pk=expense_id, group=group)
    if not (group.owner == request.user or expense.paid_by == request.user):
        return JsonResponse({"error": "Forbidden"}, status=403)
    with transaction.atomic():
        for alloc in expense.allocations.all():
            delta  = -(expense.amount - alloc.amount_owed) if alloc.user_id == expense.paid_by_id else alloc.amount_owed
            ledger = BalanceLedger.objects.filter(group=group, user_id=alloc.user_id).first()
            if ledger:
                ledger.net_balance = Decimal(str(ledger.net_balance)) + delta
                ledger.save()
        expense.delete()
    return JsonResponse({"ok": True})


@login_required
def settlement_view(request, pk):
    group = get_object_or_404(TripGroup, pk=pk)
    if not GroupMember.objects.filter(group=group, user=request.user).exists():
        return JsonResponse({"error": "Forbidden"}, status=403)
    transfers = compute_group_settlement(group)
    result = [
        {"from": t["from_user"].username if t["from_user"] else "?",
         "to": t["to_user"].username if t["to_user"] else "?",
         "amount": t["amount"]}
        for t in transfers
    ]
    return JsonResponse({"transfers": result})
