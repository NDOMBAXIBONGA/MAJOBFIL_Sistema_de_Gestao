from django.db import models
from django.core.exceptions import ValidationError
from decimal import Decimal

class Produto(models.Model):
    nome = models.CharField(max_length=100, verbose_name='Nome do Produto')
    preco = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name='Preço'
    )
    imagem = models.ImageField(
        upload_to='produtos/',
        verbose_name='Imagem do Produto',
        blank=True,
        null=True
    )
    
    def __str__(self):
        return self.nome
    
    class Meta:
        verbose_name = 'Produto'
        verbose_name_plural = 'Produtos'

class Recarga(models.Model):
    nome = models.CharField(max_length=100)
    preco = models.DecimalField(max_digits=10, decimal_places=2)
    inicio = models.DateTimeField(auto_now_add=True)
    vendidas = models.IntegerField(default=0)
    total_vendas = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    resto = models.IntegerField(default=0)
    imagem = models.ImageField(upload_to='recargas/', null=True, blank=True)

    def __str__(self):
        return self.nome