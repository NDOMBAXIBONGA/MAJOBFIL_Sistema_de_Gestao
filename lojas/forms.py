# forms.py
from django import forms
from .models import Loja

class LojaForm(forms.ModelForm):
    acc = forms.IntegerField(
        label='ACC (Total Produtos Vendidos)',
        required=False,
        widget=forms.NumberInput(attrs={
            'readonly': 'readonly',
            'class': 'form-control'
        })
    )
    
    class Meta:
        model = Loja
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Preenche o campo ACC com o valor calculado
        if self.instance and self.instance.pk:
            self.fields['acc'].initial = self.instance.acc_total_vendido