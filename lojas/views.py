from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.db.models import Sum, Q, Count
import json
from datetime import datetime, timedelta
from .models import Loja, EstoqueLoja, Venda

# Importar Produto e Recarga do app correto
try:
    from produtos.models import Produto, Recarga
except ImportError:
    from produtos.models import Produto, Recarga

# Importar EstoqueRecarga se existir
try:
    from .models import EstoqueRecarga
except ImportError:
    # Se não existir, vamos criar uma implementação básica
    class EstoqueRecarga:
        objects = None

def is_superuser(user):
    return user.is_superuser

@login_required
def produtos_loja_gerente(request):
    lojas_gerente = Loja.objects.filter(gerentes=request.user)
    
    if not lojas_gerente.exists():
        return render(request, 'vendas/nova_vendas.html', {
            'lojas': [],
            'produtos_estoque': [],
            'recargas_estoque': [],  # Adicionado
            'mensagem': 'Você não é gerente de nenhuma loja.'
        })
    
    if lojas_gerente.count() == 1:
        loja = lojas_gerente.first()
        return render_produtos_loja(request, loja)
    
    loja_id = request.GET.get('loja_id')
    if loja_id:
        loja_selecionada = get_object_or_404(Loja, id=loja_id, gerentes=request.user)
        return render_produtos_loja(request, loja_selecionada)
    else:
        return render(request, 'vendas/nova_vendas.html', {
            'loja_selecionada': None,
            'lojas': lojas_gerente,
            'produtos_estoque': [],
            'recargas_estoque': []  # Adicionado
        })

def render_produtos_loja(request, loja):
    # Obter estoque de produtos
    produtos_estoque = EstoqueLoja.objects.filter(
        loja=loja, 
        quantidade__gt=0
    ).select_related('produto').order_by('produto__nome')
    
    # Obter estoque de recargas - se o modelo existir
    recargas_estoque = []
    if EstoqueRecarga and hasattr(EstoqueRecarga, 'objects'):
        recargas_estoque = EstoqueRecarga.objects.filter(
            loja=loja,
            quantidade__gt=0
        ).select_related('recarga').order_by('recarga__nome')
    
    # Calcular estatísticas para produtos
    total_produtos = produtos_estoque.aggregate(total=Sum('quantidade'))['total'] or 0
    produtos_com_estoque = produtos_estoque.count()
    estoque_baixo_produtos = produtos_estoque.filter(quantidade__lte=5).count()
    
    # Calcular estatísticas para recargas
    total_recargas = recargas_estoque.aggregate(total=Sum('quantidade'))['total'] or 0 if recargas_estoque else 0
    recargas_com_estoque = recargas_estoque.count() if recargas_estoque else 0
    estoque_baixo_recargas = recargas_estoque.filter(quantidade__lte=5).count() if recargas_estoque else 0
    
    # Totais gerais
    total_estoque = total_produtos + total_recargas
    total_com_estoque = produtos_com_estoque + recargas_com_estoque
    estoque_baixo_total = estoque_baixo_produtos + estoque_baixo_recargas
    
    # Calcular valor total do estoque
    valor_total_estoque = 0
    
    # Para produtos
    for estoque in produtos_estoque:
        estoque.valor_total = estoque.quantidade * estoque.produto.preco
        valor_total_estoque += estoque.valor_total
    
    # Para recargas
    for estoque in recargas_estoque:
        estoque.valor_total = estoque.quantidade * estoque.recarga.preco
        valor_total_estoque += estoque.valor_total
    
    return render(request, 'vendas/nova_vendas.html', {
        'loja_selecionada': loja,
        'lojas': Loja.objects.filter(gerentes=request.user),
        'produtos_estoque': produtos_estoque,
        'recargas_estoque': recargas_estoque,  # Adicionado
        'total_estoque': total_estoque,
        'produtos_com_estoque': total_com_estoque,  # Agora inclui produtos e recargas
        'recargas_com_estoque': recargas_com_estoque,  # Adicionado
        'estoque_baixo': estoque_baixo_total,
        'valor_total_estoque': f"{valor_total_estoque:.2f}"
    })

