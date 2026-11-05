from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from .forms import CustomLoginForm, CustomRegistrationForm
from django.contrib.auth import get_user_model

CustomUser = get_user_model()

def login_view(request):
    if request.user.is_authenticated:
        return redirect('inspections:dashboard')
    
    if request.method == 'POST':
        form = CustomLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}! Signed in as {user.get_role_display()}.")
            next_url = request.GET.get('next') or request.POST.get('next') or 'inspections:dashboard'
            return redirect(next_url)
        else:
            messages.error(request, "Invalid username or password. Please try again.")
    else:
        form = CustomLoginForm()
        
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, "You have been securely signed out.")
    return redirect('accounts:login')


def register_view(request):
    if request.user.is_authenticated:
        return redirect('inspections:dashboard')

    if request.method == 'POST':
        form = CustomRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Account created successfully as {user.get_role_display()}!")
            return redirect('inspections:dashboard')
        else:
            messages.error(request, "Please correct the errors below to register.")
    else:
        form = CustomRegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


@require_POST
def demo_login_view(request):
    """Allows one-click role switching during demonstration for evaluators."""
    role = request.POST.get('role', 'engineer')
    username = f"{role}"
    
    user = CustomUser.objects.filter(username=username).first()
    if not user:
        # Create demo user on the fly if needed
        role_map = {
            'admin': (CustomUser.ROLE_ADMIN, 'Quality Administrator', True),
            'engineer': (CustomUser.ROLE_ENGINEER, 'Quality Engineer', False),
            'supervisor': (CustomUser.ROLE_SUPERVISOR, 'Inspection Supervisor', False)
        }
        if role in role_map:
            u_role, dept, is_super = role_map[role]
            user = CustomUser.objects.create_user(
                username=username,
                password=f"{role.capitalize()}@123",
                role=u_role,
                department=dept,
                is_superuser=is_super,
                is_staff=is_super
            )
            
    if user:
        login(request, user)
        messages.success(request, f"Switched to {user.get_role_display()} ({user.username})")
    else:
        messages.error(request, f"Could not switch to demo role '{role}'")
        
    next_url = request.POST.get('next') or 'inspections:dashboard'
    return redirect(next_url)

