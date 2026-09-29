from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_faturas, name='lista_faturas'),
    path('nova/', views.emitir_fatura_view, name='emitir_fatura'),
    path('<int:fatura_id>/', views.detalhe_fatura, name='detalhe_fatura'),
    path('saft/', views.exportar_saft_view, name='exportar_saft'),
    path('api/validar-nif/', views.api_validar_nif, name='api_validar_nif'),
    path('faturar-venda/<int:venda_id>/', views.faturar_venda_view, name='faturar_venda'),
]
