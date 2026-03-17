from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from lojas import views
from django.shortcuts import render
from django.conf.urls import handler404

def custom_404_view(request, exception):
    return render(request, '404.html', {
        'request_path': request.path,
        'exception': exception
    }, status=404)

def custom_403_view(request, exception):
    return render(request, '403.html', {
        'request_path': request.path,
        'exception': exception
    }, status=403)

urlpatterns = [
    path('admin/', admin.site.urls, name="admin"),
    path('', include("conta.urls")),
    path('balanco/', include("balanco.urls")),
    path('loja/', include("lojas.urls")),
    path('relatorio/', include("relatorio.urls")),
    path('produtos/', include("produtos.urls")),
    path('api/totais-vendas/', views.api_totais_vendas, name='api_totais_vendas'),
]

handler404 = custom_404_view
handler403 = 'majobfil.urls.custom_403_view'

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)