from django.db import models
from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('Admin', 'Admin'),
        ('Doctor', 'Doctor'),
        ('User', 'User'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Doctor')

    # unique=True enforces no two users can share the same email
    email = models.EmailField(unique=True)

    hospital = models.ForeignKey(
        'hospital.Hospital',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )

    mfa_secret = models.CharField(max_length=64, blank=True, null=True)
    mfa_enabled = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.username} ({self.role})"