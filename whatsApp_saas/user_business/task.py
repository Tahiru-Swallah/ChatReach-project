from celery import shared_task
from django.utils import timezone
from user_authentication.models import CustomUser
from .models import ScheduledMessage, Notification
from django.contrib.contenttypes.models import ContentType
from .utils import send_whatsapp_message


@shared_task
def create_notification(user_id, title, message, notify_type='info', content_type_app_label=None, content_type_model=None, object_id=None):
    try:
        user = CustomUser.objects.get(id=user_id)
        notification = Notification.objects.create(
            user=user,
            title=title,
            messsage=message,
            type=notify_type
        )

        if content_type_app_label and content_type_model and object_id:
            content_type = ContentType.objects.get(app_label=content_type_app_label, model=content_type_model)
            notification.content_type = content_type
            notification.object_id = object_id
            notification.save()

    except Exception as e:
        print(f'Error Creating notification: {e}')

@shared_task
def process_schedule_message():
    messages = ScheduledMessage.objects.filter(
        scheduled_time__lte=timezone.now(),
        status='pending'
    )

    for message in messages:
        try:
            for contact in message.contacts.all():
                send_whatsapp_message(
                    phone_number=contact.phone_number,
                    message_text=message.message,
                    media_url=message.media.url if message.media else None
                )

            message.status = 'sent'
        except Exception as e:
            message.status = 'failed'
            message.error_message = str(e)

        message.save()
