from django.db import models
from user_authentication.models import CustomUser, BusinessProfile
from uuid import uuid4
from phonenumber_field.modelfields import PhoneNumberField


class CustomerContact(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='customer_contacts')
    name = models.CharField(max_length=255)
    phone_number = PhoneNumberField()
    email = models.EmailField(blank=True, null=True)
    tag = models.CharField(max_length=100, blank=True, null=True)  # for grouping contacts
    created_on = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'phone_number')  # prevent duplicates for same user
        ordering = ['-created_on']

    def __str__(self):
        return f"{self.name} ({self.phone_number})"
    

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
    title = models.CharField(max_length=150)
    
    # The message with placeholders
    content = models.TextField(
        help_text="Use variables like {{name}}, {{date}}, {{business_name}} for dynamic content"
    )
    
    category = models.ForeignKey(TemplateCategory, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Allow upload of images, PDFs, documents
    attachment = models.FileField(upload_to='template_attachments/', null=True, blank=True)

    # Optional website, WhatsApp, or booking link
    external_link = models.URLField(null=True, blank=True, help_text="Optional link to website or landing page")

    is_favorite = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title