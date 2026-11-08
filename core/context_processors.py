from .models import DirectMessage


def unread_dms(request):
    if request.user.is_authenticated:
        count = DirectMessage.objects.filter(recipient=request.user, read=False).count()
        return {"unread_dm_count": count}
    return {"unread_dm_count": 0}
