from django.contrib import admin
from django.urls import include, path

from core import views as v

urlpatterns = [
    path("admin/", admin.site.urls),
    # Auth (built-in login/password reset)
    path("accounts/", include("django.contrib.auth.urls")),
    path("accounts/signup/", v.signup_view, name="signup"),
    path("accounts/logout/", v.logout_view, name="logout"),

    # Core pages
    path("", v.home, name="home"),
    path("dashboard/", v.dashboard, name="dashboard"),
    path("onboarding/", v.onboarding, name="onboarding"),
    path("profile/", v.profile_view, name="profile"),

    # Matches
    path("matches/", v.match_feed, name="match_feed"),
    path("matches/<int:user_id>/action/", v.match_action, name="match_action"),
    path("matches/mutual/", v.mutual_matches, name="mutual_matches"),

    # Direct Messages
    path("messages/", v.dm_inbox, name="dm_inbox"),
    path("messages/<int:user_id>/", v.dm_conversation, name="dm_conversation"),
    path("messages/<int:user_id>/send/", v.dm_send, name="dm_send"),
    path("messages/<int:user_id>/poll/", v.dm_poll, name="dm_poll"),

    # Groups
    path("groups/", v.group_list, name="group_list"),
    path("groups/create/", v.group_create, name="group_create"),
    path("groups/<int:pk>/", v.group_detail, name="group_detail"),
    path("groups/<int:pk>/join/", v.group_join, name="group_join"),
    path("groups/<int:pk>/leave/", v.group_leave, name="group_leave"),
    path("groups/<int:pk>/invite/", v.group_invite, name="group_invite"),
    path("groups/<int:pk>/members/<int:user_id>/remove/", v.group_remove_member, name="group_remove_member"),

    # Chat (AJAX)
    path("groups/<int:pk>/chat/messages/", v.chat_messages, name="chat_messages"),
    path("groups/<int:pk>/chat/send/", v.chat_send, name="chat_send"),

    # Itinerary (AJAX)
    path("groups/<int:pk>/itinerary/days/add/", v.itinerary_add_day, name="itinerary_add_day"),
    path("groups/<int:pk>/itinerary/days/<int:day_id>/activities/add/", v.itinerary_add_activity, name="itinerary_add_activity"),
    path("groups/<int:pk>/itinerary/activities/<int:activity_id>/delete/", v.itinerary_delete_activity, name="itinerary_delete_activity"),
    path("groups/<int:pk>/itinerary/reorder/", v.itinerary_reorder, name="itinerary_reorder"),

    # Expenses (AJAX)
    path("groups/<int:pk>/expenses/add/", v.expense_create, name="expense_create"),
    path("groups/<int:pk>/expenses/<int:expense_id>/delete/", v.expense_delete, name="expense_delete"),
    path("groups/<int:pk>/expenses/settlement/", v.settlement_view, name="settlement_view"),
]
