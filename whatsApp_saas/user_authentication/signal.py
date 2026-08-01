from django.db.models.signals import post_save
from .models import CustomUser, Business
from django.dispatch import receiver

@receiver(post_save, sender=CustomUser)
def create_business_profile(sender, instance, created, **kwargs):
    if created:
        Business.objects.create(owner=instance)