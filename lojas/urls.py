from django.urls import path
from . import views

urlpatterns = [
    path('meus-produtos/', views.produtos_loja_gerente, name='nova_venda'),
    # API para os totais de vendas (ACC)

    # Lojas
    path('lojas/', views.listar_lojas, name='listar_lojas'),
    path('lojas/nova/', views.criar_loja, name='criar_loja'),
    path('lojas/<int:loja_id>/editar/', views.editar_loja, name='editar_loja'),
    path('lojas/<int:loja_id>/excluir/', views.excluir_loja, name='excluir_loja'),
    path('lojas/<int:loja_id>/detalhes/', views.detalhes_loja, name='detalhes_loja'),
    
    # Estoque
    path('estoque/', views.listar_estoque, name='listar_estoque'),
    path('estoque/adicionar/', views.adicionar_estoque, name='adicionar_estoque'),
    path('estoque/<int:estoque_id>/editar/', views.editar_estoque, name='editar_estoque'),
    
    # Vendas
    path('vendas/', views.listar_vendas, name='listar_vendas'),
    path('vendas/novo/', views.registrar_venda, name='registrar_venda'),
    path('vendas/<int:venda_id>/detalhes/', views.detalhes_venda, name='detalhes_venda'),
    path('vendas/registrar-retroativa/', views.registrar_venda_retroativa, name='registrar_venda_retroativa'),
    path('vendas/retroativas/', views.listar_vendas_retroativas, name='listar_vendas_retroativas'),
    

    # Entradas de estoque
    path('estoque/entrada/', views.registrar_entrada_estoque, name='registrar_entrada_estoque'),
    path('estoque/movimentacoes/', views.listar_movimentacoes_estoque, name='listar_movimentacoes_estoque'),
    
    # Devoluções
    path('vendas/devolucoes/', views.listar_devolucoes, name='listar_devolucoes'),
    path('vendas/devolucao/', views.registrar_devolucao, name='registrar_devolucao'),
    path('vendas/<int:venda_id>/detalhes-devolucao/', views.detalhes_venda_com_devolucao, name='detalhes_venda_com_devolucao'),
]