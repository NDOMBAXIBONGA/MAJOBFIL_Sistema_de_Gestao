from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db.models import Sum, Q
from datetime import datetime, date
from produtos.models import Recarga

from django.db import models
from django.conf import settings
from django.db.models import Sum, Q, Count
from datetime import datetime

class Loja(models.Model):
    PROVINCIAS = [
        ('Bengo', 'Bengo'),
        ('Benguela', 'Benguela'),
        ('Bié', 'Bié'),
        ('Cabinda', 'Cabinda'),
        ('Cuando-Cubango', 'Cuando-Cubango'),
        ('Cuanza-Norte', 'Cuanza-Norte'),
        ('Cuanza-Sul', 'Cuanza-Sul'),
        ('Cunene', 'Cunene'),
        ('Huambo', 'Huambo'),
        ('Huíla', 'Huíla'),
        ('Luanda', 'Luanda'),
        ('Lunda-Norte', 'Lunda-Norte'),
        ('Lunda-Sul', 'Lunda-Sul'),
        ('Malanje', 'Malanje'),
        ('Moxico', 'Moxico'),
        ('Namibe', 'Namibe'),
        ('Uíge', 'Uíge'),
        ('Zaire', 'Zaire'),
    ]
    
    nome = models.CharField(max_length=100, verbose_name='Nome da Loja')
    bairro = models.CharField(max_length=100, verbose_name='Bairro')
    cidade = models.CharField(max_length=100, verbose_name='Cidade')
    provincia = models.CharField(max_length=50, choices=PROVINCIAS, verbose_name='Província')
    municipio = models.CharField(max_length=100, verbose_name='Município')
    gerentes = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        verbose_name='Gerentes', 
        related_name='lojas_gerenciadas'
    )
    
    def __str__(self):
        return self.nome
    
    @property
    def total_vendas(self):
        """
        Retorna o número total de transações de venda da loja (produtos + recargas)
        """
        return Venda.objects.filter(
            Q(estoque_loja__loja=self) | Q(estoque_recarga__loja=self)
        ).count()
    
    @property
    def total_vendas_quantidade(self):
        """
        Retorna a quantidade total de itens vendidos (soma das quantidades)
        """
        resultado = Venda.objects.filter(
            Q(estoque_loja__loja=self) | Q(estoque_recarga__loja=self)
        ).aggregate(total=Sum('quantidade'))
        return resultado['total'] or 0
    
    @property
    def valor_total_vendas(self):
        """
        Retorna o valor total das vendas da loja
        """
        resultado = Venda.objects.filter(
            Q(estoque_loja__loja=self) | Q(estoque_recarga__loja=self)
        ).aggregate(total=Sum('valor_total'))
        return resultado['total'] or 0
    
    @property
    def produtos_em_estoque(self):
        """Retorna o número de produtos diferentes em estoque"""
        return self.estoqueloja_set.filter(quantidade__gt=0).count()
    
    @property
    def recargas_em_estoque(self):
        """Retorna o número de recargas diferentes em estoque"""
        return self.estoquerecarga_set.filter(quantidade__gt=0).count()
    
    @property
    def total_itens_em_estoque(self):
        """Retorna o total de itens em estoque (quantidade)"""
        total_produtos = self.estoqueloja_set.aggregate(total=Sum('quantidade'))['total'] or 0
        total_recargas = self.estoquerecarga_set.aggregate(total=Sum('quantidade'))['total'] or 0
        return total_produtos + total_recargas
    
    @property
    def valor_total_estoque(self):
        """Retorna o valor total do estoque (produtos + recargas)"""
        valor_produtos = 0
        for estoque in self.estoqueloja_set.filter(quantidade__gt=0):
            valor_produtos += estoque.quantidade * estoque.produto.preco
        
        valor_recargas = 0
        for estoque in self.estoquerecarga_set.filter(quantidade__gt=0):
            valor_recargas += estoque.quantidade * estoque.recarga.preco
        
        return valor_produtos + valor_recargas

    def acc_total_vendido(self, data_relatorio=None):
        """
        Calcula o ACC (Total de Produtos Vendidos) para esta loja
        Se data_relatorio for fornecida, filtra por essa data
        """
        vendas_query = Venda.objects.filter(
            Q(estoque_loja__loja=self) | Q(estoque_recarga__loja=self)
        )
        
        if data_relatorio:
            if isinstance(data_relatorio, str):
                try:
                    data_relatorio = datetime.strptime(data_relatorio, '%Y-%m-%d').date()
                except ValueError:
                    return 0
            vendas_query = vendas_query.filter(data_venda__date=data_relatorio)
        
        total = vendas_query.aggregate(
            total_vendido=Sum('quantidade')
        )['total_vendido'] or 0
        return total
    
    def acc_valor_total_vendas(self, data_relatorio=None):
        """
        Calcula o valor total das vendas para esta loja
        Se data_relatorio for fornecida, filtra por essa data
        """
        vendas_query = Venda.objects.filter(
            Q(estoque_loja__loja=self) | Q(estoque_recarga__loja=self)
        )
        
        if data_relatorio:
            if isinstance(data_relatorio, str):
                try:
                    data_relatorio = datetime.strptime(data_relatorio, '%Y-%m-%d').date()
                except ValueError:
                    return 0
            vendas_query = vendas_query.filter(data_venda__date=data_relatorio)
        
        total = vendas_query.aggregate(
            total_valor=Sum('valor_total')
        )['total_valor'] or 0
        return total
    
    def get_vendas_por_periodo(self, data_inicio, data_fim):
        """
        Retorna vendas por período específico
        """
        return Venda.objects.filter(
            Q(estoque_loja__loja=self) | Q(estoque_recarga__loja=self),
            data_venda__date__range=[data_inicio, data_fim]
        )
    
    def get_ranking_produtos(self, data_inicio=None, data_fim=None):
        """
        Retorna ranking de produtos mais vendidos
        """
        from django.db.models import Count, Sum
        
        # Filtra vendas de produtos desta loja
        vendas_query = Venda.objects.filter(
            estoque_loja__loja=self,
            item_type='produto'
        )
        
        if data_inicio and data_fim:
            vendas_query = vendas_query.filter(
                data_venda__date__range=[data_inicio, data_fim]
            )
        
        return vendas_query.values(
            'estoque_loja__produto__nome',
            'estoque_loja__produto__id'
        ).annotate(
            total_vendido=Sum('quantidade'),
            total_valor=Sum('valor_total')
        ).order_by('-total_vendido')
    
    def get_ranking_recargas(self, data_inicio=None, data_fim=None):
        """
        Retorna ranking de recargas mais vendidas
        """
        from django.db.models import Count, Sum
        
        # Filtra vendas de recargas desta loja
        vendas_query = Venda.objects.filter(
            estoque_recarga__loja=self,
            item_type='recarga'
        )
        
        if data_inicio and data_fim:
            vendas_query = vendas_query.filter(
                data_venda__date__range=[data_inicio, data_fim]
            )
        
        return vendas_query.values(
            'estoque_recarga__recarga__nome',
            'estoque_recarga__recarga__id'
        ).annotate(
            total_vendido=Sum('quantidade'),
            total_valor=Sum('valor_total')
        ).order_by('-total_vendido')
    
    def get_vendas_hoje(self):
        """Retorna vendas do dia atual"""
        hoje = datetime.now().date()
        return Venda.objects.filter(
            Q(estoque_loja__loja=self) | Q(estoque_recarga__loja=self),
            data_venda__date=hoje
        )
    
    def get_vendas_mes_atual(self):
        """Retorna vendas do mês atual"""
        hoje = datetime.now().date()
        primeiro_dia_mes = hoje.replace(day=1)
        return Venda.objects.filter(
            Q(estoque_loja__loja=self) | Q(estoque_recarga__loja=self),
            data_venda__date__range=[primeiro_dia_mes, hoje]
        )
    
    def get_estoque_baixo(self):
        """Retorna itens com estoque baixo (menos de 10 unidades)"""
        produtos_baixo = self.estoqueloja_set.filter(quantidade__lt=10, quantidade__gt=0)
        recargas_baixo = self.estoquerecarga_set.filter(quantidade__lt=10, quantidade__gt=0)
        return {
            'produtos': produtos_baixo,
            'recargas': recargas_baixo,
            'total': produtos_baixo.count() + recargas_baixo.count()
        }
    
    def get_estoque_esgotado(self):
        """Retorna itens com estoque esgotado"""
        produtos_esgotado = self.estoqueloja_set.filter(quantidade=0)
        recargas_esgotado = self.estoquerecarga_set.filter(quantidade=0)
        return {
            'produtos': produtos_esgotado,
            'recargas': recargas_esgotado,
            'total': produtos_esgotado.count() + recargas_esgotado.count()
        }
    
    class Meta:
        verbose_name = 'Loja'
        verbose_name_plural = 'Lojas'

