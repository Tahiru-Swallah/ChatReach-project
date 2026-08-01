from django.contrib import admin
from .models import CustomUser, Business, WhatsAppConnection, Product, ProductImage

@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('email', 'phonenumber', 'date_joined', 'is_staff', 'is_active')
    search_fields = ('email', 'phonenumber')

@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ('owner', 'name', 'slug', 'phone_number', 'website', 'country', 'city', 'is_active', 'created_at', 'updated_at')

@admin.register(WhatsAppConnection)
class WhatsAppConnectionAdmin(admin.ModelAdmin):
    list_display = ('business', 'whatsapp_business_account_id', 'phone_number_id', 'display_phone_number', 'catalog_id', 'access_token', 'verify_token', 'status', 'connected_at', 'updated_at')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("business", "name", "description", "seller", "content_id", "price", "currency", "availability", "condition", "image", "image_url_override", "product_url", "is_synced_to_meta", "last_synced_at", "created_at", "updated_at")

@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ("product", "image", "image_url_override")