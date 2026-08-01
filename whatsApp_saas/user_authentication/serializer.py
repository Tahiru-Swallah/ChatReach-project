from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.password_validation import validate_password
from dj_rest_auth.registration.serializers import SocialLoginSerializer
from .models import CustomUser, Business, WhatsAppConnection, Product, ProductImage
from .service import generate_whatsapp_product_link

class CustomGoogleLoginSerializer(SocialLoginSerializer):
    id_token = serializers.CharField(required=True, allow_blank=True)

    def validate(self, attrs):
        attrs['access_token'] = attrs['id_token']
        return super().validate(attrs)
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email_or_phonenumber'

    email_or_phonenumber = serializers.CharField()
    password = serializers.CharField(write_only = True)

    def validate(self, attrs):
        email_or_phonenumber = attrs.get('email_or_phonenumber')
        password = attrs.get('password')

        user = None

        try:
            user = CustomUser.objects.get(email=email_or_phonenumber)
        except CustomUser.DoesNotExist:
            try:
                user = CustomUser.objects.get(phonenumber=email_or_phonenumber)
            except CustomUser.DoesNotExist:
                raise serializers.ValidationError('Invalid email or phonenumber')
        
        if not user.check_password(password):
            raise serializers.ValidationError('Invalid credentials')
        
        if not user.is_active:
            raise serializers.ValidationError('User is inactive')
        
        data = super().get_token(user)

        return {
            "refresh_token": str(data),
            "access_token": str(data.access_token),
            "user": {
                "id": str(user.id),
                "email": user.email,
                "phonenumber": str(user.phonenumber),
            },
        }


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    class Meta:
        model = CustomUser
        fields = ('email', 'phonenumber', 'password')

    def validate_email(self, value):
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError('Email already exists')
        return value

    def validate_phonenumber(self, value):
        if CustomUser.objects.filter(phonenumber=value).exists():
            raise serializers.ValidationError('Phonenumber already exists')
        return value

    def create(self, validated_data):
        user = CustomUser(
            email = validated_data['email'],
            phonenumber = validated_data['phonenumber'],
        )

        user.set_password(validated_data['password'])
        user.save()

        return user
    
class WhatsAppConnectionSerializer(serializers.ModelSerializer):
    """
    Handles the WhatsApp Cloud API integration settings.
    Notice we mark sensitive fields like 'access_token' and 'verify_token'
    as write-only or read-only for security.
    """
    class Meta: 
        model = WhatsAppConnection
        fields = ['id', 'business', 'whatsapp_business_account_id', 'phone_number_id', 'display_phone_number', "catalog_id", 'access_token', 'verify_token', 'status', 'connected_at', 'updated_at']
        read_only_fields = ['id', 'verify_token', 'status', 'connected_at', 'updated_at']
        extra_kwargs = {'access_token': {'write_only': True},}


class BusinessSerializer(serializers.ModelSerializer):
    """
    Handles the core Business profile metadata for the SaaS platform.
    Includes the nested WhatsApp connection status so React gets everything in one call.
    """
    # Nesting the WhatsApp connection details inside the business object
    whatsapp_connection = WhatsAppConnectionSerializer(read_only=True)
    slug = serializers.SlugField(read_only=True)

    class Meta:
        model = Business
        fields = ['id', 'owner', 'name', 'slug', 'logo', 'phone_number', 'website', 'timezone', 'whatsapp_connection', 'country', 'city', 'is_active', 'created_at', 'updated_at']

        read_only_fields = ['id', 'owner', 'slug', 'created_at', 'updated_at', 'is_active']

    def create(self, validated_data):
        """
        Automatically hooks up the loggen-in user as the owner of the business.
        Automatically generates a clean URL slug from the business name.
        """

        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['owner'] = request.user
        
        from django.utils.text import slugify
        base_slug = slugify(validated_data['name'])
        slug = base_slug

        count = 1
        while Business.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{count}"
            count += 1

        validated_data['slug'] = slug

        return super().create(validated_data)

