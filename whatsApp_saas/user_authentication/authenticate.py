from django.contrib.auth.backends import ModelBackend
from django.db.models import Q
from .models import CustomUser


class EmailOrPhoneNumberBackend(ModelBackend):

    def authenticate(self, request, username = None, password = None, **kwargs):
        if username is None:
            return None
        try:
            user = CustomUser.objects.get(Q(email=username) | Q(phonenumber=username))
        
        except (CustomUser.DoesNotExist, CustomUser.MultipleObjectsReturned):
            return None
        
        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        
        return None