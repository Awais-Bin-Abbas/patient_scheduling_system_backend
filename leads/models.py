from django.db import models

class Lead(models.Model):
    patient = models.ForeignKey('patients.Patient', on_delete=models.CASCADE)  # Patient model is now in `patients` app
    lead_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=100)

    def __str__(self):
        return f'Lead for {self.patient.first_name} {self.patient.last_name}'