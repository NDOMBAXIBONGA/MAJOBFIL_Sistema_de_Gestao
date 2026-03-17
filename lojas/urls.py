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
]