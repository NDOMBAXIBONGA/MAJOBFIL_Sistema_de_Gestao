# conta/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.contrib.auth.views import LoginView
from .forms import ContaCreationForm
from conta.utils import registrar_atividade
from .models import Conta

class CustomLoginView(LoginView):
    template_name = 'login.html'
    
    def form_valid(self, form):
        # Autenticar usando email em vez de username
        email = form.cleaned_data.get('username')  # O campo 'username' contém o email
        password = form.cleaned_data.get('password')
        
        # Tentar autenticar com email
        user = authenticate(self.request, email=email, password=password)
        
        if user is not None:
            if user.is_active:
                login(self.request, user)
                messages.success(self.request, f'Bem-vindo, {user.nome}!')
                return redirect('dashboard')
            else:
                messages.error(self.request, 'Sua conta está desativada.')
                return self.form_invalid(form)
        else:
            messages.error(self.request, 'Email ou senha incorretos.')
            return self.form_invalid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, 'Por favor, corrija os erros abaixo.')
        return super().form_invalid(form)

@login_required
def dashboard(request):
    """
    View para o dashboard principal com dados analíticos e gráficos dinâmicos
    """
    import json
    from datetime import date, timedelta
    from django.db.models import Sum, Q
    from lojas.models import Venda, Loja
    from faturacao.models import Fatura
    from .models import Atividade
    
    user = request.user
    hoje = date.today()
    
    # 1. Gráfico dos últimos 7 dias (faturamento diário)
    dias_labels = []
    valores_dias = []
    for i in range(6, -1, -1):
        dia = hoje - timedelta(days=i)
        dias_labels.append(dia.strftime('%d/%m'))
        tot = Venda.objects.filter(data_venda__date=dia).aggregate(total=Sum('valor_total'))['total'] or 0
        valores_dias.append(float(tot))
        
    # 2. Vendas por Loja (mês atual)
    lojas = Loja.objects.filter(ativo=True)[:6]
    lojas_labels = []
    lojas_valores = []
    primeiro_dia_mes = hoje.replace(day=1)
    
    for l in lojas:
        tot_loja = Venda.objects.filter(
            Q(estoque_loja__loja=l) | Q(estoque_recarga__loja=l),
            data_venda__date__gte=primeiro_dia_mes
        ).aggregate(total=Sum('valor_total'))['total'] or 0
        lojas_labels.append(l.nome)
        lojas_valores.append(float(tot_loja))
        
    # 3. Estatísticas fiscais
    total_faturas = Fatura.objects.count()
    faturas_mes = Fatura.objects.filter(data_emissao__gte=primeiro_dia_mes).count()
    
    # Atividades recentes do utilizador
    atividades_recentes = Atividade.objects.filter(usuario=user)[:6]
    
    context = {
        'user': user,
        'dias_labels': json.dumps(dias_labels),
        'valores_dias': json.dumps(valores_dias),
        'lojas_labels': json.dumps(lojas_labels),
        'lojas_valores': json.dumps(lojas_valores),
        'total_faturas': total_faturas,
        'faturas_mes': faturas_mes,
        'atividades_recentes': atividades_recentes,
    }
    
    return render(request, 'index.html', context)


@login_required
def perfil_usuario(request):
    """
    View para exibir e editar perfil do usuário
    """
    user = request.user
    
    if request.method == 'POST':
        # Aqui você pode adicionar lógica para atualizar o perfil
        messages.success(request, 'Perfil atualizado com sucesso!')
        return redirect('perfil')
    
    return render(request, 'perfil.html', {'user': user})

@login_required
def custom_logout(request):
    """
    View personalizada para logout
    """
    logout(request)
    messages.success(request, 'Você saiu da sua conta com sucesso.')
    return redirect('login')

def is_superuser(user):
    return user.is_superuser

@login_required
@user_passes_test(is_superuser)
def criar_usuario(request):
    if request.method == 'POST':
        form = ContaCreationForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                messages.success(request, f'Usuário {user.nome} criado com sucesso!')
                return redirect('listar_usuarios')
            except Exception as e:
                messages.error(request, f'Erro ao criar usuário: {str(e)}')
        else:
            # Adicionar mensagens de erro específicas
            for field, errors in form.errors.items():
                for error in errors:
                    field_name = form.fields[field].label if field in form.fields else field
                    messages.error(request, f'{field_name}: {error}')
    else:
        form = ContaCreationForm()
    
    return render(request, 'admin/criar_usuario.html', {'form': form})

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from .models import Conta
from .forms import ContaCreationForm, ContaEditForm
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

