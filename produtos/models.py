# models.py
from django.db import models
from django.core.exceptions import ValidationError
from decimal import Decimal
import os

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
    
    def save(self, *args, **kwargs):
        # Se o produto já existe no banco de dados
        if self.pk:
            # Busca o produto atual no banco
            old_produto = Produto.objects.filter(pk=self.pk).first()
            
            # Se existe imagem antiga e a imagem foi alterada
            if old_produto and old_produto.imagem and old_produto.imagem != self.imagem:
                # Remove o arquivo antigo
                if os.path.isfile(old_produto.imagem.path):
                    os.remove(old_produto.imagem.path)
        
        super().save(*args, **kwargs)
    
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

    def save(self, *args, **kwargs):
        # Se a recarga já existe no banco de dados
        if self.pk:
            # Busca a recarga atual no banco
            old_recarga = Recarga.objects.filter(pk=self.pk).first()
            
            # Se existe imagem antiga e a imagem foi alterada
            if old_recarga and old_recarga.imagem and old_recarga.imagem != self.imagem:
                # Remove o arquivo antigo
                if os.path.isfile(old_recarga.imagem.path):
                    os.remove(old_recarga.imagem.path)
        
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome