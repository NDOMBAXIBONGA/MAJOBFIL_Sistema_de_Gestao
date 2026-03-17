from django.db import models
from django.conf import settings
from decimal import Decimal

class RelatorioDiario(models.Model):
    loja = models.ForeignKey(
        'lojas.Loja', 
        on_delete=models.CASCADE, 
        verbose_name='Loja',
        related_name='relatorios_diarios',
        null=True  # Permite null para migrações
    )
    usuario = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    on_delete=models.CASCADE,
    verbose_name='Usuário/Gerente',
    related_name='relatorios_diarios',
    null=True  # Adicione esta linha temporariamente
    )
    data = models.DateField(verbose_name='Data')
    
    # Campos de TV
    tpa = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name='TPA',
        default=0
    )
    dstv = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name='DSTV',
        default=0
    )
    inicio_dstv = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name='INICIO DA DSTV',
        default=0
    )
    resto_dstv = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name='RESTO DA DSTV',
        default=0
    )
    zap = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name='ZAP',
        default=0
    )
    resto_zap = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name='RESTO DA ZAP',
        default=0
    )
    
    # Campos de Telefonia
    unitel = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name='UNITEL',
        default=0
    )
    resto_unitel = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name='RESTO DA UNITEL',
        default=0
    )
    africell = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name='AFRICEL',
        default=0
    )
    resto_africell = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name='RESTO DA AFRICEL',
        default=0
    )
    
    # Campos Financeiros
    recargas = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name='RECARGAS',
        default=0
    )

    # No models.py, na classe RelatorioDiario
    detalhes_recargas = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Detalhes das Recargas em JSON"
    )

    acc = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name='ACC',
        default=0
    )
    total_geral = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name='TOTAL GERAL',
        default=0
    )
    dm = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name='DM',
        default=0
    )
    moedas = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name='MOEDAS',
        default=0
    )
    gastos = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name='GASTOS',
        default=0
    )
    
    # Observações
    observacao_falta = models.TextField(
        verbose_name='Observação da Falta',
        blank=True,
        null=True,
        help_text='Observação obrigatória quando há falta de dinheiro no caixa'
    )
    
    # Metadados
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    def calcular_total_arrecadado(self):
        """Calcula o total arrecadado (DM + Moedas + TPA + Gastos)"""
        return (self.dm or Decimal('0.00')) + \
               (self.moedas or Decimal('0.00')) + \
               (self.tpa or Decimal('0.00')) + \
               (self.gastos or Decimal('0.00'))
    
    def calcular_diferenca(self):
        """Calcula a diferença entre total arrecadado e total geral"""
        return self.calcular_total_arrecadado() - self.total_geral
    
    def tem_campos_vazios(self):
        """Verifica se há campos importantes vazios (None ou 0)"""
        campos_obrigatorios = [
            'tpa', 'dstv', 'zap', 'unitel', 'africell', 
            'recargas', 'acc', 'dm', 'moedas', 'gastos'
        ]
        
        for campo in campos_obrigatorios:
            valor = getattr(self, campo)
            if valor is None or valor == Decimal('0.00'):
                return True
        return False
    
    @property
    def esta_completo(self):
        """Status Completo: Total Arrecadado > Total Geral OU iguais"""
        if self.tem_campos_vazios():
            return False
        return self.calcular_total_arrecadado() >= self.total_geral
    
    @property
    def esta_negativo(self):
        """Status Negativo: Total Geral > Total Arrecadado E campos preenchidos"""
        if self.tem_campos_vazios():
            return False
        return self.total_geral > self.calcular_total_arrecadado()
    
    @property
    def esta_pendente(self):
        """Status Pendente: Campos importantes vazios"""
        return self.tem_campos_vazios()
    
    def get_status(self):
        """Retorna o status do relatório"""
        if self.esta_completo:
            return 'completo'
        elif self.esta_negativo:
            return 'negativo'
        else:
            return 'pendente'
    
    def get_campos_monetarios(self):
        """Retorna lista de todos os campos monetários"""
        return ['dstv', 'zap', 'unitel', 'africell', 'recargas', 'acc', 'tpa', 'dm', 'moedas', 'gastos']
    
    def get_campos_editaveis(self):
        """Retorna lista de campos que podem ser editados (não preenchidos)"""
        campos_editaveis = []
        for campo in self.get_campos_monetarios():
            valor = getattr(self, campo)
            if valor == Decimal('0.00') or valor is None:
                campos_editaveis.append(campo)
        return campos_editaveis
    
    def get_campos_nao_editaveis(self):
        """Retorna lista de campos que NÃO podem ser editados (já preenchidos)"""
        campos_nao_editaveis = []
        for campo in self.get_campos_monetarios():
            valor = getattr(self, campo)
            if valor != Decimal('0.00') and valor is not None:
                campos_nao_editaveis.append(campo)
        return campos_nao_editaveis
    
    @property
    def esta_completamente_preenchido(self):
        """Verifica se todos os campos monetários estão preenchidos"""
        for campo in self.get_campos_monetarios():
            valor = getattr(self, campo)
            if valor == Decimal('0.00') or valor is None:
                return False
        return True
    
    def calcular_total_arrecadado(self):
        """Calcula o total arrecadado"""
        total = Decimal('0.00')
        for campo in self.get_campos_monetarios():
            valor = getattr(self, campo)
            if valor and valor != Decimal('0.00'):
                total += valor
        return total
    
    def calcular_diferenca(self):
        """Calcula a diferença entre total geral e total arrecadado"""
        return self.total_geral - self.calcular_total_arrecadado()

    class Meta:
        verbose_name = 'Relatório Diário'
        verbose_name_plural = 'Relatórios Diários'
        ordering = ['-data', 'loja']
        unique_together = ['loja', 'data']
    
    def __str__(self):
        nome_loja = self.loja.nome if self.loja else "Sem Loja"
        return f"Relatório {nome_loja} - {self.data}"
    
    def save(self, *args, **kwargs):
        # Se não tem loja definida, tenta pegar a loja do usuário
        if not self.loja and self.usuario:
            loja_usuario = self.usuario.lojas_gerenciadas.first()
            if loja_usuario:
                self.loja = loja_usuario
        
        # Calcular o total geral automaticamente antes de salvar
        self.calcular_total_geral()
        super().save(*args, **kwargs)
    
    def calcular_total_geral(self):
        """Calcula o total geral automaticamente"""
        campos_soma = [
            self.dstv,
            self.zap, 
            self.unitel, 
            self.africell, 
            self.recargas, 
            self.acc,
        ]
        
        total = Decimal('0.00')
        for campo in campos_soma:
            if campo is not None:
                total += campo
        
        self.total_geral = total
        return self.total_geral
    
    def calcular_total_vendas_dia(self):
        """Calcula o total de vendas do dia baseado nas vendas registradas para a loja"""
        from django.db.models import Sum
        
        try:
            if not self.loja:
                return Decimal('0.00')
                
            # Buscar vendas do dia e da loja específica
            from lojas.models import Venda
            vendas_dia = Venda.objects.filter(
                data_venda__date=self.data,
                estoque__loja=self.loja
            ).aggregate(total=Sum('valor_total'))
            
            return vendas_dia['total'] or Decimal('0.00')
        except:
            return Decimal('0.00')
    
    def calcular_total_arrecadado(self):
        """Calcula o total arrecadado (DM + Moedas + TPA + Gastos)"""
        return (self.dm or Decimal('0.00')) + \
               (self.moedas or Decimal('0.00')) + \
               (self.tpa or Decimal('0.00')) + \
               (self.gastos or Decimal('0.00'))
    
    def calcular_diferenca(self):
        """Calcula a diferença entre total geral e total arrecadado"""
        return self.total_geral - self.calcular_total_arrecadado()
    
    def tem_falta_dinheiro(self):
        """Verifica se há falta de dinheiro no caixa"""
        return self.calcular_diferenca() > Decimal('0.00')
    
    def get_loja_display(self):
        """Retorna o nome da loja ou uma string padrão se não tiver loja"""
        return self.loja.nome if self.loja else "Loja não definida"