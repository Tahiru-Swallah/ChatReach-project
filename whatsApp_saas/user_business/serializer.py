from rest_framework import serializers
from .models import CustomerContact, WhatsAppTemplate

class CustomerContactSerializer(serializers.ModelSerializer):
    """
    Serializer for managing individual CustomerContact records.
    Handles validation, phone sanitization, and multi-tenant scoping.
    """

    class Meta:
        model = CustomerContact
        fields = [
            'id',
            'business',
            'name',
            'phone_number',
            'email',
            'tag',
            'is_opted_in',
            'attributes',
            'created_on',
            'updated_at'
        ]
        read_only_fields = ['id', 'business', 'created_on', 'updated_at']

    def validate_phone_number(self, value):
        """
        Clean the phone number input before saving/validating against DB rules.
        """

        if value:
            # Strip whitespace and leading '+'
            cleaned_number = value.strip().lstrip('+')
            return cleaned_number
        return value

    def validate(self, attrs):
        """
        Ensure duplicate contacts per business are caught early in validation 
        before hitting the database UniqueConstraint exception.
        """

        request = self.context.get('request')
        phone_number = attrs.get('phone_number')

        if request and hasattr(request, 'user') and hasattr(request.user, 'owned_businesses'):
            business = request.user.owned_businesses.first()  # Assuming single business context for now

            existing_query = CustomerContact.objects.filter(business=business, phone_number=phone_number)

            if self.instance:
                # Exclude the current instance when updating
                existing_query = existing_query.exclude(pk=self.instance.pk)

            if existing_query.exists():
                raise serializers.ValidationError(
                    {"phone_number": "This phone number already exists in your contact list."}
                )

        return attrs

    def create(self, validated_data):
        """
        Automatically bind the authenticated user's Business instance.
        """
        request = self.context.get('request')
        if request and hasattr(request.user, 'owned_businesses'):
            validated_data['business'] = request.user.owned_businesses.first()
        return super().create(validated_data)

class BulkCustomerContactSerializer(serializers.Serializer):
    """
    Specialized Serializer to handle batch CSV/Excel/JSON bulk imports efficiently.
    Accepts an array of contact objects.
    """

    contacts = CustomerContactSerializer(many=True)

    def create(self, validated_data):
        request = self.context.get('request')
        business = request.user.owned_businesses.first() if request and hasattr(request.user, 'owned_businesses') else None

        contacts_data = validated_data.get('contacts', [])
        created_contacts = []
        updated_contacts = []

        for item in contacts_data:
            phone = item.get('phone_number')

            # Perform upsert (update existing or create new)
            contact, created = CustomerContact.objects.update_or_create(
                business=business,
                phone_number=phone,
                defaults = {
                    'name': item.get('name', ''),
                    'email': item.get('email', None),
                    'tag': item.get('tag', []),
                    'is_opted_in': item.get('is_opted_in', True),
                    'attributes': item.get('attributes', {}),
                }
            )

            if created:
                created_contacts.append(contact)
            else:
                updated_contacts.append(contact)

        return {
            'created_count': len(created_contacts),
            'updated_count': len(updated_contacts),
            'total': len(contacts_data)
        }

class WhatsAppTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhatsAppTemplate
        fields = [
            'id', 'name', 'category', 'language', 'status',
            'header_type', 'header_text', 'body_text', 'footer_text',
            'meta_template_id', 'rejection_reason', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'status', 'meta_template_id', 'rejection_reason', 'created_at', 'updated_at']