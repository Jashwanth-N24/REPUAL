from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model

CustomUser = get_user_model()

class CustomLoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control form-control-lg',
        'placeholder': 'Username',
        'autofocus': True,
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control form-control-lg',
        'placeholder': 'Password',
    }))


class CustomRegistrationForm(UserCreationForm):
    role = forms.ChoiceField(
        choices=CustomUser.ROLE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select form-select-lg'}),
        initial=CustomUser.ROLE_ENGINEER,
        help_text='Select your role in the inspection pipeline'
    )
    department = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'e.g. Line 3 Quality'})
    )

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('username', 'email', 'role', 'department')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-control form-control-lg'

