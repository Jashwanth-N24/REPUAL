from django import forms
from .models import Inspection, Batch
from apps.products.models import Product

class SingleInspectionUploadForm(forms.Form):
    product = forms.ModelChoiceField(
        queryset=Product.objects.filter(is_active=True),
        empty_label=None,
        widget=forms.Select(attrs={'class': 'form-select form-select-lg'})
    )
    image = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control form-control-lg',
            'accept': 'image/png, image/jpeg',
            'id': 'imageFileInput'
        }),
        help_text='Accepts JPEG or PNG only. Maximum 5 MiB. Minimum dimension 64x64.'
    )


class MultipleFileInput(forms.FileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={
            'class': 'form-control form-control-lg',
            'multiple': True,
            'accept': 'image/png, image/jpeg',
            'id': 'batchFilesInput'
        }))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_clean(d, initial) for d in data]
        else:
            result = [single_clean(data, initial)]
        return result

class BatchInspectionUploadForm(forms.Form):
    product = forms.ModelChoiceField(
        queryset=Product.objects.filter(is_active=True),
        empty_label=None,
        widget=forms.Select(attrs={'class': 'form-select form-select-lg'})
    )
    images = MultipleFileField(
        help_text='Select 1 to 10 images (JPEG or PNG). Background worker processes each concurrently.'
    )


class SupervisorReviewForm(forms.Form):
    reviewed_class = forms.ChoiceField(
        choices=Inspection.CLASS_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    review_comment = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Add notes or reasons for confirmation/correction (optional)...'
        })
    )


class HistoryFilterForm(forms.Form):
    PREDICTION_CHOICES = [
        ('', 'All Predictions'),
        ('Normal', 'Normal'),
        ('Defective', 'Defective'),
    ]
    REVIEW_CHOICES = [
        ('', 'All Review States'),
        ('pending', 'Pending Review'),
        ('confirmed', 'Confirmed'),
        ('corrected', 'Corrected'),
    ]
    STATUS_CHOICES = [
        ('', 'All Statuses'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('processing', 'Processing'),
    ]

    prediction = forms.ChoiceField(choices=PREDICTION_CHOICES, required=False, widget=forms.Select(attrs={'class': 'form-select form-select-sm'}))
    review_status = forms.ChoiceField(choices=REVIEW_CHOICES, required=False, widget=forms.Select(attrs={'class': 'form-select form-select-sm'}))
    status = forms.ChoiceField(choices=STATUS_CHOICES, required=False, widget=forms.Select(attrs={'class': 'form-select form-select-sm'}))
    q = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Search filename or ID...'}))
