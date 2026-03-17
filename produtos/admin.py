from django.contrib import admin
from django.utils.html import mark_safe
from .models import Produto

@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'preco', 'imagem_preview']
    search_fields = ['nome']
    list_filter = ['preco']
    list_editable = ['preco']
    
    fields = ['nome', 'preco', 'imagem', 'imagem_preview']
    readonly_fields = ['imagem_preview']
    
    def imagem_preview(self, obj):
        if obj.imagem:
            return mark_safe(f'<img src="{obj.imagem.url}" width="50" height="50" />')
        return "Sem imagem"
    
    imagem_preview.short_description = 'Imagem'

from django.contrib import admin
from .models import Recarga

@admin.register(Recarga)
class RecargaAdmin(admin.ModelAdmin):
    list_display = ['nome', 'preco', 'inicio', 'vendidas', 'total_vendas', 'resto']
    list_filter = ['inicio']
    search_fields = ['nome']