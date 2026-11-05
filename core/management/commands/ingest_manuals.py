import csv
import os
from django.conf import settings
from django.core.management.base import BaseCommand
from core.models import Machine, Manual
import fitz  # PyMuPDF


class Command(BaseCommand):
    help = 'Registers machines and ingests PDF manuals using the provided index CSV.'

    def handle(self, *args, **kwargs):
        csv_path = os.path.join(settings.BASE_DIR, 'machine_manual_index.csv')
        manuals_dir = os.path.join(settings.BASE_DIR, 'Manuals')

        if not os.path.exists(csv_path):
            # Try finding it in root or current directory
            csv_path = 'machine_manual_index.csv'

        if not os.path.exists(csv_path):
            self.stdout.write(self.style.ERROR(f'CSV index file not found at: {csv_path}'))
            return

        self.stdout.write(self.style.SUCCESS(f'Reading metadata from {csv_path}'))

        # Read CSV and register manuals
        with open(csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                machine_id = row.get('machine_id') or row.get('Machine ID')
                machine_name = row.get('machine_name') or row.get('Machine Name')
                doc_id = row.get('document_id') or row.get('Document ID')
                title = row.get('title') or row.get('Title')
                revision = row.get('revision') or row.get('Revision')
                filename = (
                    row.get('pdf_filename')
                    or row.get('filename')
                    or row.get('Filename')
                )

                if not machine_id or not doc_id:
                    continue

                # 1. Get or create Machine
                machine, _ = Machine.objects.get_or_create(
                    machine_id=machine_id.strip(),
                    defaults={
                        'name': (machine_name or machine_id).strip(),
                        'description': 'Demonstration equipment',
                    },
                )

                # 2. Create Manual record
                pdf_filename = filename.strip() if filename else ''
                pdf_path = os.path.join(manuals_dir, pdf_filename)
                if not os.path.exists(pdf_path):
                    pdf_path = os.path.join('Manuals', pdf_filename)
                if not os.path.exists(pdf_path):
                    pdf_path = pdf_filename  # Try direct path

                manual, created = Manual.objects.get_or_create(
                    machine=machine,
                    document_id=doc_id.strip(),
                    defaults={
                        'title': (title or '').strip(),
                        'revision': (revision or '').strip(),
                        'pdf_file': f'manuals/{pdf_filename}' if pdf_filename else '',
                    },
                )

                self.stdout.write(
                    self.style.SUCCESS(f'Successfully registered: {doc_id} for {machine_id}')
                )

                # 3. Extract text page-by-page using PyMuPDF
                if pdf_filename and os.path.exists(pdf_path):
                    doc = fitz.open(pdf_path)
                    for page_idx in range(len(doc)):
                        page = doc[page_idx]
                        text = page.get_text()
                        page_num = page_idx + 1
                        # Here you can also save chunks to your vector store / search index if needed!
                        print(
                            f'   -> Processed {pdf_filename} Page {page_num} ({len(text)} chars)'
                        )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'PDF file not found at: {pdf_path}')
                    )

        self.stdout.write(
            self.style.SUCCESS('Manual ingestion process completed!')
        )
