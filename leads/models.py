# leads/models.py

from django.db import models
from django.utils import timezone


class LeadCriteria(models.Model):
    """
    Stores reusable lead generation rules per hospital.
    Admin creates these through the UI.
    """

    hospital   = models.ForeignKey(
        'hospital.Hospital',
        on_delete=models.CASCADE,
        related_name='lead_criteria'
    )
    name       = models.CharField(max_length=255)
    criteria   = models.JSONField()
    is_active  = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        'authentication.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_criteria'
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.name} — {self.hospital.name}'

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Lead Criteria'


class Lead(models.Model):
    """
    A patient who matches specific criteria and is a potential
    candidate for a hospital service or follow-up.
    """

    STATUS_CHOICES = [
        ('new',       'New'),
        ('contacted', 'Contacted'),
        ('qualified', 'Qualified'),
        ('converted', 'Appointed'),
        ('rejected',  'Rejected'),
    ]

    patient     = models.ForeignKey(
        'patients.Patient',
        on_delete=models.CASCADE,
        related_name='leads'
    )

    # null=True allows existing rows to have no hospital during migration
    # We will remove null=True in a follow-up migration after data is clean
    hospital    = models.ForeignKey(
        'hospital.Hospital',
        on_delete=models.CASCADE,
        related_name='leads',
        null=True,
        blank=True
    )

    criteria    = models.ForeignKey(
        LeadCriteria,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_leads'
    )

    assigned_to = models.ForeignKey(
        'authentication.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_leads'
    )

    status      = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='new'
    )

    notes       = models.TextField(blank=True, null=True)
    lead_date   = models.DateTimeField(default=timezone.now, editable=False)
    updated_at  = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Lead — {self.patient} — {self.status}'

    class Meta:
        ordering = ['-lead_date']
        unique_together = ['patient', 'hospital']  