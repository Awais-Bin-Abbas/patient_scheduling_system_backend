from django.db import models
from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    # Role choices for access control
    ROLE_CHOICES = [
        ('Admin', 'Admin'),
        ('Doctor', 'Doctor'),
        ('User', 'User'),
    ]

    # Role field to determine user's access level
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Doctor')

    # Link user to a hospital for multi-tenant context (nullable for superadmin)
    hospital = models.ForeignKey(
        'hospital.Hospital',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )

    # MFA secret key (stores TOTP secret, empty if MFA not enabled)
    mfa_secret = models.CharField(max_length=64, blank=True, null=True)

    # Flag to track if user has MFA enabled
    mfa_enabled = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.username} ({self.role})"