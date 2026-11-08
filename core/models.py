import json
import secrets
import string

from django.contrib.auth.models import User
from django.db import models


def _gen_invite_code():
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(10))


# ---------------------------------------------------------------------------
# User travel profile
# ---------------------------------------------------------------------------

class Profile(models.Model):
    BUDGET_CHOICES = [
        ("economy", "Economy"),
        ("mid", "Mid-range"),
        ("luxury", "Luxury"),
    ]
    STYLE_CHOICES = [
        ("adventure", "Adventure"),
        ("cultural", "Cultural"),
        ("relaxation", "Relaxation"),
        ("mixed", "Mixed"),
    ]
    DURATION_CHOICES = [
        ("weekend", "Weekend"),
        ("week", "One Week"),
        ("twoweeks", "Two Weeks"),
        ("extended", "Extended"),
    ]
    ACCOMMODATION_CHOICES = [
        ("hostel", "Hostel"),
        ("airbnb", "Airbnb"),
        ("hotel", "Hotel"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    bio = models.TextField(blank=True)
    avatar_url = models.URLField(blank=True)

    # Preference fields
    destinations = models.JSONField(default=list, blank=True)   # list of region strings
    style = models.CharField(max_length=20, choices=STYLE_CHOICES, default="mixed")
    budget = models.CharField(max_length=10, choices=BUDGET_CHOICES, default="mid")
    duration = models.CharField(max_length=20, choices=DURATION_CHOICES, default="week")
    accommodation = models.CharField(max_length=10, choices=ACCOMMODATION_CHOICES, default="hotel")
    travel_months = models.JSONField(default=list, blank=True)  # list of 1-12 ints

    onboarding_complete = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s profile"

    @property
    def preference_dict(self):
        return {
            "destinations": self.destinations or [],
            "style": self.style,
            "budget": self.budget,
            "duration": self.duration,
            "accommodation": self.accommodation,
        }


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

class MatchAction(models.Model):
    ACTION_CHOICES = [("like", "Like"), ("pass", "Pass")]

    actor = models.ForeignKey(User, on_delete=models.CASCADE, related_name="match_actions")
    target = models.ForeignKey(User, on_delete=models.CASCADE, related_name="match_targets")
    action = models.CharField(max_length=5, choices=ACTION_CHOICES)
    score = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("actor", "target")

    def __str__(self):
        return f"{self.actor} {self.action}d {self.target}"


# ---------------------------------------------------------------------------
# Trip groups
# ---------------------------------------------------------------------------

class TripGroup(models.Model):
    name = models.CharField(max_length=100)
    destination = models.CharField(max_length=200)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="owned_groups")
    invite_code = models.CharField(max_length=16, unique=True, default=_gen_invite_code)
    max_members = models.PositiveSmallIntegerField(default=12)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} → {self.destination}"

    @property
    def member_count(self):
        return self.memberships.count()


class GroupMember(models.Model):
    ROLE_CHOICES = [("owner", "Owner"), ("co-owner", "Co-Owner"), ("member", "Member")]

    group = models.ForeignKey(TripGroup, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="group_memberships")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="member")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("group", "user")

    def __str__(self):
        return f"{self.user.username} in {self.group.name} ({self.role})"


# ---------------------------------------------------------------------------
# Chat messages
# ---------------------------------------------------------------------------

class Message(models.Model):
    group = models.ForeignKey(TripGroup, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="messages")
    body = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sent_at"]

    def __str__(self):
        return f"[{self.group.name}] {self.sender.username}: {self.body[:40]}"

    def to_dict(self):
        return {
            "id": self.pk,
            "sender_id": self.sender_id,
            "sender_name": self.sender.username,
            "body": self.body,
            "sent_at": self.sent_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# Itinerary
# ---------------------------------------------------------------------------

class ItineraryDay(models.Model):
    group = models.ForeignKey(TripGroup, on_delete=models.CASCADE, related_name="itinerary_days")
    day_number = models.PositiveSmallIntegerField()
    date = models.DateField(null=True, blank=True)
    title = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["day_number"]
        unique_together = ("group", "day_number")

    def __str__(self):
        return f"{self.group.name} - Day {self.day_number}"


class ItineraryActivity(models.Model):
    day = models.ForeignKey(ItineraryDay, on_delete=models.CASCADE, related_name="activities")
    name = models.CharField(max_length=200)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    location_name = models.CharField(max_length=200, blank=True)
    location_lat = models.FloatField(null=True, blank=True)
    location_lng = models.FloatField(null=True, blank=True)
    notes = models.TextField(blank=True)
    assignee = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_activities"
    )
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "start_time"]

    def __str__(self):
        return f"{self.day} - {self.name}"

    def to_dict(self):
        return {
            "id": self.pk,
            "name": self.name,
            "start_time": self.start_time.strftime("%H:%M") if self.start_time else "",
            "end_time": self.end_time.strftime("%H:%M") if self.end_time else "",
            "location_name": self.location_name,
            "notes": self.notes,
            "assignee": self.assignee.username if self.assignee else "",
            "order": self.order,
        }


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------

class Expense(models.Model):
    SPLIT_CHOICES = [
        ("equal", "Equal"),
        ("exact", "Exact"),
        ("percentage", "Percentage"),
    ]

    group = models.ForeignKey(TripGroup, on_delete=models.CASCADE, related_name="expenses")
    paid_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="paid_expenses")
    description = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    expense_date = models.DateField()
    split_type = models.CharField(max_length=15, choices=SPLIT_CHOICES, default="equal")
    category = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.description} (${self.amount}) in {self.group.name}"


class ExpenseAllocation(models.Model):
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name="allocations")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="expense_allocations")
    amount_owed = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        unique_together = ("expense", "user")

    def __str__(self):
        return f"{self.user.username} owes ${self.amount_owed} for {self.expense.description}"


class BalanceLedger(models.Model):
    """Continuously updated net balance per (group, user) pair.
    Positive = others owe this user. Negative = this user owes others.
    """
    group = models.ForeignKey(TripGroup, on_delete=models.CASCADE, related_name="balances")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="balances")
    net_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        unique_together = ("group", "user")

    def __str__(self):
        return f"{self.user.username} in {self.group.name}: {self.net_balance}"


# ---------------------------------------------------------------------------
# Direct Messages (mutual matches only)
# ---------------------------------------------------------------------------

class DirectMessage(models.Model):
    sender    = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_dms")
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_dms")
    body      = models.TextField()
    sent_at   = models.DateTimeField(auto_now_add=True)
    read      = models.BooleanField(default=False)

    class Meta:
        ordering = ["sent_at"]

    def __str__(self):
        return f"{self.sender.username} → {self.recipient.username}: {self.body[:40]}"

    def to_dict(self):
        return {
            "id": self.pk,
            "sender_id": self.sender_id,
            "sender_name": self.sender.username,
            "body": self.body,
            "sent_at": self.sent_at.isoformat(),
            "read": self.read,
        }
