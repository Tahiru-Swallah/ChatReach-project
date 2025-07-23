from rest_framework import serializers
from .models import CustomerContact, ScheduledMessage, MessageTemplate

class CustomerContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerContact
        fields = ['id', 'user', 'phone_number', 'email', 'tag', 'created_on']
        read_only_fields = ['id', 'user', 'created_on']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
    

class ScheduledMessageSerializer(serializers.ModelSerializer):
    contacts = serializers.PrimaryKeyRelatedField(
        many=True, queryset=CustomerContact.objects.all()
    )

    class Meta:
        model = ScheduledMessage
        fields = [
            'id',
            'user',
            'contacts',
            'message_body',
            'media_url',
            'scheduled_time',
            'status',
            'created_on'
        ]
        read_only_fields = ['id', 'user', 'status', 'created_on']

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['user'] = user
        return super().create(validated_data)

class MessageTemplateSerializer(serializers.ModelSerializer):
    attachment = serializers.FileField(required=False, allow_null=True)
    external_link = serializers.URLField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = MessageTemplate
        fields = [
            'id',
            'user',
            'title',
            'content',
            'category',
            'attachment',
            'external_link',
            'is_favorite',
            'created_at',
        ]
        read_only_fields = ['id', 'user', 'created_at']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
