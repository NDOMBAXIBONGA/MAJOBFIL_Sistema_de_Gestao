# urls.py
from django.urls import path
from . import views

urlpatterns = [
    # URLs para produtos (function-based views)
    path('itens/', views.listar_todos_itens, name='listar_todos_itens'),
    path('produtos/cadastrar/', views.cadastrar_item, name='cadastrar_item'),
    path('itens/editar/<str:item_type>/<int:item_id>/', views.editar_item, name='editar_item'),
    path('itens/deletar/<str:item_type>/<int:item_id>/', views.deletar_item, name='deletar_item'),
]