@require_POST
@csrf_exempt
@login_required
def registrar_venda(request):
    try:
        # Debug: verificar o que está chegando
        print("=== REGISTRAR VENDA CHAMADA ===")
        print("Content-Type:", request.content_type)
        print("Método:", request.method)
        
        # Verificar se é JSON ou FormData
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST.dict()
        
        print("Dados recebidos:", data)
        
        estoque_id = data.get('estoque_id')
        item_type = data.get('item_type', 'produto').lower().strip()
        quantidade = data.get('quantidade')
        observacao = data.get('observacao', '')
        
        print(f"Item type: '{item_type}', Estoque ID: '{estoque_id}', Quantidade: '{quantidade}'")
        
        # Validar dados obrigatórios
        if not estoque_id:
            return JsonResponse({
                'success': False,
                'error': 'ID do estoque não fornecido.'
            })
        
        if not quantidade:
            return JsonResponse({
                'success': False,
                'error': 'Quantidade não fornecida.'
            })
        
        try:
            quantidade = int(quantidade)
            if quantidade <= 0:
                return JsonResponse({
                    'success': False,
                    'error': 'Quantidade deve ser maior que zero.'
                })
        except (ValueError, TypeError):
            return JsonResponse({
                'success': False,
                'error': 'Quantidade inválida.'
            })
        
        if item_type == 'produto':
            # Buscar o estoque de produto
            try:
                estoque = EstoqueLoja.objects.get(id=estoque_id)
                preco_unitario = estoque.produto.preco
                item_nome = estoque.produto.nome
                print(f"Produto encontrado: {item_nome}, Preço: {preco_unitario}")
            except EstoqueLoja.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Estoque de produto não encontrado.'
                })
                
        elif item_type == 'recarga':
            # Buscar o estoque de recarga
            try:
                estoque = EstoqueRecarga.objects.get(id=estoque_id)
                preco_unitario = estoque.recarga.preco
                item_nome = estoque.recarga.nome
                print(f"Recarga encontrada: {item_nome}, Preço: {preco_unitario}")
            except EstoqueRecarga.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Estoque de recarga não encontrado.'
                })
        else:
            return JsonResponse({
                'success': False,
                'error': f'Tipo de item inválido: "{item_type}". Tipos válidos: "produto" ou "recarga".'
            })
        
        # Verificar se o usuário é gerente da loja
        if request.user not in estoque.loja.gerentes.all() and not request.user.is_superuser:
            return JsonResponse({
                'success': False,
                'error': 'Você não tem permissão para vender itens desta loja.'
            })
        
        # Verificar se há estoque suficiente
        if estoque.quantidade < quantidade:
            return JsonResponse({
                'success': False,
                'error': f'Estoque insuficiente. Disponível: {estoque.quantidade}'
            })
        
        # Calcular valor total
        valor_total = quantidade * preco_unitario
        
        print(f"Valor total calculado: {valor_total}")
        
        # Registrar a venda
        if item_type == 'produto':
            venda = Venda.objects.create(
                estoque_loja=estoque,  # CORREÇÃO: usar estoque_loja
                item_type='produto',
                quantidade=quantidade,
                valor_total=valor_total,
                vendedor=request.user,
                observacao=observacao
            )
            print(f"Venda de produto criada: {venda.id}")
        else:  # recarga
            venda = Venda.objects.create(
                estoque_recarga=estoque,  # CORREÇÃO: usar estoque_recarga
                item_type='recarga',
                quantidade=quantidade,
                valor_total=valor_total,
                vendedor=request.user,
                observacao=observacao
            )
            print(f"Venda de recarga criada: {venda.id}")
        
        # Atualizar estoque
        estoque.quantidade -= quantidade
        estoque.save()
        
        print(f"Estoque atualizado: {estoque.quantidade}")
        
        return JsonResponse({
            'success': True,
            'venda_id': venda.id,
            'novo_estoque': estoque.quantidade,
            'valor_total': float(valor_total),
            'item_nome': item_nome
        })
        
    except Exception as e:
        print(f"Erro geral em registrar_venda: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        
        return JsonResponse({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        })

@require_GET
@csrf_exempt
def api_totais_vendas(request):
    """API simplificada para retornar os totais de vendas"""
    
    try:
        # Obter parâmetros
        loja_id = request.GET.get('loja_id')
        data_relatorio = request.GET.get('data_relatorio')
        
        if not loja_id:
            return JsonResponse({
                'status': 'error',
                'message': 'Parâmetro loja_id é obrigatório'
            }, status=400)
        
        # Buscar loja
        try:
            loja = Loja.objects.get(id=loja_id)
        except Loja.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': f'Loja com ID {loja_id} não encontrada'
            }, status=404)
        
        # Query base para vendas
        vendas_query = Venda.objects.filter(
            Q(estoque_loja__loja=loja) | Q(estoque_recarga__loja=loja)
        )
        
        # Aplicar filtro de data se fornecido
        if data_relatorio:
            try:
                data_obj = datetime.strptime(data_relatorio, '%Y-%m-%d').date()
                vendas_query = vendas_query.filter(data_venda__date=data_obj)
            except ValueError:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Formato de data inválido. Use YYYY-MM-DD'
                }, status=400)
        
        # Calcular totais
        total_quantidade = vendas_query.aggregate(total=Sum('quantidade'))['total'] or 0
        total_valor = vendas_query.aggregate(total=Sum('valor_total'))['total'] or 0
        total_vendas = vendas_query.count()
        
        # Calcular por tipo
        vendas_produtos = vendas_query.filter(item_type='produto')
        vendas_recargas = vendas_query.filter(item_type='recarga')
        
        response_data = {
            'acc_total': total_quantidade,
            'valor_total': float(total_valor),
            'total_vendas_count': total_vendas,
            
            'acc_produtos': vendas_produtos.aggregate(total=Sum('quantidade'))['total'] or 0,
            'acc_recargas': vendas_recargas.aggregate(total=Sum('quantidade'))['total'] or 0,
            'valor_produtos': float(vendas_produtos.aggregate(total=Sum('valor_total'))['total'] or 0),
            'valor_recargas': float(vendas_recargas.aggregate(total=Sum('valor_total'))['total'] or 0),
            'count_produtos': vendas_produtos.count(),
            'count_recargas': vendas_recargas.count(),
            
            'loja_nome': loja.nome,
            'data_relatorio': data_relatorio if data_relatorio else 'Todas as datas',
            'status': 'success'
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Erro interno: {str(e)}'
        }, status=500)

