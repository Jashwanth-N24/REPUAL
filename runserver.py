import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'manufacturing_assistant.settings')
import django
django.setup()
from django.core.management import call_command

print("Starting Django server on http://127.0.0.1:8000 ...", flush=True)
try:
    call_command('runserver', '127.0.0.1:8000', use_reloader=False)
except Exception as e:
    print(f"Error: {e}", flush=True)