class EstoqueLoja(models.Model):
    loja = models.ForeignKey(Loja, on_delete=models.CASCADE)
    produto = models.ForeignKey('produtos.Produto', on_delete=models.CASCADE)
    quantidade = models.PositiveIntegerField(default=0)
    
    class Meta:
        unique_together = ['loja', 'produto']
        verbose_name = 'Estoque da Loja'
        verbose_name_plural = 'Estoques das Lojas'
    
    def __str__(self):
        return f"{self.loja.nome} - {self.produto.nome}: {self.quantidade}"
    
    @property
    def total_vendido(self):
        """Calcula o total vendido para este produto usando o novo relacionamento"""
        from django.db.models import Sum
        total = self.vendas_produto.aggregate(
            total=Sum('quantidade')
        )['total']
        return total or 0
    
    @property
    def valor_total_vendas(self):
        """Calcula o valor total das vendas para este produto usando o novo relacionamento"""
        from django.db.models import Sum
        total = self.vendas_produto.aggregate(
            total=Sum('valor_total')
        )['total']
        return total or 0
    
    @property
    def status_estoque(self):
        """Retorna o status do estoque"""
        if self.quantidade == 0:
            return 'esgotado'
        elif self.quantidade < 10:
            return 'baixo'
        else:
            return 'normal'

