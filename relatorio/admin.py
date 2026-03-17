from django.contrib import admin
from .models import RelatorioDiario

@admin.register(RelatorioDiario)
class RelatorioDiarioAdmin(admin.ModelAdmin):
    list_display = [
        'data', 
        'get_usuario_nome',
        'get_loja_nome',
        'tpa', 'dstv', 'zap', 'unitel', 'africell', 
        'recargas', 'acc', 'total_geral', 'dm', 'moedas', 'gastos'
    ]
    list_filter = ['data', 'usuario', 'loja']
    search_fields = ['data', 'usuario__username', 'loja__nome']
    
    # Campos que serão sempre readonly
    readonly_fields = [
        'total_geral', 'criado_em', 'atualizado_em', 
        'get_usuario_nome', 'get_loja_nome'
    ]
    
    fieldsets = [
        ('Informações Básicas', {
            'fields': [
                'data', 
                'usuario',
                'loja'
            ]
        }),
        ('Serviços', {
            'fields': [
                'tpa', 'dstv', 'inicio_dstv', 'resto_dstv',
                'zap', 'resto_zap', 'unitel', 'resto_unitel',
                'africell', 'resto_africell'
            ]
        }),
        ('Vendas', {
            'fields': ['recargas', 'acc']
        }),
        ('Totais', {
            'fields': ['total_geral', 'dm', 'moedas', 'gastos']
        }),
        ('Observações', {
            'fields': ['observacao_falta']
        }),
        ('Auditoria', {
            'fields': ['criado_em', 'atualizado_em'],
            'classes': ['collapse']
        }),
    ]
    
    # Métodos customizados para mostrar informações relacionadas
    def get_usuario_nome(self, obj):
        return obj.usuario.username if obj.usuario else "N/A"
    get_usuario_nome.short_description = 'Usuário'
    get_usuario_nome.admin_order_field = 'usuario__username'
    
    def get_loja_nome(self, obj):
        return obj.loja.nome if obj.loja else "N/A"
    get_loja_nome.short_description = 'Loja'
    get_loja_nome.admin_order_field = 'loja__nome'
    
    # Método para definir campos readonly dinamicamente
    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj)
        
        # Se é uma edição (obj existe), torna usuario e loja readonly
        if obj:
            readonly_fields = list(readonly_fields) + ['usuario', 'loja']
        # Se é uma criação, apenas usuario é readonly (loja pode ser selecionada)
        else:
            readonly_fields = list(readonly_fields) + ['usuario']
            
        return readonly_fields
    
    # Filtra os relatórios por usuário (para não superusers)
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Usuários normais só veem seus próprios relatórios
        return qs.filter(usuario=request.user)
    
    # Filtra as opções do campo usuário (para não superusers)
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "usuario" and not request.user.is_superuser:
            kwargs["queryset"] = type(request.user).objects.filter(pk=request.user.pk)
            kwargs["empty_label"] = None  # Remove a opção vazia
        elif db_field.name == "loja" and not request.user.is_superuser:
            # Filtra lojas para usuários normais
            kwargs["queryset"] = request.user.lojas_gerenciadas.all()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    # Define o usuário automaticamente ao criar um relatório
    def save_model(self, request, obj, form, change):
        if not obj.usuario_id:
            obj.usuario = request.user
        
        # Para usuários não superusers, define a loja automaticamente se não foi selecionada
        if not request.user.is_superuser and not obj.loja_id:
            loja_usuario = request.user.lojas_gerenciadas.first()
            if loja_usuario:
                obj.loja = loja_usuario
        
        super().save_model(request, obj, form, change)
    
    # Remove o botão de deletar para usuários não superusers
    def has_delete_permission(self, request, obj=None):
        if obj and not request.user.is_superuser:
            return obj.usuario == request.user
        return super().has_delete_permission(request, obj)
    
    # Remove a permissão de adicionar se o usuário não tem lojas
    def has_add_permission(self, request):
        if not request.user.is_superuser and not request.user.lojas_gerenciadas.exists():
            return False
        return super().has_add_permission(request)
