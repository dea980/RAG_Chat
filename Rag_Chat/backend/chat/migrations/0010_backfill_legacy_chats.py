"""Backfill: legacy Chat rows -> Conversation + Message pairs.

For each user with Chat rows:
- Create one Conversation titled "Legacy".
- For each Chat (oldest first):
  - Insert a user Message (content_text = question_text, created_at = Q time).
  - Insert an assistant Message (content_text = response_text, created_at = same).
- Set Conversation.created_at = earliest Q; last_message_at = latest Q.

Reversible — backward op deletes only the "Legacy" conversations.
"""
from django.db import migrations


def forward(apps, schema_editor):
    Chat = apps.get_model("chat", "Chat")
    Conversation = apps.get_model("chat", "Conversation")
    Message = apps.get_model("chat", "Message")

    user_ids = (
        Chat.objects.values_list("user_id", flat=True).distinct()
    )
    created_convs = 0
    created_msgs = 0
    for uid in user_ids:
        chats = Chat.objects.filter(user_id=uid).order_by("question_created_datetime")
        if not chats.exists():
            continue
        first = chats.first()
        last = chats.last()
        conv = Conversation.objects.create(
            user_id=uid,
            title="Legacy",
        )
        # Adjust timestamps by direct UPDATE (auto_now_add already fired).
        Conversation.objects.filter(pk=conv.pk).update(
            created_at=first.question_created_datetime,
            last_message_at=last.question_created_datetime,
        )
        created_convs += 1
        for c in chats:
            u = Message.objects.create(
                conversation=conv,
                role="user",
                content_text=c.question_text or "",
            )
            Message.objects.filter(pk=u.pk).update(created_at=c.question_created_datetime)
            a = Message.objects.create(
                conversation=conv,
                role="assistant",
                content_text=c.response_text or "",
                data_id=c.data_id if c.data_id else None,
            )
            Message.objects.filter(pk=a.pk).update(created_at=c.question_created_datetime)
            created_msgs += 2
    print(f"  backfill: {created_convs} Conversations, {created_msgs} Messages")


def backward(apps, schema_editor):
    Conversation = apps.get_model("chat", "Conversation")
    deleted, _ = Conversation.objects.filter(title="Legacy").delete()
    print(f"  reverse backfill: removed {deleted} Legacy conversations + cascaded messages")


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0009_conversation_message_attachment_and_more"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