@login_required
def listar_lojas(request):
    if request.user.is_superuser:
        lojas = Loja.objects.all()
    else:
        lojas = Loja.objects.filter(gerentes=request.user)
    
    context = {
        'lojas': lojas,
        'total_lojas': lojas.count()
    }
    return render(request, 'lojas/listar_lojas.html', context)

@login_required
@user_passes_test(is_superuser)
def criar_loja(request):
    if request.method == 'POST':
        try:
            nome = request.POST.get('nome')
            bairro = request.POST.get('bairro')
            cidade = request.POST.get('cidade')
            provincia = request.POST.get('provincia')
            municipio = request.POST.get('municipio')
            gerentes_ids = request.POST.getlist('gerentes')
            
            loja = Loja.objects.create(
                nome=nome,
                bairro=bairro,
                cidade=cidade,
                provincia=provincia,
                municipio=municipio
            )
            
            if gerentes_ids:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                gerentes = User.objects.filter(id__in=gerentes_ids)
                loja.gerentes.set(gerentes)
            
            messages.success(request, 'Loja criada com sucesso!')
            return redirect('listar_lojas')
        except Exception as e:
            messages.error(request, f'Erro ao criar loja: {str(e)}')
    
    from django.contrib.auth import get_user_model
    User = get_user_model()
    gerentes = User.objects.filter(is_active=True)
    
    context = {
        'gerentes': gerentes,
        'provincias': Loja.PROVINCIAS
    }
    return render(request, 'lojas/criar_loja.html', context)

