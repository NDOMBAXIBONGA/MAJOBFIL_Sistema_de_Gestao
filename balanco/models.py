from django.db import models
from django.conf import settings
from django.db.models import Sum, Q, Count
from datetime import datetime, timedelta
from decimal import Decimal
import json
from django.db.models import Avg

class Balanco(models.Model):
    PERIODO_CHOICES = [
        ('diario', 'Diário'),
        ('semanal', 'Semanal'),
        ('mensal', 'Mensal'), 
        ('anual', 'Anual'),
        ('personalizado', 'Personalizado'),
    ]
    
    STATUS_CHOICES = [
        ('positivo', 'Positivo'),
        ('negativo', 'Negativo'),
        ('neutro', 'Neutro'),
    ]

    # Informações da Loja
    loja = models.ForeignKey(
        'lojas.Loja',
        on_delete=models.CASCADE,
        verbose_name='Loja',
        related_name='balancos'
    )
    
    # Período do Balanço
    periodo_tipo = models.CharField(
        max_length=15,
        choices=PERIODO_CHOICES,
        verbose_name='Tipo de Período'
    )
    
    data_inicio = models.DateField(verbose_name='Data de Início')
    data_fim = models.DateField(verbose_name='Data de Fim')
    descricao_periodo = models.CharField(max_length=100, blank=True, verbose_name='Descrição do Período')
    
    # === VENDAS ===
    total_vendas_produtos = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_vendas_recargas = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_vendas_geral = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    quantidade_vendas_produtos = models.PositiveIntegerField(default=0)
    quantidade_vendas_recargas = models.PositiveIntegerField(default=0)
    total_transacoes = models.PositiveIntegerField(default=0)
    
    # === RELATÓRIOS DIÁRIOS (SOMAS) ===
    # TV
    total_tpa = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_dstv = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_inicio_dstv = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_resto_dstv = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_zap = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_resto_zap = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Telefonia
    total_unitel = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_resto_unitel = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_africell = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_resto_africell = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Financeiro
    total_recargas_relatorios = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_acc_relatorios = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_geral_relatorios = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_dm = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_moedas = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_gastos = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # === MÉTRICAS CALCULADAS ===
    total_arrecadado = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    diferenca_caixa = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    custos_operacionais = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    lucro_bruto = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    margem_lucro = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Status
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='neutro')
    
    # Detalhes em JSON
    detalhes_vendas_diarias = models.JSONField(default=dict, blank=True)
    detalhes_relatorios_diarios = models.JSONField(default=dict, blank=True)
    detalhes_produtos = models.JSONField(default=dict, blank=True)
    detalhes_recargas = models.JSONField(default=dict, blank=True)
    detalhes_vendedores = models.JSONField(default=dict, blank=True)
    
    # Metadados
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        verbose_name = 'Balanço'
        verbose_name_plural = 'Balanços'
        ordering = ['-data_inicio', 'loja']
        unique_together = ['loja', 'periodo_tipo', 'data_inicio']
    
    def __str__(self):
        return f"Balanço {self.loja.nome} - {self.descricao_periodo}"
    
    def save(self, *args, **kwargs):
        if not self.descricao_periodo:
            self.descricao_periodo = f"{self.data_inicio.strftime('%d/%m/%Y')} a {self.data_fim.strftime('%d/%m/%Y')}"
        
        self.calcular_todos_dados()
        super().save(*args, **kwargs)
    
    def calcular_todos_dados(self):
        """Calcula todos os dados do balanço"""
        self.calcular_vendas()
        self.calcular_relatorios_diarios()
        self.calcular_metricas_financeiras()
        self.coletar_detalhes()
        self.definir_status()
    
    def calcular_vendas(self):
        """Calcula dados de vendas do período"""
        from lojas.models import Venda
        
        vendas_periodo = Venda.objects.filter(
            Q(estoque_loja__loja=self.loja) | Q(estoque_recarga__loja=self.loja),
            data_venda__date__range=[self.data_inicio, self.data_fim]
        )
        
        # Vendas de produtos
        vendas_produtos = vendas_periodo.filter(item_type='produto')
        self.total_vendas_produtos = vendas_produtos.aggregate(total=Sum('valor_total'))['total'] or Decimal('0.00')
        self.quantidade_vendas_produtos = vendas_produtos.count()
        
        # Vendas de recargas
        vendas_recargas = vendas_periodo.filter(item_type='recarga')
        self.total_vendas_recargas = vendas_recargas.aggregate(total=Sum('valor_total'))['total'] or Decimal('0.00')
        self.quantidade_vendas_recargas = vendas_recargas.count()
        
        self.total_vendas_geral = self.total_vendas_produtos + self.total_vendas_recargas
        self.total_transacoes = self.quantidade_vendas_produtos + self.quantidade_vendas_recargas
    
    def calcular_relatorios_diarios(self):
        """Calcula somas dos relatórios diários do período"""
        from relatorio.models import RelatorioDiario
        
        relatorios_periodo = RelatorioDiario.objects.filter(
            loja=self.loja,
            data__range=[self.data_inicio, self.data_fim]
        )
        
        # TV
        self.total_tpa = relatorios_periodo.aggregate(total=Sum('tpa'))['total'] or Decimal('0.00')
        self.total_dstv = relatorios_periodo.aggregate(total=Sum('dstv'))['total'] or Decimal('0.00')
        self.total_inicio_dstv = relatorios_periodo.aggregate(total=Sum('inicio_dstv'))['total'] or Decimal('0.00')
        self.total_resto_dstv = relatorios_periodo.aggregate(total=Sum('resto_dstv'))['total'] or Decimal('0.00')
        self.total_zap = relatorios_periodo.aggregate(total=Sum('zap'))['total'] or Decimal('0.00')
        self.total_resto_zap = relatorios_periodo.aggregate(total=Sum('resto_zap'))['total'] or Decimal('0.00')
        
        # Telefonia
        self.total_unitel = relatorios_periodo.aggregate(total=Sum('unitel'))['total'] or Decimal('0.00')
        self.total_resto_unitel = relatorios_periodo.aggregate(total=Sum('resto_unitel'))['total'] or Decimal('0.00')
        self.total_africell = relatorios_periodo.aggregate(total=Sum('africell'))['total'] or Decimal('0.00')
        self.total_resto_africell = relatorios_periodo.aggregate(total=Sum('resto_africell'))['total'] or Decimal('0.00')
        
        # Financeiro
        self.total_recargas_relatorios = relatorios_periodo.aggregate(total=Sum('recargas'))['total'] or Decimal('0.00')
        self.total_acc_relatorios = relatorios_periodo.aggregate(total=Sum('acc'))['total'] or Decimal('0.00')
        self.total_geral_relatorios = relatorios_periodo.aggregate(total=Sum('total_geral'))['total'] or Decimal('0.00')
        self.total_dm = relatorios_periodo.aggregate(total=Sum('dm'))['total'] or Decimal('0.00')
        self.total_moedas = relatorios_periodo.aggregate(total=Sum('moedas'))['total'] or Decimal('0.00')
        self.total_gastos = relatorios_periodo.aggregate(total=Sum('gastos'))['total'] or Decimal('0.00')
        
        # Totais calculados
        self.total_arrecadado = self.total_dm + self.total_moedas + self.total_tpa + self.total_gastos
        self.diferenca_caixa = self.total_arrecadado - self.total_geral_relatorios
    
    def calcular_metricas_financeiras(self):
        """Calcula métricas financeiras"""
        # Custos operacionais (30% das vendas totais)
        self.custos_operacionais = self.total_vendas_geral * Decimal('0.30')
        self.lucro_bruto = self.total_vendas_geral - self.custos_operacionais
        
        # Margem de lucro
        if self.total_vendas_geral > 0:
            self.margem_lucro = (self.lucro_bruto / self.total_vendas_geral) * 100
        else:
            self.margem_lucro = Decimal('0.00')
    
    def coletar_detalhes(self):
        """Coleta dados detalhados para análise - VERSÃO ATUALIZADA"""
        from lojas.models import Venda
        from relatorio.models import RelatorioDiario
        
        # === VENDAS POR DIA - DETALHADO ===
        vendas_por_dia_detalhadas = []
        data_atual = self.data_inicio
        while data_atual <= self.data_fim:
            # Vendas do dia
            vendas_dia = Venda.objects.filter(
                Q(estoque_loja__loja=self.loja) | Q(estoque_recarga__loja=self.loja),
                data_venda__date=data_atual
            )
            
            total_vendas_dia = vendas_dia.aggregate(total=Sum('valor_total'))['total'] or Decimal('0.00')
            
            # Detalhes por tipo
            vendas_produtos_dia = vendas_dia.filter(item_type='produto')
            vendas_recargas_dia = vendas_dia.filter(item_type='recarga')
            
            total_produtos_dia = vendas_produtos_dia.aggregate(total=Sum('valor_total'))['total'] or Decimal('0.00')
            total_recargas_dia = vendas_recargas_dia.aggregate(total=Sum('valor_total'))['total'] or Decimal('0.00')
            quantidade_produtos_dia = vendas_produtos_dia.count()
            quantidade_recargas_dia = vendas_recargas_dia.count()
            
            vendas_por_dia_detalhadas.append({
                'data': data_atual.strftime('%d/%m/%Y'),
                'total': float(total_vendas_dia),
                'produtos': {
                    'total': float(total_produtos_dia),
                    'quantidade': quantidade_produtos_dia
                },
                'recargas': {
                    'total': float(total_recargas_dia),
                    'quantidade': quantidade_recargas_dia
                },
                'total_transacoes': quantidade_produtos_dia + quantidade_recargas_dia
            })
            data_atual += timedelta(days=1)
        
        # === RELATÓRIOS POR DIA ===
        relatorios_por_dia_raw = RelatorioDiario.objects.filter(
            loja=self.loja,
            data__range=[self.data_inicio, self.data_fim]
        ).values('data').annotate(
            total_geral=Sum('total_geral'),
            total_dm=Sum('dm'),
            total_moedas=Sum('moedas'),
            total_tpa=Sum('tpa'),
            total_gastos=Sum('gastos')
        ).order_by('data')
        
        relatorios_por_dia = []
        for relatorio in relatorios_por_dia_raw:
            total_arrecadado_dia = (relatorio['total_dm'] or Decimal('0.00')) + \
                                (relatorio['total_moedas'] or Decimal('0.00')) + \
                                (relatorio['total_tpa'] or Decimal('0.00')) + \
                                (relatorio['total_gastos'] or Decimal('0.00'))
            
            relatorios_por_dia.append({
                'data': relatorio['data'].strftime('%d/%m/%Y'),
                'total_geral': float(relatorio['total_geral'] or 0.0),
                'total_arrecadado': float(total_arrecadado_dia),
                'dm': float(relatorio['total_dm'] or 0.0),
                'moedas': float(relatorio['total_moedas'] or 0.0),
                'tpa': float(relatorio['total_tpa'] or 0.0),
                'gastos': float(relatorio['total_gastos'] or 0.0)
            })
        
        # === CÁLCULOS ESPECÍFICOS DOS RELATÓRIOS ===
        
        # DSTV - Cálculo com 5%
        total_dstv_sem_resto = self.total_dstv - self.total_resto_dstv
        dstv_com_5_percent = total_dstv_sem_resto * Decimal('1.05')
        diferenca_dstv = dstv_com_5_percent - self.total_dstv
        
        # ZAP
        total_zap_sem_resto = self.total_zap - self.total_resto_zap
        
        # Unitel
        total_unitel_sem_resto = self.total_unitel - self.total_resto_unitel
        
        # Africell
        total_africell_sem_resto = self.total_africell - self.total_resto_africell
        
        # Status do balanço geral
        if self.total_geral_relatorios > self.total_arrecadado:
            status_balanco = 'falta'
            diferenca_balanco = self.total_geral_relatorios - self.total_arrecadado
        elif self.total_geral_relatorios < self.total_arrecadado:
            status_balanco = 'positivo'
            diferenca_balanco = self.total_arrecadado - self.total_geral_relatorios
        else:
            status_balanco = 'positivo'
            diferenca_balanco = Decimal('0.00')
        
        # === TOP PRODUTOS ===
        top_produtos_raw = Venda.objects.filter(
            estoque_loja__loja=self.loja,
            item_type='produto',
            data_venda__date__range=[self.data_inicio, self.data_fim]
        ).values(
            'estoque_loja__produto__nome',
            'estoque_loja__produto__preco'
        ).annotate(
            total_vendido=Sum('quantidade'),
            total_valor=Sum('valor_total'),
            numero_vendas=Count('id')
        ).order_by('-total_valor')[:10]
        
        top_produtos = []
        for produto in top_produtos_raw:
            top_produtos.append({
                'nome': produto['estoque_loja__produto__nome'],
                'preco_unitario': float(produto['estoque_loja__produto__preco'] or 0.0),
                'total_vendido': produto['total_vendido'],
                'total_valor': float(produto['total_valor'] or 0.0),
                'numero_vendas': produto['numero_vendas'],
                'media_venda': float(produto['total_valor'] or 0.0) / produto['numero_vendas'] if produto['numero_vendas'] > 0 else 0.0
            })
        
        # === TOP RECARGAS ===
        top_recargas_raw = Venda.objects.filter(
            estoque_recarga__loja=self.loja,
            item_type='recarga',
            data_venda__date__range=[self.data_inicio, self.data_fim]
        ).values(
            'estoque_recarga__recarga__nome',
            'estoque_recarga__recarga__preco'
        ).annotate(
            total_vendido=Sum('quantidade'),
            total_valor=Sum('valor_total'),
            numero_vendas=Count('id')
        ).order_by('-total_valor')[:10]
        
        top_recargas = []
        for recarga in top_recargas_raw:
            top_recargas.append({
                'nome': recarga['estoque_recarga__recarga__nome'],
                'preco_unitario': float(recarga['estoque_recarga__recarga__preco'] or 0.0),
                'total_vendido': recarga['total_vendido'],
                'total_valor': float(recarga['total_valor'] or 0.0),
                'numero_vendas': recarga['numero_vendas'],
                'media_venda': float(recarga['total_valor'] or 0.0) / recarga['numero_vendas'] if recarga['numero_vendas'] > 0 else 0.0
            })
        
        # === TOP VENDEDORES DETALHADO ===
        top_vendedores_raw = Venda.objects.filter(
            Q(estoque_loja__loja=self.loja) | Q(estoque_recarga__loja=self.loja),
            data_venda__date__range=[self.data_inicio, self.data_fim]
        ).values(
            'vendedor__id',
            'vendedor__nome',
            'vendedor__email'
        ).annotate(
            total_vendas=Count('id'),
            total_valor=Sum('valor_total'),
            media_venda=Avg('valor_total'),
            vendas_produtos=Count('id', filter=Q(item_type='produto')),
            vendas_recargas=Count('id', filter=Q(item_type='recarga'))
        ).order_by('-total_valor')[:10]
        
        top_vendedores = []
        for vendedor in top_vendedores_raw:
            top_vendedores.append({
                'id': vendedor['vendedor__id'],
                'nome': vendedor['vendedor__nome'] or 'N/A',
                'email': vendedor['vendedor__email'] or '',
                'total_vendas': vendedor['total_vendas'],
                'total_valor': float(vendedor['total_valor'] or 0.0),
                'media_venda': float(vendedor['media_venda'] or 0.0),
                'vendas_produtos': vendedor['vendas_produtos'],
                'vendas_recargas': vendedor['vendas_recargas'],
                'performance': 'alta' if vendedor['total_valor'] and vendedor['total_valor'] > 1000 else 'media' if vendedor['total_valor'] and vendedor['total_valor'] > 500 else 'baixa'
            })
        
        # === DADOS DOS RELATÓRIOS PARA O TEMPLATE ===
        dados_relatorios = {
            'dstv': {
                'total': float(self.total_dstv),
                'inicio': float(self.total_inicio_dstv),
                'resto': float(self.total_resto_dstv),
                'sem_resto': float(total_dstv_sem_resto),
                'com_5_percent': float(dstv_com_5_percent),
                'diferenca': float(diferenca_dstv),
                'status': 'falta' if diferenca_dstv > 0 else 'positivo'
            },
            'zap': {
                'total': float(self.total_zap),
                'resto': float(self.total_resto_zap),
                'sem_resto': float(total_zap_sem_resto)
            },
            'unitel': {
                'total': float(self.total_unitel),
                'resto': float(self.total_resto_unitel),
                'sem_resto': float(total_unitel_sem_resto)
            },
            'africell': {
                'total': float(self.total_africell),
                'resto': float(self.total_resto_africell),
                'sem_resto': float(total_africell_sem_resto)
            },
            'dm': float(self.total_dm),
            'moedas': float(self.total_moedas),
            'tpa': float(self.total_tpa),
            'gastos': float(self.total_gastos),
            'total_geral': float(self.total_geral_relatorios),
            'total_arrecadado': float(self.total_arrecadado),
            'diferenca_balanco': float(diferenca_balanco),
            'status_balanco': status_balanco
        }
        
        # Atribuir os dados convertidos
        self.detalhes_vendas_diarias = vendas_por_dia_detalhadas
        self.detalhes_relatorios_diarios = relatorios_por_dia
        self.detalhes_produtos = top_produtos
        self.detalhes_recargas = top_recargas
        self.detalhes_vendedores = top_vendedores
        
        # Salvar dados dos relatórios em JSON separado
        self.detalhes_relatorios = dados_relatorios

    def calcular_dados_relatorios_em_tempo_real(self):
        """Calcula dados dos relatórios em tempo real se necessário"""
        from decimal import Decimal
        
        try:
            # DSTV - Cálculo com 5%
            total_dstv_sem_resto = self.total_dstv - self.total_resto_dstv
            dstv_com_5_percent = total_dstv_sem_resto * Decimal('1.05')
            diferenca_dstv = dstv_com_5_percent - self.total_dstv
            
            # Status do balanço geral
            if self.total_geral_relatorios > self.total_arrecadado:
                status_balanco = 'falta'
                diferenca_balanco = self.total_geral_relatorios - self.total_arrecadado
            elif self.total_geral_relatorios < self.total_arrecadado:
                status_balanco = 'positivo'
                diferenca_balanco = self.total_arrecadado - self.total_geral_relatorios
            else:
                status_balanco = 'positivo'
                diferenca_balanco = Decimal('0.00')
            
            dados_relatorios = {
                'dstv': {
                    'total': float(self.total_dstv),
                    'inicio': float(self.total_inicio_dstv),
                    'resto': float(self.total_resto_dstv),
                    'sem_resto': float(total_dstv_sem_resto),
                    'com_5_percent': float(dstv_com_5_percent),
                    'diferenca': float(diferenca_dstv),
                    'status': 'falta' if diferenca_dstv > 0 else 'positivo'
                },
                'zap': {
                    'total': float(self.total_zap),
                    'resto': float(self.total_resto_zap),
                    'sem_resto': float(self.total_zap - self.total_resto_zap)
                },
                'unitel': {
                    'total': float(self.total_unitel),
                    'resto': float(self.total_resto_unitel),
                    'sem_resto': float(self.total_unitel - self.total_resto_unitel)
                },
                'africell': {
                    'total': float(self.total_africell),
                    'resto': float(self.total_resto_africell),
                    'sem_resto': float(self.total_africell - self.total_resto_africell)
                },
                'dm': float(self.total_dm),
                'moedas': float(self.total_moedas),
                'tpa': float(self.total_tpa),
                'gastos': float(self.total_gastos),
                'total_geral': float(self.total_geral_relatorios),
                'total_arrecadado': float(self.total_arrecadado),
                'diferenca_balanco': float(diferenca_balanco),
                'status_balanco': status_balanco
            }
            
            return dados_relatorios
            
        except Exception as e:
            print(f"Erro ao calcular dados em tempo real: {e}")
            return {}
    
    def definir_status(self):
        """Define o status do balanço"""
        if self.lucro_bruto > Decimal('1000.00'):
            self.status = 'positivo'
        elif self.lucro_bruto < Decimal('0.00'):
            self.status = 'negativo'
        else:
            self.status = 'neutro'

    def get_absolute_url(self):
       from django.urls import reverse
       return reverse('detalhe_balanco', args=[str(self.id)])

    @property
    def total_servicos_tv(self):
        """Total de serviços de TV"""
        return self.total_dstv + self.total_zap
    
    @property
    def total_servicos_telefonia(self):
        """Total de serviços de telefonia"""
        return self.total_unitel + self.total_africell
    
    @property
    def total_restos(self):
        """Total de restos"""
        return (self.total_resto_dstv + self.total_resto_zap + 
                self.total_resto_unitel + self.total_resto_africell)
    
    @classmethod
    def gerar_balanco(cls, loja, periodo_tipo, data_inicio=None, data_fim=None, usuario=None):
        """Gera um balanço para o período especificado"""
        hoje = datetime.now().date()
        
        if not data_inicio or not data_fim:
            if periodo_tipo == 'diario':
                data_inicio = hoje
                data_fim = hoje
            elif periodo_tipo == 'semanal':
                data_inicio = hoje - timedelta(days=hoje.weekday())
                data_fim = data_inicio + timedelta(days=6)
            elif periodo_tipo == 'mensal':
                data_inicio = hoje.replace(day=1)
                data_fim = (hoje.replace(month=hoje.month+1, day=1) if hoje.month < 12 
                           else hoje.replace(year=hoje.year+1, month=1, day=1)) - timedelta(days=1)
            elif periodo_tipo == 'anual':
                data_inicio = hoje.replace(month=1, day=1)
                data_fim = hoje.replace(month=12, day=31)
        
        balanco, created = cls.objects.get_or_create(
            loja=loja,
            periodo_tipo=periodo_tipo,
            data_inicio=data_inicio,
            defaults={
                'data_fim': data_fim,
                'criado_por': usuario
            }
        )
        
        if not created:
            balanco.data_fim = data_fim
            balanco.criado_por = usuario
            balanco.save()
        
        return balanco

