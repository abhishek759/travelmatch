from django.contrib import admin

from .models import (
    BalanceLedger, DirectMessage, Expense, ExpenseAllocation,
    GroupMember, ItineraryActivity, ItineraryDay,
    MatchAction, Message, Profile, TripGroup,
)

admin.site.register(Profile)
admin.site.register(MatchAction)
admin.site.register(TripGroup)
admin.site.register(GroupMember)
admin.site.register(Message)
admin.site.register(ItineraryDay)
admin.site.register(ItineraryActivity)
admin.site.register(Expense)
admin.site.register(ExpenseAllocation)
admin.site.register(BalanceLedger)
admin.site.register(DirectMessage)
