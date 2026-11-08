from datetime import date

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Expense, ItineraryActivity, Profile, TripGroup

DESTINATION_CHOICES = [
    ("europe", "Europe"),
    ("north_america", "North America"),
    ("south_america", "South America"),
    ("east_asia", "East Asia"),
    ("southeast_asia", "Southeast Asia"),
    ("south_asia", "South Asia"),
    ("middle_east", "Middle East"),
    ("africa", "Africa"),
    ("oceania", "Oceania"),
    ("caribbean", "Caribbean"),
]

MONTH_CHOICES = [
    (1, "January"), (2, "February"), (3, "March"),
    (4, "April"), (5, "May"), (6, "June"),
    (7, "July"), (8, "August"), (9, "September"),
    (10, "October"), (11, "November"), (12, "December"),
]


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class OnboardingForm(forms.ModelForm):
    destinations = forms.MultipleChoiceField(
        choices=DESTINATION_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Destination regions",
    )
    travel_months = forms.MultipleChoiceField(
        choices=MONTH_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Preferred travel months",
    )

    class Meta:
        model = Profile
        fields = ["bio", "style", "budget", "duration", "accommodation"]
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 3, "class": "form-control", "placeholder": "Tell other travelers about yourself..."}),
            "style": forms.Select(attrs={"class": "form-select"}),
            "budget": forms.Select(attrs={"class": "form-select"}),
            "duration": forms.Select(attrs={"class": "form-select"}),
            "accommodation": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial["destinations"] = self.instance.destinations or []
            self.initial["travel_months"] = [str(m) for m in (self.instance.travel_months or [])]


class GroupCreateForm(forms.ModelForm):
    class Meta:
        model = TripGroup
        fields = ["name", "destination", "start_date", "end_date", "max_members", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., Paris Spring 2026"}),
            "destination": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., Paris, France"}),
            "start_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "end_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "max_members": forms.NumberInput(attrs={"class": "form-control", "min": 2, "max": 12}),
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-control", "placeholder": "Describe your trip..."}),
        }


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ["description", "amount", "currency", "expense_date", "split_type", "category"]
        widgets = {
            "description": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., Hotel room"}),
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0", "placeholder": "0.00"}),
            "currency": forms.TextInput(attrs={"class": "form-control", "maxlength": "3", "value": "USD"}),
            "expense_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "split_type": forms.Select(attrs={"class": "form-select", "id": "id_split_type"}),
            "category": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., Food, Transport"}),
        }

    def __init__(self, *args, group=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.group = group
        self.fields["expense_date"].initial = date.today().isoformat()


class ActivityForm(forms.ModelForm):
    class Meta:
        model = ItineraryActivity
        fields = ["name", "start_time", "end_time", "location_name", "notes", "assignee"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Activity name"}),
            "start_time": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "end_time": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "location_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Location / place name"}),
            "notes": forms.Textarea(attrs={"rows": 2, "class": "form-control", "placeholder": "Optional notes..."}),
            "assignee": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, group=None, **kwargs):
        super().__init__(*args, **kwargs)
        if group:
            from .models import GroupMember
            member_ids = GroupMember.objects.filter(group=group).values_list("user_id", flat=True)
            self.fields["assignee"].queryset = User.objects.filter(pk__in=member_ids)
            self.fields["assignee"].empty_label = "— No assignee —"
