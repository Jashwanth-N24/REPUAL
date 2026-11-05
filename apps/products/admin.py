from django.contrib import admin
from .models import Product

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('product_id', 'product_name', 'is_active', 'created_at')
    search_fields = ('product_id', 'product_name', 'description')
    list_filter = ('is_active', 'created_at')

