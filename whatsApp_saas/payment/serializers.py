from .models import Payment
from rest_framework import serializers

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            'id',
            'user',
            'email',
            'amount',
            'reference',
            'status',
            'verified',
            'created_at'
        ]

        read_only_fields = ['id', 'user', 'status', 'verified', 'created_at', 'reference']

    
    def create(self, validated_data):
        request = self.context['request']
        validated_data['user'] = request.user
        return super().create(validated_data)