# models.py - adicione este modelo
class EstoqueRecarga(models.Model):
    loja = models.ForeignKey(Loja, on_delete=models.CASCADE, verbose_name='Loja')
    recarga = models.ForeignKey(Recarga, on_delete=models.CASCADE, verbose_name='Recarga')
    quantidade = models.PositiveIntegerField(default=0, verbose_name='Quantidade em Estoque')
    
    # Campos de data
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')
    
    class Meta:
        verbose_name = 'Estoque de Recarga'
        verbose_name_plural = 'Estoques de Recargas'
        unique_together = ['loja', 'recarga']
    
    def __str__(self):
        return f"{self.loja.nome} - {self.recarga.nome}: {self.quantidade}"
    
    @property
    def total_vendido(self):
        """Calcula o total vendido para esta recarga"""
        from django.db.models import Sum
        total = Venda.objects.filter(
            estoque_recarga=self,
            item_type='recarga'
        ).aggregate(total=Sum('quantidade'))['total']
        return total or 0
    
    @property
    def valor_total_vendas(self):
        """Calcula o valor total das vendas para esta recarga"""
        from django.db.models import Sum
        total = Venda.objects.filter(
            estoque_recarga=self,
            item_type='recarga'
        ).aggregate(total=Sum('valor_total'))['total']
        return total or 0
    
    @property
    def status_estoque(self):
        """Retorna o status do estoque"""
        if self.quantidade == 0:
            return 'esgotado'
        elif self.quantidade < 10:
            return 'baixo'
        else:
            return 'normal'

class Venda(models.Model):
    ITEM_TYPE_CHOICES = [
        ('produto', 'Produto'),
        ('recarga', 'Recarga'),
    ]

    # Para produtos
    estoque_loja = models.ForeignKey(
        'EstoqueLoja', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        verbose_name='Estoque do Produto',
        related_name='vendas_produto'
    )
    
    # Para recargas
    estoque_recarga = models.ForeignKey(
        'EstoqueRecarga',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name='Estoque da Recarga',
        related_name='vendas_recarga'
    )
    
    item_type = models.CharField(
        max_length=10, 
        choices=ITEM_TYPE_CHOICES, 
        default='produto',
        verbose_name='Tipo de Item'
    )
    
    quantidade = models.PositiveIntegerField(verbose_name='Quantidade Vendida')
    valor_total = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name='Valor Total'
    )
    vendedor = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        verbose_name='Vendedor'
    )
    data_venda = models.DateTimeField(auto_now_add=True, verbose_name='Data da Venda')
    observacao = models.TextField(blank=True, verbose_name='Observações')
    
    class Meta:
        verbose_name = 'Venda'
        verbose_name_plural = 'Vendas'
        ordering = ['-data_venda']
        indexes = [
            models.Index(fields=['estoque_loja', 'data_venda']),
            models.Index(fields=['estoque_recarga', 'data_venda']),
            models.Index(fields=['data_venda']),
        ]
    
    def __str__(self):
        if self.item_type == 'produto' and self.estoque_loja:
            return f"Venda #{self.id} - {self.estoque_loja.produto.nome} - {self.quantidade} unidades"
        elif self.item_type == 'recarga' and self.estoque_recarga:
            return f"Venda #{self.id} - {self.estoque_recarga.recarga.nome} - {self.quantidade} unidades"
        else:
            return f"Venda #{self.id}"
    
    def save(self, *args, **kwargs):
        # Calcular valor total baseado no tipo de item
        if self.item_type == 'produto' and self.estoque_loja:
            self.valor_total = self.quantidade * self.estoque_loja.produto.preco
        elif self.item_type == 'recarga' and self.estoque_recarga:
            self.valor_total = self.quantidade * self.estoque_recarga.recarga.preco
        
        # Validar que pelo menos um estoque está definido
        if not self.estoque_loja and not self.estoque_recarga:
            raise ValueError("Uma venda deve estar associada a um estoque de produto ou recarga")
        
        super().save(*args, **kwargs)
    
    @property
    def item_nome(self):
        """Retorna o nome do item vendido"""
        if self.item_type == 'produto' and self.estoque_loja:
            return self.estoque_loja.produto.nome
        elif self.item_type == 'recarga' and self.estoque_recarga:
            return self.estoque_recarga.recarga.nome
        return "Item não especificado"
    
    @property
    def loja(self):
        """Retorna a loja onde ocorreu a venda"""
        if self.item_type == 'produto' and self.estoque_loja:
            return self.estoque_loja.loja
        elif self.item_type == 'recarga' and self.estoque_recarga:
            return self.estoque_recarga.loja
        return None
    
    @property
    def preco_unitario(self):
        """Retorna o preço unitário do item"""
        if self.item_type == 'produto' and self.estoque_loja:
            return self.estoque_loja.produto.preco
        elif self.item_type == 'recarga' and self.estoque_recarga:
            return self.estoque_recarga.recarga.preco
        return 0