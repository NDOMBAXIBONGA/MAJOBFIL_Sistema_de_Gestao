from django.urls import path
from . import views

urlpatterns = [
    path('relatorios/criar/', views.criar_relatorio_diario, name='criar_relatorio_diario'),
    path('relatorios/editar/<int:pk>/', views.editar_relatorio_diario, name='editar_relatorio_diario'),
    path('relatorios/lista/', views.lista_relatorios, name='listar_relatorios_diarios'),
    path('relatorios/detalhes/<int:pk>/', views.detalhes_relatorio, name='detalhes_relatorio_diario'),
    path('relatorios/deletar/<int:pk>/', views.deletar_relatorio, name='excluir_relatorio_diario'),
#    path('relatorios/calcular-total/', views.calcular_total_geral, name='calcular_total_geral'),
]