@login_required
@user_passes_test(is_superuser)
def editar_loja(request, loja_id):
    loja = get_object_or_404(Loja, id=loja_id)
    
    if request.method == 'POST':
        try:
            loja.nome = request.POST.get('nome')
            loja.bairro = request.POST.get('bairro')
            loja.cidade = request.POST.get('cidade')
            loja.provincia = request.POST.get('provincia')
            loja.municipio = request.POST.get('municipio')
            loja.save()
            
            gerentes_ids = request.POST.getlist('gerentes')
            if gerentes_ids:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                gerentes = User.objects.filter(id__in=gerentes_ids)
                loja.gerentes.set(gerentes)
            
            messages.success(request, 'Loja atualizada com sucesso!')
            return redirect('listar_lojas')
        except Exception as e:
            messages.error(request, f'Erro ao atualizar loja: {str(e)}')
    
    from django.contrib.auth import get_user_model
    User = get_user_model()
    gerentes = User.objects.filter(is_active=True)
    
    context = {
        'loja': loja,
        'gerentes': gerentes,
        'provincias': Loja.PROVINCIAS
    }
    return render(request, 'lojas/editar_loja.html', context)

@login_required
@user_passes_test(is_superuser)
def excluir_loja(request, loja_id):
    loja = get_object_or_404(Loja, id=loja_id)
    
    if request.method == 'POST':
        try:
            loja.delete()
            messages.success(request, 'Loja excluída com sucesso!')
        except Exception as e:
            messages.error(request, f'Erro ao excluir loja: {str(e)}')
        return redirect('listar_lojas')
    
    context = {'loja': loja}
    return render(request, 'lojas/excluir_loja.html', context)

# views.py
@login_required
def detalhes_loja(request, loja_id):
    loja = get_object_or_404(Loja, id=loja_id)
    
    # Verificar se o usuário tem acesso a esta loja
    if not request.user.is_superuser and request.user not in loja.gerentes.all():
        messages.error(request, 'Você não tem permissão para acessar esta loja.')
        return redirect('listar_lojas')
    
    # Estatísticas
    estoque_loja = EstoqueLoja.objects.filter(loja=loja)
    total_produtos = estoque_loja.count()
    total_estoque = estoque_loja.aggregate(total=Sum('quantidade'))['total'] or 0
    
    # Vendas recentes - CORRIGIDO: usar Q objects para ambos os tipos
    vendas_recentes = Venda.objects.filter(
        Q(estoque_loja__loja=loja) | Q(estoque_recarga__loja=loja)
    ).order_by('-data_venda')[:10]
    
    # Ranking de produtos
    ranking_produtos = loja.get_ranking_produtos()
    
    context = {
        'loja': loja,
        'total_produtos': total_produtos,
        'total_estoque': total_estoque,
        'vendas_recentes': vendas_recentes,
        'ranking_produtos': ranking_produtos,
    }
    return render(request, 'lojas/detalhes_loja.html', context)

