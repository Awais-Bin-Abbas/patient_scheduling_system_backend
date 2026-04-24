# patients/management/commands/seed_patients.py

import requests
from django.core.management.base import BaseCommand
from patients.models import Patient
from hospital.models import Hospital


class Command(BaseCommand):
    help = 'Seed patient data from randomuser.me — auto distributes across all active hospitals'

    def add_arguments(self, parser):
        # Total patients to seed across ALL hospitals
        parser.add_argument(
            '--count',
            type=int,
            default=50,
            help='Total number of patients to seed across all hospitals (default: 50)'
        )

    def handle(self, *args, **options):
        total_count = options['count']

        # Get all active hospitals in the system
        hospitals = Hospital.objects.filter(is_active=True)

        if not hospitals.exists():
            self.stdout.write(
                self.style.ERROR(
                    'No active hospitals found. Create at least one hospital first.'
                )
            )
            return

        hospital_count = hospitals.count()

        self.stdout.write(
            f'Found {hospital_count} active hospital(s).'
        )
        self.stdout.write(
            f'Fetching {total_count} patients from randomuser.me...'
        )

        try:
            # Fetch all patients in one API call
            response = requests.get(
                f'https://randomuser.me/api/?results={total_count}&nat=us',
                timeout=10
            )
            response.raise_for_status()
            results = response.json()['results']

        except requests.RequestException as e:
            self.stdout.write(self.style.ERROR(f'API call failed: {e}'))
            return

        created_count = 0
        skipped_count = 0

        for index, person in enumerate(results):
            # Cycle through hospitals using modulo
            # index 0 → hospital 0
            # index 1 → hospital 1
            # index 2 → hospital 0 again (if only 2 hospitals)
            # This ensures even distribution across all hospitals
            hospital = hospitals[index % hospital_count]

            # Parse date of birth
            dob_str = person['dob']['date'][:10]

            # get_or_create ensures no duplicates on re-run
            patient, created = Patient.objects.get_or_create(
                email=person['email'],
                defaults={
                    'hospital':     hospital,
                    'first_name':   person['name']['first'],
                    'last_name':    person['name']['last'],
                    'dob':          dob_str,
                    'contact_info': person['phone'],
                    'is_chronic':   False,
                }
            )

            if created:
                created_count += 1
            else:
                skipped_count += 1

        # Print summary per hospital
        self.stdout.write('\n--- Distribution Summary ---')
        for hospital in hospitals:
            count = Patient.objects.filter(hospital=hospital).count()
            self.stdout.write(f'  {hospital.name}: {count} patients')

        self.stdout.write(
            self.style.SUCCESS(
                f'\nDone. Created: {created_count} | Skipped (already exist): {skipped_count}'
            )
        )