def is_superuser(user):
    return user.is_superuser

@login_required
@user_passes_test(is_superuser)
def listar_usuarios(request):
    # Filtro de busca
    query = request.GET.get('q', '')
    
    if query:
        usuarios = Conta.objects.filter(
            Q(nome__icontains=query) |
            Q(email__icontains=query) |
            Q(username__icontains=query) |
            Q(telemovel__icontains=query)
        ).order_by('-date_joined')
    else:
        usuarios = Conta.objects.all().order_by('-date_joined')
    
    # Calcular estatísticas
    total_usuarios = usuarios.count()
    usuarios_ativos = usuarios.filter(is_active=True).count()
    usuarios_inativos = total_usuarios - usuarios_ativos
    total_administradores = usuarios.filter(is_superuser=True).count()
    
    # Paginação
    page = request.GET.get('page', 1)
    paginator = Paginator(usuarios, 10)  # 10 usuários por página
    
    try:
        usuarios_paginados = paginator.page(page)
    except PageNotAnInteger:
        usuarios_paginados = paginator.page(1)
    except EmptyPage:
        usuarios_paginados = paginator.page(paginator.num_pages)
    
    context = {
        'usuarios': usuarios_paginados,
        'query': query,
        'total_usuarios': total_usuarios,
        'usuarios_ativos': usuarios_ativos,
        'usuarios_inativos': usuarios_inativos,
        'total_administradores': total_administradores,
    }
    
    return render(request, 'admin/listar_usuarios.html', context)

@login_required
@user_passes_test(is_superuser)
def detalhes_usuario(request, user_id):
    usuario = get_object_or_404(Conta, id=user_id)
    
    # Estatísticas do usuário (usando os métodos do modelo)
    total_vendas = usuario.total_vendas_usuario()
    vendas_30_dias = usuario.vendas_ultimos_30_dias()
    quantidade_vendida = usuario.total_quantidade_vendida()
    numero_vendas = usuario.numero_vendas_realizadas()
    
    context = {
        'usuario': usuario,
        'total_vendas': total_vendas,
        'vendas_30_dias': vendas_30_dias,
        'quantidade_vendida': quantidade_vendida,
        'numero_vendas': numero_vendas,
    }
    return render(request, 'admin/detalhes_usuario.html', context)

