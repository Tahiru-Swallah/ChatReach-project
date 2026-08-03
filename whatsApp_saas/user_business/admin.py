from django.contrib import admin
from .models import CustomerContact, WhatsAppTemplate, ScheduledMessage, MessageTemplate, TemplateCategory, Notification

@admin.register(CustomerContact)
class CustomerContactAdmin(admin.ModelAdmin):
    list_display = ['business', 'name', 'phone_number', 'email', 'tag', 'is_opted_in', 'attributes', 'created_on', 'updated_at']

@admin.register(WhatsAppTemplate)
class WhatsAppTemplateAdmin(admin.ModelAdmin):
    list_display = ['business', 'name', 'category', 'language', 'status', 'body_text', 'header_type', 'header_text', 'footer_text', 'meta_template_id', 'rejection_reason', 'created_at', 'updated_at']