from django.urls import path
from . import views


urlpatterns = [
    # Principais
    path('', views.lista_balancos, name='lista_balancos'),
    path('balanco/<int:balanco_id>/', views.detalhe_balanco, name='detalhe_balanco'),
    path('balanco/criar/personalizado/', views.criar_balanco_personalizado, name='criar_balanco_personalizado'),
    path('balanco/excluir/<int:balanco_id>/', views.excluir_balanco, name='excluir_balanco'),
    
    # Geração rápida
    path('gerar/rapido/<str:periodo_tipo>/', views.gerar_balanco_rapido, name='gerar_balanco_rapido'),
    
    # Períodos específicos
    path('diario/', views.balanco_diario, name='balanco_diario'),
    path('semanal/', views.balanco_semanal, name='balanco_semanal'),
    path('mensal/', views.balanco_mensal, name='balanco_mensal'),
    path('anual/', views.balanco_anual, name='balanco_anual'),
    
    # APIs
    path('api/dados/<int:balanco_id>/', views.api_dados_balanco, name='api_dados_balanco'),

     # Estoque consolidado (produtos de todas as lojas)
    path('produtos/', views.listar_produtos_estoque, name='listar_produtos_estoque'),
    
    # Detalhe de produto com filtro por loja
    path('produto/<int:produto_id>/', views.detalhe_produto_loja, name='detalhe_produto_loja'),
    path('produto/<int:produto_id>/loja/<int:loja_id>/', views.detalhe_produto_loja, name='detalhe_produto_loja'),
    
    # Ações de estoque
    path('entrada/', views.criar_entrada_estoque, name='criar_entrada_estoque'),
    path('saida/', views.criar_saida_estoque, name='criar_saida_estoque'),
    
    # Exportação
    path('exportar/', views.exportar_estoque, name='exportar_estoque'),
    
    # URLs anteriores mantidas para compatibilidade
    #path('movimentos/', views.listar_movimentos_estoque, name='listar_movimentos_estoque'),
    #path('movimentos/exemplo/', views.criar_movimentos_exemplo, name='criar_movimentos_exemplo'),
    #path('movimentos/exportar/', views.exportar_movimentos, name='exportar_movimentos'),
    #path('movimentos/novo/', views.novo_movimento, name='novo_movimento'),
    #path('movimentos/<int:movimento_id>/', views.detalhe_movimento, name='detalhe_movimento'),
    #path('movimentos/<int:movimento_id>/editar/', views.editar_movimento, name='editar_movimento'),
    #path('movimentos/<int:movimento_id>/excluir/', views.excluir_movimento, name='excluir_movimento'),
    #path('dashboard/', views.dashboard_estoque, name='dashboard_estoque'),   
]