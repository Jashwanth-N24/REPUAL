from django.db import models

class Product(models.Model):
    product_id = models.CharField(max_length=64, primary_key=True, help_text='Unique Product Code, e.g., P-PLATE01')
    product_name = models.CharField(max_length=255, help_text='Descriptive product title')
    description = models.TextField(blank=True, help_text='Product specification or inspection guide')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['product_id']
        verbose_name = 'Manufactured Product'
        verbose_name_plural = 'Manufactured Products'

    def __str__(self):
        return f"{self.product_id} - {self.product_name}"

