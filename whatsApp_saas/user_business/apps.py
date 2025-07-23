# user_business/apps.py

from django.apps import AppConfig

class UserBusinessConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'user_business'

    def ready(self):
        import threading

        def setup_periodic_task():
            from django_celery_beat.models import PeriodicTask, IntervalSchedule
            from django.db.utils import OperationalError, ProgrammingError
            import json

            try:
                schedule, _ = IntervalSchedule.objects.get_or_create(
                    every=1,
                    period=IntervalSchedule.MINUTES,
                )

                if not PeriodicTask.objects.filter(name='Send Scheduled Message').exists():
                    PeriodicTask.objects.create(
                        interval=schedule,
                        name='Send Scheduled Message',
                        task='user_business.tasks.process_schedule_message',
                        args=json.dumps([]),
                    )
            except (OperationalError, ProgrammingError):
                # Handle cases where DB isn't ready yet (e.g., during migrations)
                pass

        # Use a thread to delay execution until apps are ready
        threading.Thread(target=setup_periodic_task).start()
