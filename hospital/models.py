# hospital/models.py

from django.db import models
from django.utils.text import slugify
from django.utils import timezone

class Hospital(models.Model):
    name = models.CharField(max_length=255)
    address = models.TextField()
    contact_info = models.CharField(max_length=100)
    slug = models.SlugField(max_length=255, unique=True, blank=True)

    owner = models.ForeignKey(
        'authentication.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_hospitals'
    )

    is_active = models.BooleanField(default=True)

    # Provide explicit default so existing rows get a valid value
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Auto-generate slug from hospital name if not already set
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({'Active' if self.is_active else 'Inactive'})"

    class Meta:
        ordering = ['name']