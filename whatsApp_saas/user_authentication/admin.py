from django.contrib import admin
from .models import CustomUser, BusinessProfile

@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'email', 'phonenumber', 'date_joined', 'is_staff', 'is_active')

@admin.register(BusinessProfile)
class BusinessProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'business_name', 'phone_number', 'email', 'website', 'description', 'location', 'is_registered', 'is_premium', 'created_on')