from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from rest_framework import viewsets, permissions
from apps.accounts.permissions import IsAdminRole, admin_required
from .models import Product
from .serializers import ProductSerializer
from .forms import ProductForm

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminRole()]
        return [permissions.IsAuthenticated()]


@login_required
def product_list_view(request):
    products = Product.objects.all()
    form = ProductForm()
    return render(request, 'products/product_list.html', {
        'products': products,
        'form': form,
    })


@login_required
@admin_required
def product_create_view(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save()
            messages.success(request, f"Product {product.product_id} registered successfully.")
            return redirect('products:list')
        else:
            messages.error(request, "Error creating product. Please verify form details.")
    else:
        form = ProductForm()

    products = Product.objects.all()
    return render(request, 'products/product_list.html', {
        'products': products,
        'form': form,
    })
