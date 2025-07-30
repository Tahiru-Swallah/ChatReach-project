from django.db.models.signals import post_save
from .models import CustomUser, BusinessProfile
from django.dispatch import receiver

@receiver(post_save, sender=CustomUser)
def create_business_profile(sender, instance, created, **kwargs):
    if created:
        BusinessProfile.objects.create(user=instance)