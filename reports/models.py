# reports/models.py

from django.db import models
from django.utils import timezone


class Report(models.Model):
    """
    Stores generated report results per hospital.
    Created by Celery task after background processing.
    """

    STATUS_CHOICES = [
        ('pending',    'Pending'),
        ('processing', 'Processing'),
        ('complete',   'Complete'),
        ('failed',     'Failed'),
    ]

    # Which hospital this report belongs to
    hospital     = models.ForeignKey(
        'hospital.Hospital',
        on_delete=models.CASCADE,
        related_name='reports'
    )

    # Who triggered the report
    generated_by = models.ForeignKey(
        'authentication.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_reports'
    )

    # Actual report data stored as JSON
    data         = models.JSONField(null=True, blank=True)

    # Current status of report generation
    status       = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    # Celery task ID for polling status
    task_id      = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    # Timestamps
    created_at   = models.DateTimeField(default=timezone.now, editable=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'Report — {self.hospital.name} — {self.status} — {self.created_at.date()}'

    class Meta:
        ordering = ['-created_at']