@login_required
@user_passes_test(is_superuser)
def editar_usuario(request, user_id):
    usuario = get_object_or_404(Conta, id=user_id)
    
    if request.method == 'POST':
        form = ContaEditForm(request.POST, instance=usuario)
        if form.is_valid():
            try:
                user = form.save()

                registrar_atividade(request.user, "Atualizou o perfil")
                messages.success(request, f'Usuário {user.nome} atualizado com sucesso!')
                return redirect('detalhes_usuario', user_id=user.id)
            except Exception as e:
                messages.error(request, f'Erro ao atualizar usuário: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = ContaEditForm(instance=usuario)
    
    context = {
        'form': form,
        'usuario': usuario
    }
    return render(request, 'admin/editar_usuario.html', context)

@login_required
@user_passes_test(is_superuser)
def deletar_usuario(request, user_id):
    usuario = get_object_or_404(Conta, id=user_id)
    
    if request.method == 'POST':
        try:
            nome_usuario = usuario.nome
            usuario.delete()
            messages.success(request, f'Usuário {nome_usuario} deletado com sucesso!')
            return redirect('listar_usuarios')
        except Exception as e:
            messages.error(request, f'Erro ao deletar usuário: {str(e)}')
            return redirect('detalhes_usuario', user_id=user_id)
    
    context = {
        'usuario': usuario
    }
    return render(request, 'admin/deletar_usuario.html', context)

@login_required
@user_passes_test(is_superuser)
@require_POST
def toggle_usuario_status(request, user_id):
    usuario = get_object_or_404(Conta, id=user_id)
    
    try:
        usuario.is_active = not usuario.is_active
        usuario.save()
        
        status = "ativado" if usuario.is_active else "desativado"
        messages.success(request, f'Usuário {usuario.nome} {status} com sucesso!')
    except Exception as e:
        messages.error(request, f'Erro ao alterar status do usuário: {str(e)}')
    
    return redirect('detalhes_usuario', user_id=user_id)

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.http import JsonResponse
from .forms import EditarPerfilForm, AlterarSenhaForm
from .models import Conta

@login_required
def perfil(request):
    """Página de visualização do perfil"""
    context = {
        'user': request.user
    }
    return render(request, 'perfil.html', context)

@login_required
def editar_perfil(request):
    """View para editar informações do perfil"""
    if request.method == 'POST':
        form = EditarPerfilForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Perfil atualizado com sucesso!')
            return redirect('perfil')
        else:
            messages.error(request, 'Por favor, corrija os erros abaixo.')
    else:
        form = EditarPerfilForm(instance=request.user)
    
    context = {
        'form': form,
        'user': request.user
    }
    return render(request, 'editar_perfil.html', context)

@login_required
def alterar_senha(request):
    """View para alterar a senha do usuário"""
    if request.method == 'POST':
        form = AlterarSenhaForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # Atualizar a sessão para não deslogar o usuário
            update_session_auth_hash(request, user)
            messages.success(request, 'Sua senha foi alterada com sucesso!')
            return redirect('perfil')
        else:
            messages.error(request, 'Por favor, corrija os erros abaixo.')
    else:
        form = AlterarSenhaForm(request.user)
    
    context = {
        'form': form,
        'user': request.user
    }
    return render(request, 'alterar_senha.html', context)

# View AJAX para edição rápida do perfil
@login_required
def editar_perfil_ajax(request):
    """View para edição via AJAX"""
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        form = EditarPerfilForm(request.POST, instance=request.user)
        
        if form.is_valid():
            perfil_atualizado = form.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Perfil atualizado com sucesso!',
                'dados': {
                    'username': perfil_atualizado.username,
                    'nome': perfil_atualizado.nome,
                    'email': perfil_atualizado.email,
                    'telemovel': perfil_atualizado.telemovel or 'Não informado',
                    'data_nascimento': perfil_atualizado.data_nascimento.strftime('%d/%m/%Y') if perfil_atualizado.data_nascimento else 'Não informado',
                    'bilhete_identidade': perfil_atualizado.bilhete_identidade or 'Não informado',
                    'bairro': perfil_atualizado.bairro or 'Não informado',
                    'cidade': perfil_atualizado.cidade or 'Não informado',
                    'provincia': perfil_atualizado.provincia or 'Não informado',
                    'municipio': perfil_atualizado.municipio or 'Não informado',
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            })
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})

# views.py
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from .models import Conta

@login_required
@user_passes_test(lambda u: u.is_superuser)
@require_POST
@csrf_protect
def redefinir_senha_admin(request):
    """View para administrador redefinir a senha de um usuário"""
    try:
        user_id = request.POST.get('user_id')
        nova_senha = request.POST.get('nova_senha')
        confirmar_senha = request.POST.get('confirmar_senha')
        
        # Validações básicas
        if not user_id or not nova_senha or not confirmar_senha:
            return JsonResponse({
                'success': False,
                'errors': ['Todos os campos são obrigatórios.']
            })
        
        if nova_senha != confirmar_senha:
            return JsonResponse({
                'success': False,
                'errors': ['As senhas não coincidem.']
            })
        
        # Buscar usuário
        try:
            usuario = Conta.objects.get(id=user_id)
        except Conta.DoesNotExist:
            return JsonResponse({
                'success': False,
                'errors': ['Usuário não encontrado.']
            })
        
        # Validação oficial de segurança da senha
        try:
            validate_password(nova_senha, user=usuario)
        except ValidationError as e:
            return JsonResponse({
                'success': False,
                'errors': list(e.messages)
            })
        
        # Redefinir senha
        usuario.set_password(nova_senha)
        usuario.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Senha redefinida com sucesso!'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'errors': ['Erro interno do servidor.']
        })