class ProductImageSerializer(serializers.ModelSerializer):
    """
    Serializer for handling additional product gallery images.
    """
    public_url = serializers.CharField(source="get_public_url", read_only=True)

    class Meta:
        model = ProductImage
        fields = [
            'id',
            'product',
            'image',
            'image_url_override',
            'public_url'
            ]

        read_only_fields = ['id', 'product']

    def validate(self, attrs):
        image = attrs.get('image')
        image_url_override = attrs.get('image_url_override')

        if not self.instance and not image and not image_url_override:
            raise serializers.ValidationError({
                "image": "Provide either an uploaded image file or an image_url_override URL."
            })
        return attrs

class ProductSerializer(serializers.ModelSerializer):
    """
    Serializer for managing Product creation, updates, and catalog representation.
    Includes support for multiple additional gallery images.
    """
    content_id = serializers.CharField(read_only=True)
    price_in_minor_units = serializers.IntegerField(read_only=True)
    get_public_image_url = serializers.CharField(read_only=True)
    business_name = serializers.CharField(source='business.name', read_only=True)

    # Nested additional gallery images
    additional_images = ProductImageSerializer(many=True, read_only=True)

    # Optional fields
    seller = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    product_url = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    image_url_override = serializers.URLField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Product
        fields = [
            'id',
            'business',
            'business_name',
            'seller',
            'name',
            'description',
            'content_id',
            'price',
            'price_in_minor_units',
            'currency',
            'availability',
            'condition',
            'image',
            'image_url_override',
            'get_public_image_url',
            'additional_images',  # <-- NESTED GALLERY IMAGES
            'product_url',
            'is_synced_to_meta',
            'last_synced_at',
            'created_at',
            'updated_at',
        ]

        read_only_fields = [
            'id', 
            'business', 
            'content_id', 
            'is_synced_to_meta', 
            'last_synced_at', 
            'created_at', 
            'updated_at'
        ]

    def validate(self, attrs):
        image = attrs.get('image')
        image_url_override = attrs.get('image_url_override')

        if not self.instance and not image and not image_url_override:
            raise serializers.ValidationError({
                "image": "Either a local file upload or an 'image_url_override' URL must be provided."
            })
            
        return attrs

    def create(self, validated_data):
        request = self.context.get('request')

        if request:
            validated_data['business'] = request.user.owned_businesses.first()

        return super().create(validated_data)

class MetaCatalogBatchSerializer(serializers.ModelSerializer):
    """
    Formats Product instances directly into Meta's Catalog Batch API payload schema.
    """
    method = serializers.SerializerMethodField()
    retailer_id = serializers.CharField(source="content_id")
    data = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ['method', 'retailer_id', 'data']

    def get_method(self, obj) -> str:
        return 'UPDATE'

    def get_data(self, obj) -> dict:

        additional_urls = [
            img.get_public_url for img in obj.additional_images.all() if img.get_public_url 
        ]

        product_url = obj.product_url 

        if not product_url:
            request = self.context.get('request')
            business = request.user.owned_businesses.first()

            whatsapp_conn = WhatsAppConnection.objects.get(business=business, status=WhatsAppConnection.Status.CONNECTED)

            phone_number = None
            if whatsapp_conn:
                phone_number = whatsapp_conn.display_phone_number
            elif business:
                phone_number = business.phone_number

            if phone_number:
                product_url = generate_whatsapp_product_link(phone_number, obj.name)

            # Fallback 2: Domain safety fallback to ensure Meta never gets None
            if not product_url:
                product_url = f"https://chatreach.io/products/{obj.content_id}"

        return {
            "name": obj.name,
            "description": obj.description or obj.name,
            "brand": obj.seller or obj.business.name,
            "price": obj.price_in_minor_units,
            "currency": obj.currency,
            "availability": obj.availability,
            "condition": obj.condition,
            "image_url": obj.get_public_image_url,
            "additional_image_urls": additional_urls,  # <-- MAPPED TO META
            "url": product_url,
        }