# views.py - Corrigindo a view listar_estoque
@login_required
def listar_estoque(request):
    tipo_selecionado = request.GET.get('tipo', 'todos')
    
    if request.user.is_superuser:
        produtos_estoque = EstoqueLoja.objects.all()
        # Verificar se o modelo EstoqueRecarga existe
        if hasattr(EstoqueRecarga, 'objects'):
            recargas_estoque = EstoqueRecarga.objects.all()
        else:
            recargas_estoque = []
        lojas = Loja.objects.all()
    else:
        lojas_usuario = Loja.objects.filter(gerentes=request.user)
        produtos_estoque = EstoqueLoja.objects.filter(loja__in=lojas_usuario)
        if hasattr(EstoqueRecarga, 'objects'):
            recargas_estoque = EstoqueRecarga.objects.filter(loja__in=lojas_usuario)
        else:
            recargas_estoque = []
        lojas = lojas_usuario
    
    # Filtros
    loja_id = request.GET.get('loja')
    if loja_id:
        produtos_estoque = produtos_estoque.filter(loja_id=loja_id)
        if hasattr(EstoqueRecarga, 'objects'):
            recargas_estoque = recargas_estoque.filter(loja_id=loja_id)
    
    produto_nome = request.GET.get('produto')
    if produto_nome:
        produtos_estoque = produtos_estoque.filter(produto__nome__icontains=produto_nome)
        if hasattr(EstoqueRecarga, 'objects'):
            recargas_estoque = recargas_estoque.filter(recarga__nome__icontains=produto_nome)
    
    # NÃO tente atribuir às propriedades - elas são calculadas automaticamente
    # Apenas use as propriedades no template
    
    context = {
        'produtos_estoque': produtos_estoque,
        'recargas_estoque': recargas_estoque,
        'lojas': lojas,
        'tipo_selecionado': tipo_selecionado,
    }
    return render(request, 'estoque/listar_estoque.html', context)

# views.py
@login_required
def adicionar_estoque(request):
    if request.method == 'POST':
        try:
            tipo_item = request.POST.get('tipo_item', 'produto')
            loja_id = request.POST.get('loja')
            quantidade = request.POST.get('quantidade')
            
            loja = get_object_or_404(Loja, id=loja_id)
            
            # Verificar se usuário tem acesso à loja
            if not request.user.is_superuser and request.user not in loja.gerentes.all():
                messages.error(request, 'Você não tem permissão para adicionar estoque nesta loja.')
                return redirect('listar_estoque')
            
            if tipo_item == 'produto':
                produto_id = request.POST.get('produto')
                if not produto_id:
                    messages.error(request, 'Por favor, selecione um produto.')
                    return redirect('adicionar_estoque')
                
                produto = get_object_or_404(Produto, id=produto_id)
                
                estoque, created = EstoqueLoja.objects.get_or_create(
                    loja=loja,
                    produto=produto,
                    defaults={'quantidade': quantidade}
                )
                
                if not created:
                    estoque.quantidade += int(quantidade)
                    estoque.save()
                
                messages.success(request, f'Estoque do produto {produto.nome} atualizado com sucesso!')
                
            elif tipo_item == 'recarga':
                recarga_id = request.POST.get('recarga')
                if not recarga_id:
                    messages.error(request, 'Por favor, selecione uma recarga.')
                    return redirect('adicionar_estoque')
                
                recarga = get_object_or_404(Recarga, id=recarga_id)
                
                estoque, created = EstoqueRecarga.objects.get_or_create(
                    loja=loja,
                    recarga=recarga,
                    defaults={'quantidade': quantidade}
                )
                
                if not created:
                    estoque.quantidade += int(quantidade)
                    estoque.save()
                
                messages.success(request, f'Estoque da recarga {recarga.nome} atualizado com sucesso!')
            
            return redirect('listar_estoque')
            
        except Exception as e:
            messages.error(request, f'Erro ao adicionar estoque: {str(e)}')
    
    # Se for superuser, pode ver todas as lojas, senão apenas as que gerencia
    if request.user.is_superuser:
        lojas = Loja.objects.all()
    else:
        lojas = Loja.objects.filter(gerentes=request.user)
    
    context = {
        'lojas': lojas,
        'produtos': Produto.objects.all(),
        'recargas': Recarga.objects.all()
    }
    return render(request, 'estoque/adicionar_estoque.html', context)

