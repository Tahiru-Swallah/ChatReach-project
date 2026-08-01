from django.db import models
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser, PermissionsMixin
from uuid import uuid4
from phonenumber_field.modelfields import PhoneNumberField
import secrets
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal

# -----------------------------
# Custom User Manager
# -----------------------------
class CustomUserManager(BaseUserManager):
    def create_user(self, email=None, phonenumber=None, password=None, **extra_fields):
        if not email and not phonenumber:
            raise ValueError("Either email or phone number is required.")

        if email:
            email = self.normalize_email(email)

        user = self.model(email=email, phonenumber=phonenumber, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, phonenumber, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_superuser', True)

        if not email:
            raise ValueError("Superuser must have an email.")
        if not phonenumber:
            raise ValueError("Superuser must have a phone number.")

        return self.create_user(email=email, phonenumber=phonenumber, password=password, **extra_fields)

# -----------------------------
# Custom User Model
# -----------------------------
class CustomUser(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    email = models.EmailField(unique=True, blank=False, db_index=True)
    phonenumber = PhoneNumberField(unique=True, blank=True, null=True)
    date_joined = models.DateTimeField(auto_now_add=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['phonenumber']

    objects = CustomUserManager()

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email

# -----------------------------
# Business 
# -----------------------------
class Business(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)

    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='owned_businesses')

    name = models.CharField(max_length=255)

    slug = models.SlugField(unique=True)

    logo = models.ImageField(upload_to='business_logos/', blank=True, null=True)

    phone_number = PhoneNumberField(blank=True, null=True)

    website = models.URLField(blank=True)

    timezone = models.CharField(
        max_length=100,
        default="Africa/Accra"
    )

    country = models.CharField(max_length=100)

    city = models.CharField(max_length=100)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Business"
        verbose_name_plural = "Businesses"
        ordering = ['-created_at']

    def __str__(self):
        return self.name

# -----------------------------
# whatsApp connection
# -----------------------------


def generate_verify_token():
    return secrets.token_hex(16)

class WhatsAppConnection(models.Model):

    class Status(models.TextChoices):
        CONNECTED = "connected", "Connected"
        DISCONNECTED = "disconnected", "Disconnected"
        PENDING = "pending", "Pending"
        FAILED = "failed", "Failed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False
    )

    business = models.OneToOneField(
        Business,
        on_delete=models.CASCADE,
        related_name="whatsapp_connection"
    )

    # Meta IDs
    whatsapp_business_account_id = models.CharField(
        max_length=255,
        unique=True
    )

    phone_number_id = models.CharField(
        max_length=255,
        unique=True
    )

    display_phone_number = models.CharField(
        max_length=50
    )

    catalog_id = models.CharField(max_length=255, blank=True, null=True)

    # Authentication
    access_token = models.TextField()

    verify_token = models.CharField(
        max_length=255,
        default=generate_verify_token,
        unique=True
    )

    # Connection State
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    connected_at = models.DateTimeField(
        blank=True,
        null=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"{self.business.name} - {self.display_phone_number}"

class Product(models.Model):
    class Availability(models.TextChoices):
        IN_STOCK = 'in stock', 'In Stock'
        OUT_OF_STOCK = 'out of stock', 'Out of Stock'

    class Condition(models.TextChoices):
        NEW = 'new', 'New'
        REFURBISHED = 'refurbished', 'Refurbished'
        USED = 'used', 'Used'

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    
    # Association to the Business/User
    business = models.ForeignKey(
        Business, 
        on_delete=models.CASCADE, 
        related_name='products'
    )

    # Core Product Details
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    # Optional Seller / Vendor (e.g., individual store/seller on Winimarket)
    seller = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        help_text="Name of the vendor, seller, or brand offering this item."
    )
    
    # Meta / WhatsApp Unique Identifiers
    # Content ID acts as retailer_id in Meta Commerce Catalog
    content_id = models.CharField(max_length=100, unique=True, editable=False)
    
    # Pricing (Stored as standard currency e.g., 60.00 GHS)
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    currency = models.CharField(max_length=3, default='GHS')

    # Status & Condition
    availability = models.CharField(
        max_length=20, 
        choices=Availability.choices, 
        default=Availability.IN_STOCK
    )
    condition = models.CharField(
        max_length=20, 
        choices=Condition.choices, 
        default=Condition.NEW
    )

    # Media & Links (Meta requires absolute public URLs for image_url)
    image = models.ImageField(upload_to='product_images/')
    image_url_override = models.URLField(
        max_length=500, 
        blank=True, 
        null=True,
        help_text="Optional absolute URL if using external storage like GCS/S3."
    )
    product_url = models.URLField(
        max_length=500, 
        blank=True, 
        null=True,
        help_text="Link to product detail page on storefront."
    )

    # Sync Tracking
    is_synced_to_meta = models.BooleanField(default=False)
    last_synced_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.content_id})"

    def save(self, *args, **kwargs):
        # 1. Auto-generate unique content_id (e.g. PROD-3F8A2) if not set
        if not self.content_id:
            short_id = str(self.id)[:6].upper()
            self.content_id = f"PROD-{short_id}"

        super().save(*args, **kwargs)

    @property
    def price_in_minor_units(self) -> int:
        """Converts standard price (e.g., 60.00) to minor units/cents (6000) for Meta API."""
        return int(self.price * 100)

    @property
    def get_public_image_url(self) -> str:
        """Returns valid absolute public HTTP URL required by Meta Catalog API."""
        if self.image_url_override:
            return self.image_url_override
        if self.image:
            # Handle absolute GCS/S3 or media root URL
            if self.image.url.startswith('http'):
                return self.image.url
            return f"{settings.SITE_URL}{self.image.url}"
        return ""

class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='additional_images')
    image = models.ImageField(upload_to='product_images/additional/')
    image_url_override = models.URLField(max_length=500, blank=True, null=True)

    @property
    def get_public_url(self) -> str:
        if self.image_url_override:
            return self.image_url_override
        if self.image and self.image.url.startswith('http'):
            return self.image.url
        return f"{settings.SITE_URL}{self.image.url}"