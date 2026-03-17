# forms.py
from django import forms
from .models import Produto, Recarga

class ProdutoForm(forms.ModelForm):
    class Meta:
        model = Produto
        fields = ['nome', 'preco', 'imagem']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Digite o nome do produto',
                'id': 'id_nome'
            }),
            'preco': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0',
                'id': 'id_preco'
            }),
            'imagem': forms.FileInput(attrs={
                'class': 'form-control',
                'id': 'id_imagem'
            }),
        }

class RecargaForm(forms.ModelForm):
    class Meta:
        model = Recarga
        fields = ['nome', 'preco', 'imagem']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Digite o nome da recarga',
                'id': 'id_nome'
            }),
            'preco': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0',
                'id': 'id_preco'
            }),
            'imagem': forms.FileInput(attrs={
                'class': 'form-control',
                'id': 'id_imagem'
            }),
        }

class ItemForm(forms.Form):
    TIPO_CHOICES = [
        ('produto', 'Produto'),
        ('recarga', 'Recarga'),
    ]
    
    tipo_item = forms.ChoiceField(
        choices=TIPO_CHOICES,
        required=True,
        widget=forms.HiddenInput(attrs={'id': 'tipo_item'})
    )
    
    nome = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Digite o nome do item',
            'id': 'id_nome',
            'name': 'nome'  # Adicione name aqui
        })
    )
    
    preco = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=True,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01',
            'min': '0',
            'id': 'id_preco',
            'name': 'preco'  # Adicione name aqui
        })
    )
    
    imagem = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'id': 'id_imagem',
            'name': 'imagem'  # Adicione name aqui
        })
    )