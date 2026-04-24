# patients/models.py

from django.db import models
from django.utils import timezone

class Patient(models.Model):
    hospital     = models.ForeignKey(
        'hospital.Hospital',
        on_delete=models.CASCADE,
        related_name='patients'
    )
    first_name   = models.CharField(max_length=255)
    last_name    = models.CharField(max_length=255)
    dob          = models.DateField()
    contact_info = models.CharField(max_length=100)
    email        = models.EmailField(unique=True, default='')
    is_chronic   = models.BooleanField(default=False)

    # Use default=timezone.now instead of auto_now_add=True
    # This avoids the prompt when existing rows are present
    created_at   = models.DateTimeField(default=timezone.now, editable=False)
    updated_at   = models.DateTimeField(auto_now=True)

    @property
    def age(self):
        from datetime import date
        today = date.today()
        return today.year - self.dob.year - (
            (today.month, today.day) < (self.dob.month, self.dob.day)
        )

    def __str__(self):
        return f'{self.first_name} {self.last_name}'

    class Meta:
        ordering = ['last_name', 'first_name']


class Condition(models.Model):
    SEVERITY_CHOICES = [
        ('mild',     'Mild'),
        ('moderate', 'Moderate'),
        ('severe',   'Severe'),
    ]

    patient      = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name='conditions'
    )
    name          = models.CharField(max_length=255)
    severity      = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default='mild'
    )
    diagnosed_on  = models.DateField()
    notes         = models.TextField(blank=True, null=True)

    def __str__(self):
        return f'{self.name} ({self.severity}) — {self.patient}'

    class Meta:
        ordering = ['name']