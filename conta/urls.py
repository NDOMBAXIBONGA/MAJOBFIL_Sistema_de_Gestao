# conta/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Autenticação
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.custom_logout, name='logout'),
    
    # Dashboard e Perfil
    path('dashboard/', views.dashboard, name='dashboard'),
    path('perfil/', views.perfil_usuario, name='perfil'),
    
    # Página inicial redireciona para login ou dashboard
    path('', views.dashboard, name='home'),

    # Paginas do Admin para manipulação do usuario
    path('criar_conta', views.criar_usuario, name='criar_usuario'),
    path('usuarios/', views.listar_usuarios, name='listar_usuarios'),
    path('usuarios/<int:user_id>/', views.detalhes_usuario, name='detalhes_usuario'),
    path('usuarios/<int:user_id>/editar/', views.editar_usuario, name='editar_usuario'),
    path('usuarios/<int:user_id>/deletar/', views.deletar_usuario, name='deletar_usuario'),
    path('usuarios/<int:user_id>/toggle-status/', views.toggle_usuario_status, name='toggle_usuario_status'),

    # Paginas do editar dados do usuario
    path('perfil/', views.perfil, name='perfil'),
    path('perfil/editar/', views.editar_perfil, name='editar_perfil'),
    path('perfil/alterar-senha/', views.alterar_senha, name='alterar_senha'),
    path('perfil/editar-ajax/', views.editar_perfil_ajax, name='editar_perfil_ajax'),

    # Url para redifinir a senha so user
    path('usuarios/redefinir-senha/', views.redefinir_senha_admin, name='redefinir_senha_admin'),
]