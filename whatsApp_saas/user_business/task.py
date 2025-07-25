from celery import shared_task
from django.utils import timezone
from .models import ScheduledMessage
from .utils import send_whatsapp_message


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
