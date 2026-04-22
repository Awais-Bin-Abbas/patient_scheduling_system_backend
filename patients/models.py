from django.db import models

class Patient(models.Model):
    hospital = models.ForeignKey('hospital.Hospital', on_delete=models.CASCADE)  # Hospital model is now in `hospital` app
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    dob = models.DateField()
    contact_info = models.CharField(max_length=100)

    def __str__(self):
        return f'{self.first_name} {self.last_name}'