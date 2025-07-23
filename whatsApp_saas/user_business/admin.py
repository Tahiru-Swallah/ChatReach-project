from django.contrib import admin
from .models import CustomerContact, ScheduledMessage, MessageTemplate

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
    list_display = ['user', 'title', 'content', 'category', 'attachment', 'external_link', 'is_favorite', 'created_at']
