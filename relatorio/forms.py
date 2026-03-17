from django import forms
from .models import RelatorioDiario
from django.utils import timezone
from decimal import Decimal

class RelatorioDiarioForm(forms.ModelForm):
    class Meta:
        model = RelatorioDiario
        fields = [
            'loja', 'data', 'tpa', 'dstv', 'inicio_dstv', 'resto_dstv',
            'zap', 'resto_zap', 'unitel', 'resto_unitel',
            'africell', 'resto_africell', 'recargas', 'acc',
            'total_geral', 'dm', 'moedas', 'gastos', 'observacao_falta'
        ]
        widgets = {
            'loja': forms.Select(attrs={
                'class': 'form-control',
                'required': 'required'
            }),
            'data': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'value': timezone.now().date()
            }),
            'tpa': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'dstv': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'inicio_dstv': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'resto_dstv': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'zap': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'resto_zap': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'unitel': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'resto_unitel': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'africell': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'resto_africell': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'recargas': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'acc': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'total_geral': forms.NumberInput(attrs={
                'class': 'form-control bg-light',
                'step': '0.01',
                'min': '0',
                'readonly': 'readonly'
            }),
            'dm': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'moedas': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'gastos': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'observacao_falta': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descreva a observação sobre falta de dinheiro no caixa...'
            }),
        }
        labels = {
            'loja': 'Loja',
            'data': 'Data do Relatório',
            'tpa': 'TPA',
            'dstv': 'DSTV',
            'inicio_dstv': 'INICIO DA DSTV',
            'resto_dstv': 'RESTO DA DSTV',
            'zap': 'ZAP',
            'resto_zap': 'RESTO DA ZAP',
            'unitel': 'UNITEL',
            'resto_unitel': 'RESTO DA UNITEL',
            'africell': 'AFRICEL',
            'resto_africell': 'RESTO DA AFRICEL',
            'recargas': 'RECARGAS',
            'acc': 'ACC',
            'total_geral': 'TOTAL GERAL',
            'dm': 'DM',
            'moedas': 'MOEDAS',
            'gastos': 'GASTOS',
            'observacao_falta': 'Observação da Falta',
        }
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Se é uma nova instância, define o valor inicial do total_geral
        if not self.instance.pk:
            self.initial['total_geral'] = Decimal('0.00')
            
        # FILTRAR LOJAS DISPONÍVEIS BASEADO NO USUÁRIO LOGADO
        if self.request and self.request.user.is_authenticated:
            user = self.request.user
            
            if user.is_superuser:
                # Superuser vê todas as lojas ativas
                from lojas.models import Loja
                self.fields['loja'].queryset = Loja.objects.all()
            else:
                # Usuário normal vê apenas as lojas que gerencia
                self.fields['loja'].queryset = user.lojas_gerenciadas.all()
            
            # Se o usuário só tem uma loja, seleciona automaticamente
            lojas_disponiveis = self.fields['loja'].queryset
            if lojas_disponiveis.count() == 1 and not self.instance.pk:
                self.initial['loja'] = lojas_disponiveis.first()
                # Opcional: tornar o campo readonly se quiser
                # self.fields['loja'].widget.attrs['readonly'] = True
                # self.fields['loja'].widget.attrs['disabled'] = True
                # self.fields['loja'].required = False
        else:
            # Fallback se não há request (pode acontecer no admin)
            try:
                from lojas.models import Loja
                self.fields['loja'].queryset = Loja.objects.filter(ativa=True)
            except:
                pass
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Calcular totais para validação
        total_geral = cleaned_data.get('total_geral', Decimal('0.00'))
        dm = cleaned_data.get('dm', Decimal('0.00'))
        moedas = cleaned_data.get('moedas', Decimal('0.00'))
        tpa = cleaned_data.get('tpa', Decimal('0.00'))
        gastos = cleaned_data.get('gastos', Decimal('0.00'))
        
        total_arrecadado = dm + moedas + tpa + gastos
        
        # Validar observação obrigatória quando há falta de dinheiro
        if total_geral > total_arrecadado:
            observacao = cleaned_data.get('observacao_falta')
            if not observacao:
                self.add_error(
                    'observacao_falta', 
                    'É obrigatório preencher a observação quando há falta de dinheiro no caixa.'
                )
        
        # Validar data única por loja (apenas para novos relatórios)
        loja = cleaned_data.get('loja')
        data = cleaned_data.get('data')
        
        if loja and data:
            # Para edição, exclui a instância atual da verificação
            if self.instance.pk:
                relatorio_existente = RelatorioDiario.objects.filter(
                    loja=loja, 
                    data=data
                ).exclude(pk=self.instance.pk)
            else:
                relatorio_existente = RelatorioDiario.objects.filter(
                    loja=loja, 
                    data=data
                )
            
            if relatorio_existente.exists():
                self.add_error(
                    'data',
                    f'Já existe um relatório para a loja {loja.nome} na data {data}.'
                )
        
        # Validação adicional: verificar se o usuário tem permissão para a loja selecionada
        if self.request and loja and not self.request.user.is_superuser:
            lojas_permitidas = self.request.user.lojas_gerenciadas.all()
            if loja not in lojas_permitidas:
                self.add_error(
                    'loja',
                    'Você não tem permissão para criar relatórios para esta loja.'
                )
        
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Garante que o usuário está associado
        if self.request and not instance.usuario_id:
            instance.usuario = self.request.user
        
        # Se o usuário só tem uma loja e não selecionou nenhuma, usa a única disponível
        if self.request and not instance.loja and not self.request.user.is_superuser:
            lojas_usuario = self.request.user.lojas_gerenciadas.all()
            if lojas_usuario.count() == 1:
                instance.loja = lojas_usuario.first()
        
        if commit:
            instance.save()
        
        return instance