# views.py
@login_required
def editar_estoque(request, estoque_id):
    # Primeiro tenta encontrar como EstoqueLoja (produto)
    try:
        estoque = get_object_or_404(EstoqueLoja, id=estoque_id)
        tipo = 'produto'
    except:
        # Se não encontrar, tenta como EstoqueRecarga
        try:
            estoque = get_object_or_404(EstoqueRecarga, id=estoque_id)
            tipo = 'recarga'
        except:
            messages.error(request, 'Estoque não encontrado.')
            return redirect('listar_estoque')
    
    # Verificar permissão
    if not request.user.is_superuser and request.user not in estoque.loja.gerentes.all():
        messages.error(request, 'Você não tem permissão para editar este estoque.')
        return redirect('listar_estoque')
    
    if request.method == 'POST':
        try:
            nova_quantidade = request.POST.get('quantidade')
            observacao = request.POST.get('observacao', '')
            
            # Registrar a alteração (opcional - você pode criar um modelo para histórico)
            quantidade_antiga = estoque.quantidade
            estoque.quantidade = nova_quantidade
            estoque.save()
            
            # Log da alteração
            if observacao:
                mensagem = f'Estoque alterado de {quantidade_antiga} para {nova_quantidade}. Observação: {observacao}'
            else:
                mensagem = f'Estoque alterado de {quantidade_antiga} para {nova_quantidade}'
            
            messages.success(request, 'Estoque atualizado com sucesso!')
            return redirect('listar_estoque')
            
        except Exception as e:
            messages.error(request, f'Erro ao atualizar estoque: {str(e)}')
    
    context = {'estoque': estoque}
    return render(request, 'estoque/editar_estoque.html', context)

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

@login_required
def listar_vendas(request):
    # Base queryset
    if request.user.is_superuser:
        vendas = Venda.objects.all().order_by('-data_venda')
        lojas = Loja.objects.all()
    else:
        lojas_usuario = Loja.objects.filter(gerentes=request.user)
        vendas = Venda.objects.filter(
            Q(estoque_loja__loja__in=lojas_usuario) | 
            Q(estoque_recarga__loja__in=lojas_usuario)
        ).order_by('-data_venda')
        lojas = lojas_usuario
    
    # Filtros (sem busca)
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    loja_id = request.GET.get('loja')
    
    # Aplicar filtros
    if data_inicio:
        vendas = vendas.filter(data_venda__date__gte=data_inicio)
    if data_fim:
        vendas = vendas.filter(data_venda__date__lte=data_fim)
    if loja_id:
        vendas = vendas.filter(
            Q(estoque_loja__loja_id=loja_id) | 
            Q(estoque_recarga__loja_id=loja_id)
        )
    
    # Estatísticas
    total_vendas = vendas.count()
    valor_total = vendas.aggregate(total=Sum('valor_total'))['total'] or 0
    quantidade_total = vendas.aggregate(total=Sum('quantidade'))['total'] or 0
    ticket_medio = valor_total / total_vendas if total_vendas > 0 else 0
    
    # Paginação
    page = request.GET.get('page', 1)
    paginator = Paginator(vendas, 4)
    
    try:
        vendas_paginadas = paginator.page(page)
    except PageNotAnInteger:
        vendas_paginadas = paginator.page(1)
    except EmptyPage:
        vendas_paginadas = paginator.page(paginator.num_pages)
    
    context = {
        'vendas': vendas_paginadas,
        'total_vendas': total_vendas,
        'valor_total': valor_total,
        'quantidade_total': quantidade_total,
        'ticket_medio': ticket_medio,
        'lojas': lojas,
    }
    return render(request, 'vendas/listar_vendas.html', context)

# views.py
@login_required
def detalhes_venda(request, venda_id):
    venda = get_object_or_404(Venda, id=venda_id)
    
    # Verificar permissão
    if not request.user.is_superuser:
        if venda.estoque_loja and request.user not in venda.estoque_loja.loja.gerentes.all():
            messages.error(request, 'Você não tem permissão para visualizar esta venda.')
            return redirect('listar_vendas')
        if venda.estoque_recarga and request.user not in venda.estoque_recarga.loja.gerentes.all():
            messages.error(request, 'Você não tem permissão para visualizar esta venda.')
            return redirect('listar_vendas')
    
    # Adicionar informações contextuais se necessário
    context = {
        'venda': venda,
    }
    return render(request, 'vendas/detalhes_venda.html', context)