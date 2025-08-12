from django.db import models
from uuid import uuid4
from user_authentication.models import CustomUser

class Payment(models.Model):
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('sucess', 'Success'),
        ('failed', 'Failed')
    ]

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='payment')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    email = models.EmailField()
    reference = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=25, choices=PAYMENT_STATUS, default='pending')
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.amount} - {self.status}"