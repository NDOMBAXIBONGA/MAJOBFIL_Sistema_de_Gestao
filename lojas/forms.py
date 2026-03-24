# forms.py
from django import forms
from .models import Loja, EstoqueLoja, EstoqueRecarga, Venda, MovimentacaoEstoque
from produtos.models import Produto, Recarga
from datetime import datetime

class LojaForm(forms.ModelForm):
    acc = forms.IntegerField(
        label='ACC (Total Produtos Vendidos)',
        required=False,
        widget=forms.NumberInput(attrs={
            'readonly': 'readonly',
            'class': 'form-control'
        })
    )
    
    total_vendas = forms.DecimalField(
        label='Total em Vendas (Kz)',
        required=False,
        widget=forms.NumberInput(attrs={
            'readonly': 'readonly',
            'class': 'form-control'
        })
    )
    
    valor_estoque = forms.DecimalField(
        label='Valor Total do Estoque (Kz)',
        required=False,
        widget=forms.NumberInput(attrs={
            'readonly': 'readonly',
            'class': 'form-control'
        })
    )
    
    itens_estoque = forms.IntegerField(
        label='Itens em Estoque',
        required=False,
        widget=forms.NumberInput(attrs={
            'readonly': 'readonly',
            'class': 'form-control'
        })
    )
    
    class Meta:
        model = Loja
        fields = ['nome', 'bairro', 'cidade', 'provincia', 'municipio', 'gerentes', 
                  'acc', 'total_vendas', 'valor_estoque', 'itens_estoque']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'bairro': forms.TextInput(attrs={'class': 'form-control'}),
            'cidade': forms.TextInput(attrs={'class': 'form-control'}),
            'provincia': forms.Select(attrs={'class': 'form-select'}),
            'municipio': forms.TextInput(attrs={'class': 'form-control'}),
            'gerentes': forms.SelectMultiple(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Preenche os campos calculados com os valores da loja
        if self.instance and self.instance.pk:
            self.fields['acc'].initial = self.instance.acc_total_vendido()
            self.fields['total_vendas'].initial = self.instance.valor_total_vendas
            self.fields['valor_estoque'].initial = self.instance.valor_total_estoque
            self.fields['itens_estoque'].initial = self.instance.total_itens_em_estoque


class EntradaEstoqueForm(forms.Form):
    TIPO_ITEM_CHOICES = [
        ('produto', 'Produto'),
        ('recarga', 'Recarga'),
    ]
    
    tipo_item = forms.ChoiceField(
        choices=TIPO_ITEM_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'tipoItem'}),
        label='Tipo de Item'
    )
    
    loja = forms.ModelChoiceField(
        queryset=Loja.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Loja',
        empty_label='Selecione a loja...'
    )
    
    produto = forms.ModelChoiceField(
        queryset=Produto.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Produto',
        required=False,
        empty_label='Selecione o produto...'
    )
    
    recarga = forms.ModelChoiceField(
        queryset=Recarga.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Recarga',
        required=False,
        empty_label='Selecione a recarga...'
    )
    
    quantidade = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
        label='Quantidade'
    )
    
    valor_unitario = forms.DecimalField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        label='Valor Unitário (opcional)'
    )
    
    observacao = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': '3'}),
        label='Observação'
    )
    
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filtrar lojas baseado no usuário
        if user.is_superuser:
            self.fields['loja'].queryset = Loja.objects.all()
        else:
            self.fields['loja'].queryset = Loja.objects.filter(gerentes=user)
    
    def clean(self):
        cleaned_data = super().clean()
        tipo_item = cleaned_data.get('tipo_item')
        
        if tipo_item == 'produto':
            if not cleaned_data.get('produto'):
                self.add_error('produto', 'Selecione um produto para a entrada.')
            if cleaned_data.get('recarga'):
                cleaned_data['recarga'] = None
        elif tipo_item == 'recarga':
            if not cleaned_data.get('recarga'):
                self.add_error('recarga', 'Selecione uma recarga para a entrada.')
            if cleaned_data.get('produto'):
                cleaned_data['produto'] = None
        
        return cleaned_data


class DevolucaoForm(forms.Form):
    venda_id = forms.IntegerField(widget=forms.HiddenInput())
    
    quantidade = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'id': 'quantidadeDevolucao'}),
        label='Quantidade a Devolver',
        required=False,
        help_text='Deixe em branco para devolver toda a quantidade restante'
    )
    
    motivo = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Produto com defeito, Devolução do cliente, etc.'}),
        label='Motivo da Devolução',
        required=True
    )
    
    observacao = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': '3', 'placeholder': 'Observações adicionais...'}),
        label='Observações Adicionais'
    )
    
    def __init__(self, *args, **kwargs):
        self.venda = kwargs.pop('venda', None)
        super().__init__(*args, **kwargs)
        
        if self.venda:
            self.fields['venda_id'].initial = self.venda.id
            self.fields['quantidade'].help_text = f'Quantidade disponível para devolução: {self.venda.quantidade_restante}'
            
            # Limitar quantidade máxima
            self.fields['quantidade'].widget.attrs['max'] = self.venda.quantidade_restante
            self.fields['quantidade'].widget.attrs['placeholder'] = f'Máx: {self.venda.quantidade_restante}'
    
    def clean_quantidade(self):
        quantidade = self.cleaned_data.get('quantidade')
        
        if quantidade:
            if quantidade > self.venda.quantidade_restante:
                raise forms.ValidationError(
                    f'A quantidade a devolver ({quantidade}) excede a quantidade disponível ({self.venda.quantidade_restante}).'
                )
        else:
            # Se não especificou, devolve tudo
            quantidade = self.venda.quantidade_restante
        
        return quantidade


