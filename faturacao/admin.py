from django.contrib import admin
from .models import ConfiguracaoEmpresa, SerieFiscal, MotivoIsencaoIVA, ClienteFiscal, Fatura, ItemFatura


@admin.register(ConfiguracaoEmpresa)
class ConfiguracaoEmpresaAdmin(admin.ModelAdmin):
    list_display = ['razao_social', 'nif', 'regime_iva', 'numero_certificado_agt', 'nome_software', 'versao_software']


@admin.register(SerieFiscal)
class SerieFiscalAdmin(admin.ModelAdmin):
    list_display = ['tipo_documento', 'serie', 'ano', 'ultimo_numero', 'ativa']
    list_filter = ['tipo_documento', 'ano', 'ativa']
    readonly_fields = ['ultimo_numero', 'ultimo_hash', 'criado_em']


@admin.register(MotivoIsencaoIVA)
class MotivoIsencaoIVAAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'mencao_legal', 'ativo']
    search_fields = ['codigo', 'mencao_legal', 'descricao']
    list_filter = ['ativo']


@admin.register(ClienteFiscal)
class ClienteFiscalAdmin(admin.ModelAdmin):
    list_display = ['nome_razao_social', 'nif', 'regime_iva', 'cidade', 'provincia', 'ativo']
    search_fields = ['nome_razao_social', 'nif', 'email', 'telefone']
    list_filter = ['regime_iva', 'provincia', 'ativo']


class ItemFaturaInline(admin.TabularInline):
    model = ItemFatura
    extra = 0
    readonly_fields = ['numero_linha', 'codigo_produto', 'descricao', 'quantidade', 'preco_unitario', 'desconto_linha', 'taxa_iva', 'valor_iva', 'motivo_isencao', 'subtotal_liquido', 'total_linha']
    can_delete = False


@admin.register(Fatura)
class FaturaAdmin(admin.ModelAdmin):
    list_display = ['numero_fatura', 'cliente_nome', 'data_emissao', 'total_bruto', 'status', 'hash_curto', 'operador']
    list_filter = ['status', 'data_emissao', 'serie_fiscal__tipo_documento']
    search_fields = ['numero_fatura', 'cliente_nome', 'cliente_nif', 'hash_curto']
    readonly_fields = [
        'serie_fiscal', 'numero_sequencial', 'numero_fatura', 'status', 
        'data_emissao', 'system_entry_date', 'data_vencimento',
        'emitente_nome', 'emitente_nif', 'emitente_endereco', 'emitente_regime_iva',
        'cliente', 'cliente_nome', 'cliente_nif', 'cliente_endereco',
        'total_incidencia', 'total_iva', 'total_descontos', 'total_retencao_fonte', 'total_bruto',
        'hash_anterior', 'dados_para_hash', 'hash_assinatura', 'hash_curto', 'versao_chave',
        'operador', 'criado_em'
    ]
    inlines = [ItemFaturaInline]
    
    def has_delete_permission(self, request, obj=None):
        # A AGT proíbe expressamente a eliminação de faturas emitidas
        return False
