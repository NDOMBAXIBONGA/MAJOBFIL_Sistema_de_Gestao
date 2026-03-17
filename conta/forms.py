from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Conta

class ContaCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Endereço de email'
        })
    )
    
    nome = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nome completo'
        })
    )
    
    telemovel = forms.CharField(
        max_length=15,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Número de telemóvel'
        })
    )
    
    data_nascimento = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    bilhete_identidade = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Bilhete de identidade'
        })
    )
    
    bairro = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Bairro'
        })
    )
    
    cidade = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Cidade'
        })
    )
    
    municipio = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Município'
        })
    )
    
    provincia = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Província'
        })
    )
    
    is_staff = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    is_superuser = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    is_active = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

    class Meta:
        model = Conta
        fields = ('username', 'email', 'nome', 'telemovel', 'data_nascimento',
                 'bilhete_identidade', 'bairro', 'cidade', 'municipio', 'provincia',
                 'is_staff', 'is_superuser', 'is_active')
        
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome de usuário'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Personalizar os campos de senha
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Senha'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Confirmar senha'
        })

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.nome = self.cleaned_data['nome']
        user.telemovel = self.cleaned_data.get('telemovel', '')
        user.data_nascimento = self.cleaned_data.get('data_nascimento')
        user.bilhete_identidade = self.cleaned_data.get('bilhete_identidade', '')
        user.bairro = self.cleaned_data.get('bairro', '')
        user.cidade = self.cleaned_data.get('cidade', '')
        user.municipio = self.cleaned_data.get('municipio', '')
        user.provincia = self.cleaned_data.get('provincia', '')
        
        if commit:
            user.save()
        return user
    
class ContaEditForm(forms.ModelForm):
    class Meta:
        model = Conta
        fields = ('username', 'email', 'nome', 'telemovel', 'data_nascimento',
                 'bilhete_identidade', 'bairro', 'cidade', 'municipio', 'provincia',
                 'is_staff', 'is_superuser', 'is_active')
        
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome de usuário'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Endereço de email'
            }),
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome completo'
            }),
            'telemovel': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Número de telemóvel'
            }),
            'data_nascimento': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'bilhete_identidade': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Bilhete de identidade'
            }),
            'bairro': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Bairro'
            }),
            'cidade': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Cidade'
            }),
            'municipio': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Município'
            }),
            'provincia': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Província'
            }),
            'is_staff': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_superuser': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Tornar campos não obrigatórios se necessário
        for field in self.fields:
            if field not in ['username', 'email', 'nome']:
                self.fields[field].required = False

from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from .models import Conta

class EditarPerfilForm(forms.ModelForm):
    class Meta:
        model = Conta
        fields = [
            'username', 'email', 'nome', 'telemovel', 'data_nascimento', 
            'bilhete_identidade', 'bairro', 'cidade', 'provincia', 'municipio'
        ]
        widgets = {
            'data_nascimento': forms.DateInput(attrs={'type': 'date'}),
            'telemovel': forms.TextInput(attrs={'placeholder': '+244...'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Adicionar classes Bootstrap aos campos
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
        
        # Tornar o campo username obrigatório apenas na criação
        if self.instance and self.instance.pk:
            self.fields['username'].required = False

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if Conta.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Este email já está em uso.')
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if Conta.objects.filter(username=username).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Este nome de usuário já está em uso.')
        return username

class AlterarSenhaForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Adicionar classes Bootstrap e placeholders
        self.fields['old_password'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Digite sua senha atual'
        })
        self.fields['new_password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Digite a nova senha'
        })
        self.fields['new_password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Confirme a nova senha'
        })