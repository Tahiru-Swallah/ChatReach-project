from django.db import models
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser, PermissionsMixin
from uuid import uuid4
from phonenumber_field.modelfields import PhoneNumberField

class CustomUserManager(BaseUserManager):

    def create_user(self, email=None, phonenumber=None, password=None, **extra_fields):
        if not email and not phonenumber:
            raise ValueError("Either Email or Phonenumner required!!")
        
        if email:
            email = self.normalize_email(email)
            extra_fields['email'] = email

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

class CustomUser(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
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
            self.email = self.email.lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email or str(self.phonenumber) or self.first_name or self.last_name

