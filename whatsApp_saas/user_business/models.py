from django.db import models
from user_authentication.models import CustomUser, Business
from uuid import uuid4
from phonenumber_field.modelfields import PhoneNumberField
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

def validate_e164_phone_number(value):
    """
    Validates that the phone number is in international E.164 format (e.g. +233241234567 or 233241234567).
    """
    clean_val = value.strip().lstrip('+')
    if not re.match(r'^\d{10,15}$', clean_val):
        raise ValidationError(
            _('%(value)s is not a valid E.164 phone number.'),
            params={'value': value},
        )
class CustomerContact(models.Model):
    """
    Stores customer phone numbers, tags, and audience attributes per business tenant.
    """
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='customer_contacts')

    name = models.CharField(max_length=255, blank=True, null=True, help_text=_("Contact full name or display label"))

    phone_number = PhoneNumberField(db_index=True, help_text="Enter phone number in E.164 format (e.g. +233241234567 or 233241234567)")

    email = models.EmailField(blank=True, null=True)

    tag = models.JSONField(
        default=list, 
        blank=True, 
        help_text=_("List of audience tags e.g. ['VIP', 'Youth Group', 'Donors', 'Wholesale']")
    )

    # Enterprise & Meta Compliance
    is_opted_in = models.BooleanField(
        default=True, 
        db_index=True, 
        help_text=_("Explicit consent flag for Meta policy & Ghana Data Protection compliance")
    )

    # Custom Metadata (Dynamic Fields like location, total spent, last purchase date)
    attributes = models.JSONField(
        default=dict, 
        blank=True, 
        help_text=_("Key-value pair custom attributes for template variable interpolation e.g. {'city': 'Kumasi'}")
    )

    created_on = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_on']
        constraints = [
            models.UniqueConstraint(
                fields=['business', 'phone_number'], 
                name='unique_phone_per_business'
            )
        ]

    def __str__(self):
        return f"{self.name or 'Unnamed'} ({self.phone_number})"

class WhatsAppTemplate(models.Model):
    class Category(models.TextChoices):
        MARKETING = 'MARKETING', 'Marketing'
        UTILITY = 'UTILITY', 'Utility'
        AUTHENTICATION = 'AUTHENTICATION', 'Authentication'

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        PENDING = 'PENDING', 'Pending Approval'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
        PAUSED = 'PAUSED', 'Paused'
        DISABLED = 'DISABLED', 'Disabled'

    class Language(models.TextChoices):
        ENGLISH_US = 'en_US', 'English (US)'
        ENGLISH_UK = 'en_GB', 'English (UK)'
        FRENCH = 'fr', 'French'
        SPANISH = 'es', 'Spanish'

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    business = models.ForeignKey(
        Business, # Adjust model reference if needed
        on_delete=models.CASCADE,
        related_name='whatsapp_templates'
    )
    
    name = models.CharField(
        max_length=512, 
        help_text="Lowercase template identifier required by Meta (e.g. order_update_v1)"
    )
    category = models.CharField(max_length=32, choices=Category.choices, default=Category.UTILITY)
    language = models.CharField(max_length=10, choices=Language.choices, default=Language.ENGLISH_US)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DRAFT)
    
    # Template Structure
    body_text = models.TextField(help_text="Body content with optional variables like {{1}}, {{2}}")
    header_type = models.CharField(max_length=20, default='NONE', choices=[
        ('NONE', 'None'), ('TEXT', 'Text'), ('IMAGE', 'Image'), ('DOCUMENT', 'Document')
    ])
    header_text = models.CharField(max_length=60, blank=True, null=True)
    footer_text = models.CharField(max_length=60, blank=True, null=True)
    
    # Meta Graph Identifiers
    meta_template_id = models.CharField(max_length=128, blank=True, null=True)
    rejection_reason = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('business', 'name', 'language')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.language}) - {self.status}"    

class ScheduledMessage(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="scheduled_messages")
    message = models.TextField()
    media = models.FileField(upload_to='message_media/', null=True, blank=True)
    contacts = models.ManyToManyField(CustomerContact, related_name='scheduled_messages')
    scheduled_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.message[:30]} ({self.status})"

class TemplateCategory(models.Model):
    CATEGORY_CHOICES = [
        ('marketing', 'Marketing'),
        ('reminder', 'Reminder'),
        ('update', 'Update'),
        ('support', 'Support'),
        ('custom', 'Custom'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name = models.CharField(max_length=100, choices=CATEGORY_CHOICES)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='template_categories')
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = ['name', 'user']
        verbose_name_plural = 'Template Categories'

    def __str__(self):
        return self.name
class MessageTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    title = models.CharField(max_length=100)
    template_name = models.CharField(max_length=100, help_text="Infobip registered template name")
    language = models.CharField(max_length=10, default="en")
    placeholders = models.JSONField(blank=True, null=True, help_text="List of placeholder values for the template")
    category = models.ForeignKey(TemplateCategory, on_delete=models.SET_NULL, null=True, blank=True)
    attachment = models.FileField(upload_to='attachments/', null=True, blank=True)
    external_link = models.URLField(blank=True, null=True)
    is_favorite = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at'])
        ]

    def __str__(self):
        return self.title
    
class Notification(models.Model):
    TYPE_CHOICE = [
        ('info', 'Info'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('error', 'Error'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notification')
    title = models.CharField(max_length=255)
    message = models.TextField()
    type = models.CharField(max_length=100, choices=TYPE_CHOICE, default='info')
    is_read = models.BooleanField(default=False)

    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.UUIDField(null=True, blank=True)
    related_object = GenericForeignKey('content_type', 'object_id')

    created_at = models.DateTimeField(auto_now_add=True)


    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.first_name} - {self.title}'