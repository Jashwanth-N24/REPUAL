import csv
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth import get_user_model
from apps.products.models import Product

CustomUser = get_user_model()

class Command(BaseCommand):
    help = 'Seeds initial demonstration data: products from product_details.csv and demo user roles.'

    def handle(self, *args, **options):
        self.stdout.write("Seeding manufacturing system data...")

        # 1. Seed Products from product_details.csv
        csv_path = settings.BASE_DIR / 'product_details.csv'
        if csv_path.exists():
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    prod_id = row['product_id']
                    name = row['product_name']
                    desc = row['description']
                    obj, created = Product.objects.update_or_create(
                        product_id=prod_id,
                        defaults={
                            'product_name': name,
                            'description': desc,
                            'is_active': True,
                        }
                    )
                    status_text = "Created" if created else "Updated"
                    self.stdout.write(self.style.SUCCESS(f"  [+] {status_text} Product: {obj.product_id} - {obj.product_name}"))
        else:
            self.stdout.write(self.style.WARNING("  [!] product_details.csv not found, creating default P-PLATE01"))
            Product.objects.get_or_create(
                product_id='P-PLATE01',
                defaults={
                    'product_name': 'Demonstration metal plate',
                    'description': 'Synthetic centered plate with scratches or pits',
                    'is_active': True
                }
            )

        # 2. Seed Demo Users
        users = [
            {
                'username': 'admin',
                'password': 'Admin@123',
                'role': CustomUser.ROLE_ADMIN,
                'email': 'admin@factory.local',
                'department': 'Plant Administration',
                'is_staff': True,
                'is_superuser': True,
            },
            {
                'username': 'engineer',
                'password': 'Engineer@123',
                'role': CustomUser.ROLE_ENGINEER,
                'email': 'engineer@factory.local',
                'department': 'Quality Engineering (Line 1)',
                'is_staff': False,
                'is_superuser': False,
            },
            {
                'username': 'supervisor',
                'password': 'Supervisor@123',
                'role': CustomUser.ROLE_SUPERVISOR,
                'email': 'supervisor@factory.local',
                'department': 'Quality Assurance Supervision',
                'is_staff': False,
                'is_superuser': False,
            },
        ]

        for udata in users:
            username = udata.pop('username')
            password = udata.pop('password')
            user, created = CustomUser.objects.get_or_create(username=username, defaults=udata)
            user.set_password(password)
            for k, v in udata.items():
                setattr(user, k, v)
            user.save()
            action = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f"  [+] {action} User: {user.username} (Role: {user.get_role_display()}) | Password: {password}"))

        self.stdout.write(self.style.SUCCESS("\nDatabase seeding completed successfully!"))

