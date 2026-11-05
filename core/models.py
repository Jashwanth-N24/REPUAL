from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_ADMIN = 'admin'
    ROLE_ENGINEER = 'engineer'
    ROLE_SUPERVISOR = 'supervisor'
    ROLE_CHOICES = (
        ('admin', 'Administrator'),
        ('engineer', 'Engineer'),
        ('supervisor', 'Supervisor'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='engineer')
    has_ai_access = models.BooleanField(default=True)
    department = models.CharField(max_length=100, blank=True, default='Manufacturing')

    @property
    def is_admin_role(self):
        return self.role == 'admin' or self.is_superuser

    @property
    def is_engineer_role(self):
        return self.role == 'engineer'

    @property
    def is_supervisor_role(self):
        return self.role in ('supervisor', 'admin') or self.is_superuser

    def get_role_display(self):
        return {'admin': 'Administrator', 'engineer': 'Engineer', 'supervisor': 'Supervisor'}.get(self.role, self.role.title())


class Machine(models.Model):
    machine_id = models.CharField(
        max_length=50, unique=True
    )  # e.g., M-HP200, M-AC90
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return f'{self.name} ({self.machine_id})'


class Manual(models.Model):
    machine = models.ForeignKey(
        Machine, on_delete=models.CASCADE, related_name='manuals'
    )
    document_id = models.CharField(max_length=50)  # e.g., HP-OPS-01, AC-OM-01
    title = models.CharField(max_length=255)
    revision = models.CharField(max_length=10)
    pdf_file = models.FileField(upload_to='manuals/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.document_id} (Rev {self.revision}) - {self.machine.machine_id}'


class QuestionHistory(models.Model):
    STATUS_CHOICES = (
        ('answered', 'Answered'),
        ('insufficient_evidence', 'Insufficient Evidence'),
        ('security_blocked', 'Security Blocked'),
    )

    engineer = models.ForeignKey(User, on_delete=models.CASCADE)
    machine = models.ForeignKey(
        Machine, on_delete=models.SET_NULL, null=True, blank=True
    )
    question = models.TextField()
    answer = models.TextField()
    source_references = models.JSONField(default=list)
    status = models.CharField(max_length=50, default='answered', choices=STATUS_CHOICES)
    security_flag = models.BooleanField(
        default=False
    )  # Tracks security breaches / cross-contamination attempts
    confidence_score = models.FloatField(
        default=100.0
    )  # Tracks retrieval confidence percentage
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'[{self.status}] {self.question[:50]}'




