from django.contrib import admin
from .models import CustomerContact, ScheduledMessage, MessageTemplate, TemplateCategory, Notification

@admin.register(CustomerContact)
class CustomerContactAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone_number', 'email', 'tag', 'created_on']

@admin.register(ScheduledMessage)
class ScheduledMessageAdmin(admin.ModelAdmin):
    list_display = ['user', 'message', 'media', 'get_contacts', 'scheduled_time', 'status', 'created_at', 'updated_at']

    def get_contacts(self, obj):
        contacts = obj.contacts.all()[:5]  # limit to 5
        contacts_list = ", ".join(str(contact) for contact in contacts)
        if obj.contacts.count() > 5:
            contacts_list += "..."
        return 
    
@admin.register(MessageTemplate)
class MesssageTemplateAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'template_name', 'language', 'placeholders', 'category', 'attachment', 'external_link', 'is_favorite', 'created_at']
@admin.register(TemplateCategory)
class TemplateCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'created_at']

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'message', 'type', 'is_read', 'created_at']