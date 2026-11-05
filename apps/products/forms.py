from django import forms
from .models import Product

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['product_id', 'product_name', 'description', 'is_active']
        widgets = {
            'product_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. P-PLATE01'}),
            'product_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Demonstration metal plate'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Detailed specifications'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