class FiltroMovimentacaoForm(forms.Form):
    loja = forms.ModelChoiceField(
        queryset=Loja.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Loja'
    )
    
    tipo_movimentacao = forms.ChoiceField(
        choices=[('', 'Todos')] + list(MovimentacaoEstoque.TIPO_MOVIMENTACAO),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Tipo de Movimentação'
    )
    
    tipo_item = forms.ChoiceField(
        choices=[('', 'Todos')] + list(MovimentacaoEstoque.TIPO_ITEM),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Tipo de Item'
    )
    
    data_inicio = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label='Data Início'
    )
    
    data_fim = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label='Data Fim'
    )
    
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if user.is_superuser:
            self.fields['loja'].queryset = Loja.objects.all()
        else:
            self.fields['loja'].queryset = Loja.objects.filter(gerentes=user)


class FiltroVendasForm(forms.Form):
    data_inicio = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label='Data Início'
    )
    
    data_fim = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label='Data Fim'
    )
    
    loja = forms.ModelChoiceField(
        queryset=Loja.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Loja'
    )
    
    status = forms.ChoiceField(
        choices=[('', 'Todos')] + list(Venda.STATUS_VENDA),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Status da Venda'
    )
    
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if user.is_superuser:
            self.fields['loja'].queryset = Loja.objects.all()
        else:
            self.fields['loja'].queryset = Loja.objects.filter(gerentes=user)
    
    def clean(self):
        cleaned_data = super().clean()
        data_inicio = cleaned_data.get('data_inicio')
        data_fim = cleaned_data.get('data_fim')
        
        if data_inicio and data_fim and data_inicio > data_fim:
            raise forms.ValidationError('A data inicial não pode ser maior que a data final.')
        
        return cleaned_data


class EstoqueForm(forms.ModelForm):
    class Meta:
        model = EstoqueLoja
        fields = ['loja', 'produto', 'quantidade']
        widgets = {
            'loja': forms.Select(attrs={'class': 'form-select'}),
            'produto': forms.Select(attrs={'class': 'form-select'}),
            'quantidade': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        }
    
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if not user.is_superuser:
            self.fields['loja'].queryset = Loja.objects.filter(gerentes=user)
    
    def clean_quantidade(self):
        quantidade = self.cleaned_data.get('quantidade')
        if quantidade < 0:
            raise forms.ValidationError('A quantidade não pode ser negativa.')
        return quantidade


class EstoqueRecargaForm(forms.ModelForm):
    class Meta:
        model = EstoqueRecarga
        fields = ['loja', 'recarga', 'quantidade']
        widgets = {
            'loja': forms.Select(attrs={'class': 'form-select'}),
            'recarga': forms.Select(attrs={'class': 'form-select'}),
            'quantidade': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        }
    
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if not user.is_superuser:
            self.fields['loja'].queryset = Loja.objects.filter(gerentes=user)
    
    def clean_quantidade(self):
        quantidade = self.cleaned_data.get('quantidade')
        if quantidade < 0:
            raise forms.ValidationError('A quantidade não pode ser negativa.')
        return quantidade


class EditarDataVendaForm(forms.Form):
    data_venda = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label='Nova Data da Venda',
        required=True
    )
    
    justificativa = forms.CharField(
        max_length=500,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': '3'}),
        label='Justificativa da Alteração',
        required=True,
        help_text='Explique o motivo da alteração da data'
    )
    
    def clean_data_venda(self):
        data_venda = self.cleaned_data.get('data_venda')
        
        if data_venda > datetime.now().date():
            raise forms.ValidationError('Não é possível definir uma data futura para a venda.')
        
        return data_venda


class VendaRetroativaForm(forms.Form):
    TIPO_ITEM_CHOICES = [
        ('produto', 'Produto'),
        ('recarga', 'Recarga'),
    ]
    
    estoque_id = forms.IntegerField(widget=forms.HiddenInput())
    item_type = forms.ChoiceField(choices=TIPO_ITEM_CHOICES, widget=forms.HiddenInput())
    
    data_venda = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label='Data da Venda',
        required=True
    )
    
    quantidade = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
        label='Quantidade',
        required=True
    )
    
    justificativa = forms.CharField(
        max_length=500,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': '3'}),
        label='Justificativa da Venda Retroativa',
        required=True,
        help_text='Explique o motivo do registro retroativo'
    )
    
    observacao = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': '2'}),
        label='Observações Adicionais'
    )
    
    def clean_data_venda(self):
        data_venda = self.cleaned_data.get('data_venda')
        
        if data_venda > datetime.now().date():
            raise forms.ValidationError('Não é possível registrar vendas com data futura.')
        
        # Verificar se não é muito antiga (opcional)
        from datetime import timedelta
        data_limite = datetime.now().date() - timedelta(days=365)
        if data_venda < data_limite:
            raise forms.ValidationError('Data muito antiga. Vendas retroativas só podem ser registradas até 1 ano atrás.')
        
        return data_venda