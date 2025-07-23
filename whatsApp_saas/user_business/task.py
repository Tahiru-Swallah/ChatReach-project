from celery import shared_task
from .models import ScheduledMessage
from django.utils import timezone
from .utils import send_message


@shared_task
def process_schedule_message():
    messages = ScheduledMessage.objects.filter(
        scheduled_time__lte = timezone.now(),
        status = 'pending'
    )

    for message in messages:
        try:
            send_message(message)
            message.status = 'sent'
        except Exception as e:
            message.status = 'failed'
            message.error_message = str(e)
            
        message.save()