class MovimentoEstoque(models.Model):
    """
    Modelo para gerenciar entradas e saídas de produtos no estoque
    """
    TIPO_MOVIMENTO_CHOICES = [
        ('entrada', 'Entrada'),
        ('saida', 'Saída'),
        ('ajuste', 'Ajuste'),
        ('devolucao', 'Devolução'),
        ('transferencia', 'Transferência'),
    ]
    
    MOTIVO_ENTRADA_CHOICES = [
        ('compra', 'Compra'),
        ('transferencia_entrada', 'Transferência de Entrada'),
        ('devolucao_cliente', 'Devolução de Cliente'),
        ('inventario', 'Ajuste de Inventário'),
        ('outro', 'Outro'),
    ]
    
    MOTIVO_SAIDA_CHOICES = [
        ('venda', 'Venda'),
        ('transferencia_saida', 'Transferência de Saída'),
        ('perda', 'Perda/Danificação'),
        ('consumo_interno', 'Consumo Interno'),
        ('inventario', 'Ajuste de Inventário'),
        ('outro', 'Outro'),
    ]
    
    # Identificação do movimento
    referencia = models.CharField(max_length=50, unique=True, verbose_name='Referência')
    tipo_movimento = models.CharField(max_length=15, choices=TIPO_MOVIMENTO_CHOICES, verbose_name='Tipo de Movimento')
    
    # Dados do produto
    loja = models.ForeignKey('lojas.Loja', on_delete=models.CASCADE, verbose_name='Loja')
    produto = models.ForeignKey('produtos.Produto', on_delete=models.CASCADE, verbose_name='Produto')
    
    # Quantidades
    quantidade_anterior = models.PositiveIntegerField(default=0, verbose_name='Quantidade Anterior')
    quantidade_movimento = models.PositiveIntegerField(default=0, verbose_name='Quantidade Movimentada')
    quantidade_atual = models.PositiveIntegerField(default=0, verbose_name='Quantidade Atual')
    
    # Valores financeiros
    custo_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Custo Unitário')
    custo_total = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='Custo Total')
    preco_venda_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Preço de Venda Unitário')
    
    # Motivo e informações
    motivo_tipo = models.CharField(max_length=30, blank=True, verbose_name='Tipo de Motivo')
    motivo_detalhado = models.TextField(blank=True, verbose_name='Motivo Detalhado')
    documento_referencia = models.CharField(max_length=100, blank=True, verbose_name='Documento de Referência')
    
    # Venda relacionada (se for saída por venda)
    venda = models.ForeignKey(
        'lojas.Venda', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name='Venda Relacionada',
        related_name='movimentos_estoque'
    )
    
    # Metadados
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Data do Movimento')
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True,
        verbose_name='Responsável'
    )
    
    # Informações adicionais
    fornecedor = models.CharField(max_length=200, blank=True, verbose_name='Fornecedor')
    nota_fiscal = models.CharField(max_length=50, blank=True, verbose_name='Nota Fiscal')
    data_documento = models.DateField(null=True, blank=True, verbose_name='Data do Documento')
    
    class Meta:
        verbose_name = 'Movimento de Estoque'
        verbose_name_plural = 'Movimentos de Estoque'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['referencia']),
            models.Index(fields=['produto', 'criado_em']),
            models.Index(fields=['loja', 'tipo_movimento']),
            models.Index(fields=['criado_em']),
        ]
    
    def __str__(self):
        return f"{self.referencia} - {self.produto.nome} - {self.tipo_movimento} ({self.quantidade_movimento})"
    
    def save(self, *args, **kwargs):
        # Gerar referência automática se não existir
        if not self.referencia:
            prefix = {
                'entrada': 'ENT',
                'saida': 'SAI',
                'ajuste': 'AJT',
                'devolucao': 'DEV',
                'transferencia': 'TRF'
            }.get(self.tipo_movimento, 'MOV')
            
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            self.referencia = f"{prefix}-{self.produto.id}-{timestamp}"
        
        # Calcular custo total
        if self.quantidade_movimento > 0 and self.custo_unitario > 0:
            self.custo_total = self.quantidade_movimento * self.custo_unitario
        
        # Definir motivo tipo com base no tipo de movimento
        if not self.motivo_tipo:
            if self.tipo_movimento == 'entrada':
                self.motivo_tipo = 'compra'
            elif self.tipo_movimento == 'saida':
                self.motivo_tipo = 'venda'
        
        super().save(*args, **kwargs)
    
    @property
    def get_motivo_display(self):
        """Retorna a descrição do motivo"""
        if self.tipo_movimento == 'entrada':
            return dict(self.MOTIVO_ENTRADA_CHOICES).get(self.motivo_tipo, self.motivo_tipo)
        elif self.tipo_movimento == 'saida':
            return dict(self.MOTIVO_SAIDA_CHOICES).get(self.motivo_tipo, self.motivo_tipo)
        return self.motivo_tipo
    
    @property
    def valor_total_potencial(self):
        """Valor total potencial de venda (se todas as unidades fossem vendidas)"""
        if self.tipo_movimento == 'entrada' and self.preco_venda_unitario > 0:
            return self.quantidade_movimento * self.preco_venda_unitario
        return 0
    
    @property
    def margem_potencial(self):
        """Margem potencial de lucro"""
        if self.valor_total_potencial > 0 and self.custo_total > 0:
            return ((self.valor_total_potencial - self.custo_total) / self.custo_total) * 100
        return 0
    
    @classmethod
    def registrar_entrada(cls, produto, loja, quantidade, custo_unitario, 
                         preco_venda_unitario, motivo_tipo='compra', 
                         motivo_detalhado='', fornecedor='', nota_fiscal='',
                         criado_por=None):
        """Método para registrar uma entrada de estoque"""
        from lojas.models import EstoqueLoja
        
        # Buscar ou criar estoque da loja
        estoque, created = EstoqueLoja.objects.get_or_create(
            loja=loja,
            produto=produto,
            defaults={'quantidade': 0}
        )
        
        # Registrar movimento
        movimento = cls(
            tipo_movimento='entrada',
            produto=produto,
            loja=loja,
            quantidade_anterior=estoque.quantidade,
            quantidade_movimento=quantidade,
            quantidade_atual=estoque.quantidade + quantidade,
            custo_unitario=custo_unitario,
            preco_venda_unitario=preco_venda_unitario,
            motivo_tipo=motivo_tipo,
            motivo_detalhado=motivo_detalhado,
            fornecedor=fornecedor,
            nota_fiscal=nota_fiscal,
            criado_por=criado_por,
            data_documento=datetime.now().date()
        )
        movimento.save()
        
        # Atualizar estoque
        estoque.quantidade += quantidade
        estoque.save()
        
        return movimento
    
    @classmethod
    def registrar_saida(cls, produto, loja, quantidade, motivo_tipo='venda', 
                       motivo_detalhado='', venda=None, criado_por=None):
        """Método para registrar uma saída de estoque"""
        from lojas.models import EstoqueLoja
        
        # Buscar estoque da loja
        try:
            estoque = EstoqueLoja.objects.get(loja=loja, produto=produto)
        except EstoqueLoja.DoesNotExist:
            raise ValueError(f"Produto {produto.nome} não encontrado no estoque da loja {loja.nome}")
        
        # Verificar se há estoque suficiente
        if estoque.quantidade < quantidade:
            raise ValueError(f"Estoque insuficiente. Disponível: {estoque.quantidade}, Requerido: {quantidade}")
        
        # Registrar movimento
        movimento = cls(
            tipo_movimento='saida',
            produto=produto,
            loja=loja,
            quantidade_anterior=estoque.quantidade,
            quantidade_movimento=quantidade,
            quantidade_atual=estoque.quantidade - quantidade,
            preco_venda_unitario=produto.preco if venda else produto.preco,
            motivo_tipo=motivo_tipo,
            motivo_detalhado=motivo_detalhado,
            venda=venda,
            criado_por=criado_por
        )
        movimento.save()
        
        # Atualizar estoque
        estoque.quantidade -= quantidade
        estoque.save()
        
        return movimento
    
    @property
    def estilo_tipo(self):
        """Retorna classes CSS baseadas no tipo de movimento"""
        styles = {
            'entrada': {'class': 'success', 'icon': 'fas fa-arrow-down', 'text': 'Entrada'},
            'saida': {'class': 'danger', 'icon': 'fas fa-arrow-up', 'text': 'Saída'},
            'ajuste': {'class': 'warning', 'icon': 'fas fa-adjust', 'text': 'Ajuste'},
            'devolucao': {'class': 'info', 'icon': 'fas fa-undo', 'text': 'Devolução'},
            'transferencia': {'class': 'primary', 'icon': 'fas fa-exchange-alt', 'text': 'Transferência'},
        }
        return styles.get(self.tipo_movimento, styles['ajuste'])