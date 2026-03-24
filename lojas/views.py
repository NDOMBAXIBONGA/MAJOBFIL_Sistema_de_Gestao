from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.db.models import Sum, Q, Count, F
from django.db import transaction
import json
from datetime import datetime, timedelta
from .models import Loja, EstoqueLoja, Venda, MovimentacaoEstoque

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
            'recargas_estoque': [],
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
            'recargas_estoque': []
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
        'recargas_estoque': recargas_estoque,
        'total_estoque': total_estoque,
        'produtos_com_estoque': total_com_estoque,
        'recargas_com_estoque': recargas_com_estoque,
        'estoque_baixo': estoque_baixo_total,
        'valor_total_estoque': f"{valor_total_estoque:.2f}"
    })

@require_POST
@csrf_exempt
@login_required
def registrar_venda(request):
    try:
        print("=== REGISTRAR VENDA CHAMADA ===")
        
        # Verificar se é JSON ou FormData
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST.dict()
        
        estoque_id = data.get('estoque_id')
        item_type = data.get('item_type', 'produto').lower().strip()
        quantidade = data.get('quantidade')
        observacao = data.get('observacao', '')
        
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
        
        with transaction.atomic():
            if item_type == 'produto':
                try:
                    estoque = EstoqueLoja.objects.select_for_update().get(id=estoque_id)
                    preco_unitario = estoque.produto.preco
                    item_nome = estoque.produto.nome
                except EstoqueLoja.DoesNotExist:
                    return JsonResponse({
                        'success': False,
                        'error': 'Estoque de produto não encontrado.'
                    })
                    
            elif item_type == 'recarga':
                try:
                    estoque = EstoqueRecarga.objects.select_for_update().get(id=estoque_id)
                    preco_unitario = estoque.recarga.preco
                    item_nome = estoque.recarga.nome
                except EstoqueRecarga.DoesNotExist:
                    return JsonResponse({
                        'success': False,
                        'error': 'Estoque de recarga não encontrado.'
                    })
            else:
                return JsonResponse({
                    'success': False,
                    'error': f'Tipo de item inválido: "{item_type}".'
                })
            
            # Verificar permissão
            if request.user not in estoque.loja.gerentes.all() and not request.user.is_superuser:
                return JsonResponse({
                    'success': False,
                    'error': 'Você não tem permissão para vender itens desta loja.'
                })
            
            # Verificar estoque
            if estoque.quantidade < quantidade:
                return JsonResponse({
                    'success': False,
                    'error': f'Estoque insuficiente. Disponível: {estoque.quantidade}'
                })
            
            # Calcular valor total
            valor_total = quantidade * preco_unitario
            
            # Registrar quantidade anterior
            quantidade_anterior = estoque.quantidade
            
            # Atualizar estoque
            estoque.quantidade -= quantidade
            estoque.save()
            
            # Registrar a venda
            if item_type == 'produto':
                venda = Venda.objects.create(
                    estoque_loja=estoque,
                    item_type='produto',
                    quantidade=quantidade,
                    valor_total=valor_total,
                    vendedor=request.user,
                    observacao=observacao,
                    status='normal'
                )
            else:
                venda = Venda.objects.create(
                    estoque_recarga=estoque,
                    item_type='recarga',
                    quantidade=quantidade,
                    valor_total=valor_total,
                    vendedor=request.user,
                    observacao=observacao,
                    status='normal'
                )
            
            # Registrar movimentação de saída
            MovimentacaoEstoque.objects.create(
                loja=estoque.loja,
                tipo_movimentacao='saida',
                tipo_item=item_type,
                produto=estoque.produto if item_type == 'produto' else None,
                recarga=estoque.recarga if item_type == 'recarga' else None,
                quantidade=quantidade,
                quantidade_anterior=quantidade_anterior,
                quantidade_nova=estoque.quantidade,
                valor_unitario=preco_unitario,
                valor_total=valor_total,
                observacao=f"Venda #{venda.id} - {observacao}",
                venda=venda,
                usuario=request.user
            )
        
        return JsonResponse({
            'success': True,
            'venda_id': venda.id,
            'novo_estoque': estoque.quantidade,
            'valor_total': float(valor_total),
            'item_nome': item_nome
        })
        
    except Exception as e:
        print(f"Erro em registrar_venda: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        })

# ==================== FUNÇÃO PARA REGISTRAR ENTRADA NO ESTOQUE ====================

@login_required
@user_passes_test(is_superuser)
def registrar_entrada_estoque(request):
    """
    Função para registrar entrada de produtos/recargas no estoque
    """
    if request.method == 'POST':
        try:
            with transaction.atomic():
                tipo_item = request.POST.get('tipo_item', 'produto')
                loja_id = request.POST.get('loja')
                quantidade = request.POST.get('quantidade')
                observacao = request.POST.get('observacao', '')
                valor_unitario_str = request.POST.get('valor_unitario', '').strip()
                
                # Validar quantidade
                if not quantidade:
                    messages.error(request, 'Por favor, informe a quantidade.')
                    return redirect('registrar_entrada_estoque')
                
                try:
                    quantidade = int(quantidade)
                    if quantidade <= 0:
                        messages.error(request, 'A quantidade deve ser maior que zero.')
                        return redirect('registrar_entrada_estoque')
                except (ValueError, TypeError):
                    messages.error(request, 'Quantidade inválida.')
                    return redirect('registrar_entrada_estoque')
                
                # Processar valor unitário (pode estar vazio)
                valor_unitario = None
                if valor_unitario_str:
                    try:
                        valor_unitario = float(valor_unitario_str)
                        if valor_unitario < 0:
                            messages.error(request, 'O valor unitário não pode ser negativo.')
                            return redirect('registrar_entrada_estoque')
                    except ValueError:
                        messages.error(request, 'Valor unitário inválido.')
                        return redirect('registrar_entrada_estoque')
                
                loja = get_object_or_404(Loja, id=loja_id)
                
                # Verificar permissão
                if not request.user.is_superuser and request.user not in loja.gerentes.all():
                    messages.error(request, 'Você não tem permissão para adicionar estoque nesta loja.')
                    return redirect('listar_estoque')
                
                if tipo_item == 'produto':
                    produto_id = request.POST.get('produto')
                    if not produto_id:
                        messages.error(request, 'Por favor, selecione um produto.')
                        return redirect('registrar_entrada_estoque')
                    
                    produto = get_object_or_404(Produto, id=produto_id)
                    
                    # Buscar ou criar estoque
                    estoque, created = EstoqueLoja.objects.select_for_update().get_or_create(
                        loja=loja,
                        produto=produto,
                        defaults={'quantidade': 0}
                    )
                    
                    # Registrar quantidade anterior
                    quantidade_anterior = estoque.quantidade
                    
                    # Atualizar estoque
                    estoque.quantidade += quantidade
                    estoque.save()
                    
                    # Determinar valor unitário e total
                    if valor_unitario:
                        preco_usado = valor_unitario
                    else:
                        preco_usado = produto.preco
                    
                    valor_total = quantidade * preco_usado
                    
                    # Registrar movimentação
                    MovimentacaoEstoque.objects.create(
                        loja=loja,
                        tipo_movimentacao='entrada',
                        tipo_item='produto',
                        produto=produto,
                        quantidade=quantidade,
                        quantidade_anterior=quantidade_anterior,
                        quantidade_nova=estoque.quantidade,
                        valor_unitario=preco_usado,
                        valor_total=valor_total,
                        observacao=observacao,
                        usuario=request.user
                    )
                    
                    messages.success(request, f'Entrada de {quantidade} unidade(s) de {produto.nome} registrada com sucesso!')
                    
                elif tipo_item == 'recarga':
                    recarga_id = request.POST.get('recarga')
                    if not recarga_id:
                        messages.error(request, 'Por favor, selecione uma recarga.')
                        return redirect('registrar_entrada_estoque')
                    
                    recarga = get_object_or_404(Recarga, id=recarga_id)
                    
                    # Buscar ou criar estoque
                    estoque, created = EstoqueRecarga.objects.select_for_update().get_or_create(
                        loja=loja,
                        recarga=recarga,
                        defaults={'quantidade': 0}
                    )
                    
                    # Registrar quantidade anterior
                    quantidade_anterior = estoque.quantidade
                    
                    # Atualizar estoque
                    estoque.quantidade += quantidade
                    estoque.save()
                    
                    # Determinar valor unitário e total
                    if valor_unitario:
                        preco_usado = valor_unitario
                    else:
                        preco_usado = recarga.preco
                    
                    valor_total = quantidade * preco_usado
                    
                    # Registrar movimentação
                    MovimentacaoEstoque.objects.create(
                        loja=loja,
                        tipo_movimentacao='entrada',
                        tipo_item='recarga',
                        recarga=recarga,
                        quantidade=quantidade,
                        quantidade_anterior=quantidade_anterior,
                        quantidade_nova=estoque.quantidade,
                        valor_unitario=preco_usado,
                        valor_total=valor_total,
                        observacao=observacao,
                        usuario=request.user
                    )
                    
                    messages.success(request, f'Entrada de {quantidade} unidade(s) de {recarga.nome} registrada com sucesso!')
                
                return redirect('listar_estoque')
                
        except Exception as e:
            print(f"Erro ao registrar entrada: {str(e)}")
            import traceback
            print(traceback.format_exc())
            messages.error(request, f'Erro ao registrar entrada: {str(e)}')
            return redirect('registrar_entrada_estoque')
    
    # GET - mostrar formulário
    if request.user.is_superuser:
        lojas = Loja.objects.all()
    else:
        lojas = Loja.objects.filter(gerentes=request.user)
    
    context = {
        'lojas': lojas,
        'produtos': Produto.objects.all(),
        'recargas': Recarga.objects.all(),
    }
    return render(request, 'estoque/registrar_entrada.html', context)

# ==================== FUNÇÃO PARA REGISTRAR DEVOLUÇÃO ====================

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .models import MovimentacaoEstoque

@login_required
def listar_devolucoes(request):
    """
    Lista todas as devoluções registradas
    Apenas superusers podem visualizar
    """
    if not request.user.is_superuser:
        messages.error(request, 'Apenas administradores podem visualizar devoluções.')
        return redirect('listar_vendas')
    
    # Buscar todas as movimentações do tipo devolução
    devolucoes = MovimentacaoEstoque.objects.filter(
        tipo_movimentacao='devolucao'
    ).select_related('loja', 'produto', 'recarga', 'venda', 'usuario').order_by('-data_movimentacao')
    
    # Aplicar filtros
    loja_id = request.GET.get('loja')
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    tipo_item = request.GET.get('tipo_item')
    
    if loja_id:
        devolucoes = devolucoes.filter(loja_id=loja_id)
    if data_inicio:
        devolucoes = devolucoes.filter(data_movimentacao__date__gte=data_inicio)
    if data_fim:
        devolucoes = devolucoes.filter(data_movimentacao__date__lte=data_fim)
    if tipo_item:
        devolucoes = devolucoes.filter(tipo_item=tipo_item)
    
    # Estatísticas
    total_devolucoes = devolucoes.count()
    total_quantidade = devolucoes.aggregate(total=Sum('quantidade'))['total'] or 0
    total_valor = devolucoes.aggregate(total=Sum('valor_total'))['total'] or 0
    
    # Paginação
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    page = request.GET.get('page', 1)
    paginator = Paginator(devolucoes, 5)
    
    try:
        devolucoes_paginadas = paginator.page(page)
    except PageNotAnInteger:
        devolucoes_paginadas = paginator.page(1)
    except EmptyPage:
        devolucoes_paginadas = paginator.page(paginator.num_pages)
    
    # Lojas para filtro
    if request.user.is_superuser:
        lojas = Loja.objects.all()
    else:
        lojas = Loja.objects.filter(gerentes=request.user)
    
    context = {
        'devolucoes': devolucoes_paginadas,
        'total_devolucoes': total_devolucoes,
        'total_quantidade': total_quantidade,
        'total_valor': total_valor,
        'lojas': lojas,
        'tipos_item': MovimentacaoEstoque.TIPO_ITEM,
    }
    return render(request, 'vendas/listar_devolucoes.html', context)

@require_POST
@csrf_exempt
@login_required
def registrar_devolucao(request):
    """
    Função para registrar devolução de venda
    Reverte a venda e atualiza o estoque
    """
    try:
        with transaction.atomic():
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST.dict()
            
            venda_id = data.get('venda_id')
            quantidade_devolvida = data.get('quantidade', None)
            motivo = data.get('motivo', '')
            observacao = data.get('observacao', '')
            
            # Buscar a venda
            venda = get_object_or_404(Venda, id=venda_id)
            
            # Verificar se a venda pode ser devolvida
            if not venda.pode_devolver:
                return JsonResponse({
                    'success': False,
                    'error': 'Esta venda não pode ser devolvida pois já foi totalmente devolvida.'
                })
            
            # Verificar permissão
            if not request.user.is_superuser:
                loja = venda.loja
                if loja and request.user not in loja.gerentes.all():
                    return JsonResponse({
                        'success': False,
                        'error': 'Você não tem permissão para realizar devoluções nesta loja.'
                    })
            
            # Determinar quantidade a devolver
            if quantidade_devolvida:
                try:
                    quantidade_devolvida = int(quantidade_devolvida)
                    if quantidade_devolvida > venda.quantidade_restante:
                        return JsonResponse({
                            'success': False,
                            'error': f'Quantidade a devolver ({quantidade_devolvida}) excede a quantidade disponível ({venda.quantidade_restante}).'
                        })
                    if quantidade_devolvida <= 0:
                        return JsonResponse({
                            'success': False,
                            'error': 'Quantidade a devolver deve ser maior que zero.'
                        })
                except (ValueError, TypeError):
                    return JsonResponse({
                        'success': False,
                        'error': 'Quantidade inválida.'
                    })
            else:
                quantidade_devolvida = venda.quantidade_restante
            
            # Calcular valor da devolução
            valor_unitario = venda.valor_total / venda.quantidade
            valor_devolucao = quantidade_devolvida * valor_unitario
            
            # Reverter o estoque
            if venda.item_type == 'produto':
                estoque = venda.estoque_loja
                estoque = EstoqueLoja.objects.select_for_update().get(id=estoque.id)
                quantidade_anterior = estoque.quantidade
                estoque.quantidade += quantidade_devolvida
                estoque.save()
                
                # Registrar movimentação de devolução
                MovimentacaoEstoque.objects.create(
                    loja=estoque.loja,
                    tipo_movimentacao='devolucao',
                    tipo_item='produto',
                    produto=estoque.produto,
                    quantidade=quantidade_devolvida,
                    quantidade_anterior=quantidade_anterior,
                    quantidade_nova=estoque.quantidade,
                    valor_unitario=valor_unitario,
                    valor_total=valor_devolucao,
                    observacao=f"Devolução da venda #{venda.id}. {observacao}",
                    motivo=motivo,
                    venda=venda,
                    usuario=request.user
                )
                
            else:  # recarga
                estoque = venda.estoque_recarga
                estoque = EstoqueRecarga.objects.select_for_update().get(id=estoque.id)
                quantidade_anterior = estoque.quantidade
                estoque.quantidade += quantidade_devolvida
                estoque.save()
                
                # Registrar movimentação de devolução
                MovimentacaoEstoque.objects.create(
                    loja=estoque.loja,
                    tipo_movimentacao='devolucao',
                    tipo_item='recarga',
                    recarga=estoque.recarga,
                    quantidade=quantidade_devolvida,
                    quantidade_anterior=quantidade_anterior,
                    quantidade_nova=estoque.quantidade,
                    valor_unitario=valor_unitario,
                    valor_total=valor_devolucao,
                    observacao=f"Devolução da venda #{venda.id}. {observacao}",
                    motivo=motivo,
                    venda=venda,
                    usuario=request.user
                )
            
            # Atualizar a venda
            if quantidade_devolvida == venda.quantidade:
                # Devolução total
                venda.status = 'devolvida'
                venda.observacao = f"{venda.observacao}\n\n[DEVOLUÇÃO TOTAL] Data: {datetime.now().strftime('%d/%m/%Y %H:%M')} - Motivo: {motivo} - Por: {request.user.username}"
            else:
                # Devolução parcial
                venda.status = 'parcial'
                venda.observacao = f"{venda.observacao}\n\n[DEVOLUÇÃO PARCIAL] {quantidade_devolvida} unidades devolvidas em {datetime.now().strftime('%d/%m/%Y %H:%M')} - Motivo: {motivo} - Por: {request.user.username}"
            
            venda.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Devolução de {quantidade_devolvida} unidade(s) registrada com sucesso!',
                'valor_devolucao': float(valor_devolucao),
                'novo_estoque': estoque.quantidade,
                'venda_atualizada': {
                    'status': venda.status,
                    'quantidade_restante': venda.quantidade_restante,
                    'valor_restante': float(venda.valor_total - (venda.quantidade_devolvida * valor_unitario))
                }
            })
            
    except Exception as e:
        print(f"Erro ao registrar devolução: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': f'Erro ao registrar devolução: {str(e)}'
        })

# ==================== FUNÇÃO PARA LISTAR MOVIMENTAÇÕES DE ESTOQUE ====================

@login_required
def listar_movimentacoes_estoque(request):
    """
    Lista todas as movimentações de estoque (entradas, saídas, devoluções)
    """
    if request.user.is_superuser:
        movimentacoes = MovimentacaoEstoque.objects.all()
        lojas = Loja.objects.all()
    else:
        lojas_usuario = Loja.objects.filter(gerentes=request.user)
        movimentacoes = MovimentacaoEstoque.objects.filter(loja__in=lojas_usuario)
        lojas = lojas_usuario
    
    # Filtros
    loja_id = request.GET.get('loja')
    tipo_movimentacao = request.GET.get('tipo')
    tipo_item = request.GET.get('tipo_item')
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    
    if loja_id:
        movimentacoes = movimentacoes.filter(loja_id=loja_id)
    if tipo_movimentacao:
        movimentacoes = movimentacoes.filter(tipo_movimentacao=tipo_movimentacao)
    if tipo_item:
        movimentacoes = movimentacoes.filter(tipo_item=tipo_item)
    if data_inicio:
        movimentacoes = movimentacoes.filter(data_movimentacao__date__gte=data_inicio)
    if data_fim:
        movimentacoes = movimentacoes.filter(data_movimentacao__date__lte=data_fim)
    
    # Paginação
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    paginator = Paginator(movimentacoes, 10)
    page = request.GET.get('page', 1)
    
    try:
        movimentacoes_paginadas = paginator.page(page)
    except PageNotAnInteger:
        movimentacoes_paginadas = paginator.page(1)
    except EmptyPage:
        movimentacoes_paginadas = paginator.page(paginator.num_pages)
    
    # Estatísticas
    total_entradas = movimentacoes.filter(tipo_movimentacao='entrada').aggregate(
        total=Sum('quantidade'))['total'] or 0
    total_saidas = movimentacoes.filter(tipo_movimentacao='saida').aggregate(
        total=Sum('quantidade'))['total'] or 0
    total_devolucoes = movimentacoes.filter(tipo_movimentacao='devolucao').aggregate(
        total=Sum('quantidade'))['total'] or 0
    valor_total_entradas = movimentacoes.filter(tipo_movimentacao='entrada').aggregate(
        total=Sum('valor_total'))['total'] or 0
    
    context = {
        'movimentacoes': movimentacoes_paginadas,
        'lojas': lojas,
        'total_entradas': total_entradas,
        'total_saidas': total_saidas,
        'total_devolucoes': total_devolucoes,
        'valor_total_entradas': valor_total_entradas,
        'tipos_movimentacao': MovimentacaoEstoque.TIPO_MOVIMENTACAO,
    }
    return render(request, 'estoque/listar_movimentacoes.html', context)

# ==================== FUNÇÃO PARA DETALHES DA VENDA COM DEVOLUÇÃO ====================

@login_required
def detalhes_venda_com_devolucao(request, venda_id):
    """
    Detalhes da venda com opção de devolução
    """
    venda = get_object_or_404(Venda, id=venda_id)
    
    # Verificar permissão
    if not request.user.is_superuser:
        loja = venda.loja
        if loja and request.user not in loja.gerentes.all():
            messages.error(request, 'Você não tem permissão para visualizar esta venda.')
            return redirect('listar_vendas')
    
    # Buscar devoluções associadas
    devolucoes = MovimentacaoEstoque.objects.filter(venda=venda, tipo_movimentacao='devolucao')
    
    context = {
        'venda': venda,
        'devolucoes': devolucoes,
        'pode_devolver': venda.pode_devolver,
        'quantidade_restante': venda.quantidade_restante,
    }
    return render(request, 'vendas/detalhes_venda_com_devolucao.html', context)

# ==================== FUNÇÃO PARA REGISTRAR VENDAS RETROATIVAS ====================

@require_POST
@csrf_exempt
@login_required
def registrar_venda_retroativa(request):
    """
    Função para registrar vendas de dias anteriores (vendas retroativas)
    Permite definir uma data específica para a venda
    """
    try:
        print("=== REGISTRAR VENDA RETROATIVA CHAMADA ===")
        
        # Verificar se é JSON ou FormData
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST.dict()
        
        # Extrair dados
        estoque_id = data.get('estoque_id')
        item_type = data.get('item_type', 'produto').lower().strip()
        quantidade = data.get('quantidade')
        data_venda = data.get('data_venda')
        observacao = data.get('observacao', '')
        justificativa = data.get('justificativa', '')
        
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
        
        if not data_venda:
            return JsonResponse({
                'success': False,
                'error': 'Data da venda não fornecida.'
            })
        
        # Validar quantidade
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
        
        # Validar data da venda
        try:
            data_venda_obj = datetime.strptime(data_venda, '%Y-%m-%d').date()
            
            # Verificar se a data não é futura
            if data_venda_obj > datetime.now().date():
                return JsonResponse({
                    'success': False,
                    'error': 'Não é possível registrar vendas com data futura.'
                })
            
            # Verificar se a data não é muito antiga (ex: mais de 1 ano)
            data_limite = datetime.now().date() - timedelta(days=365)
            if data_venda_obj < data_limite:
                return JsonResponse({
                    'success': False,
                    'error': 'Data muito antiga. Vendas retroativas só podem ser registradas até 1 ano atrás.'
                })
                
        except ValueError:
            return JsonResponse({
                'success': False,
                'error': 'Formato de data inválido. Use YYYY-MM-DD.'
            })
        
        with transaction.atomic():
            # Buscar o estoque
            if item_type == 'produto':
                try:
                    estoque = EstoqueLoja.objects.select_for_update().get(id=estoque_id)
                    preco_unitario = estoque.produto.preco
                    item_nome = estoque.produto.nome
                except EstoqueLoja.DoesNotExist:
                    return JsonResponse({
                        'success': False,
                        'error': 'Estoque de produto não encontrado.'
                    })
                    
            elif item_type == 'recarga':
                try:
                    estoque = EstoqueRecarga.objects.select_for_update().get(id=estoque_id)
                    preco_unitario = estoque.recarga.preco
                    item_nome = estoque.recarga.nome
                except EstoqueRecarga.DoesNotExist:
                    return JsonResponse({
                        'success': False,
                        'error': 'Estoque de recarga não encontrado.'
                    })
            else:
                return JsonResponse({
                    'success': False,
                    'error': f'Tipo de item inválido: "{item_type}".'
                })
            
            # Verificar permissão (apenas superuser pode registrar vendas retroativas)
            if not request.user.is_superuser:
                return JsonResponse({
                    'success': False,
                    'error': 'Apenas administradores podem registrar vendas de dias anteriores.'
                })
            
            # Verificar estoque
            if estoque.quantidade < quantidade:
                return JsonResponse({
                    'success': False,
                    'error': f'Estoque insuficiente. Disponível: {estoque.quantidade}'
                })
            
            # Calcular valor total
            valor_total = quantidade * preco_unitario
            
            # Registrar quantidade anterior
            quantidade_anterior = estoque.quantidade
            
            # Atualizar estoque
            estoque.quantidade -= quantidade
            estoque.save()
            
            # Construir observação com justificativa
            observacao_completa = observacao
            if justificativa:
                if observacao_completa:
                    observacao_completa += f"\nJustificativa da venda retroativa: {justificativa}"
                else:
                    observacao_completa = f"Venda retroativa do dia {data_venda}. Justificativa: {justificativa}"
            else:
                if observacao_completa:
                    observacao_completa += f"\nVenda retroativa registrada em {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                else:
                    observacao_completa = f"Venda retroativa do dia {data_venda} registrada em {datetime.now().strftime('%d/%m/%Y %H:%M')}"
            
            # Registrar a venda com data específica
            if item_type == 'produto':
                venda = Venda.objects.create(
                    estoque_loja=estoque,
                    item_type='produto',
                    quantidade=quantidade,
                    valor_total=valor_total,
                    vendedor=request.user,
                    observacao=observacao_completa,
                    data_venda=data_venda_obj,
                    status='normal'
                )
            else:
                venda = Venda.objects.create(
                    estoque_recarga=estoque,
                    item_type='recarga',
                    quantidade=quantidade,
                    valor_total=valor_total,
                    vendedor=request.user,
                    observacao=observacao_completa,
                    data_venda=data_venda_obj,
                    status='normal'
                )
            
            # Registrar movimentação de saída
            MovimentacaoEstoque.objects.create(
                loja=estoque.loja,
                tipo_movimentacao='saida',
                tipo_item=item_type,
                produto=estoque.produto if item_type == 'produto' else None,
                recarga=estoque.recarga if item_type == 'recarga' else None,
                quantidade=quantidade,
                quantidade_anterior=quantidade_anterior,
                quantidade_nova=estoque.quantidade,
                valor_unitario=preco_unitario,
                valor_total=valor_total,
                observacao=f"Venda retroativa #{venda.id} - {observacao_completa}",
                venda=venda,
                usuario=request.user
            )
        
        return JsonResponse({
            'success': True,
            'venda_id': venda.id,
            'novo_estoque': estoque.quantidade,
            'valor_total': float(valor_total),
            'item_nome': item_nome,
            'data_venda': data_venda,
            'message': f'Venda retroativa do dia {data_venda} registrada com sucesso!'
        })
        
    except Exception as e:
        print(f"Erro em registrar_venda_retroativa: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        })

# ==================== FUNÇÃO PARA EDITAR DATA DE VENDA ====================

@require_POST
@csrf_exempt
@login_required
def editar_data_venda(request, venda_id):
    """
    Função para editar a data de uma venda existente
    Apenas superusers podem editar
    """
    if not request.user.is_superuser:
        return JsonResponse({
            'success': False,
            'error': 'Apenas administradores podem editar datas de vendas.'
        })
    
    try:
        venda = get_object_or_404(Venda, id=venda_id)
        
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            nova_data = data.get('data_venda')
            justificativa = data.get('justificativa', '')
        else:
            nova_data = request.POST.get('data_venda')
            justificativa = request.POST.get('justificativa', '')
        
        if not nova_data:
            return JsonResponse({
                'success': False,
                'error': 'Nova data não fornecida.'
            })
        
        try:
            nova_data_obj = datetime.strptime(nova_data, '%Y-%m-%d').date()
            if nova_data_obj > datetime.now().date():
                return JsonResponse({
                    'success': False,
                    'error': 'Não é possível definir data futura para a venda.'
                })
        except ValueError:
            return JsonResponse({
                'success': False,
                'error': 'Formato de data inválido. Use YYYY-MM-DD.'
            })
        
        data_antiga = venda.data_venda.strftime('%d/%m/%Y')
        venda.data_venda = nova_data_obj
        
        timestamp = datetime.now().strftime('%d/%m/%Y %H:%M')
        if justificativa:
            nova_observacao = f"{venda.observacao}\n\n[ALTERAÇÃO] Data alterada de {data_antiga} para {nova_data}. Justificativa: {justificativa} (por {request.user.username} em {timestamp})"
        else:
            nova_observacao = f"{venda.observacao}\n\n[ALTERAÇÃO] Data alterada de {data_antiga} para {nova_data} por {request.user.username} em {timestamp}"
        
        venda.observacao = nova_observacao[:500]
        venda.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Data da venda alterada de {data_antiga} para {nova_data}',
            'nova_data': nova_data,
            'data_antiga': data_antiga
        })
        
    except Exception as e:
        print(f"Erro ao editar data: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Erro ao alterar data: {str(e)}'
        })

# ==================== FUNÇÃO PARA LISTAR VENDAS RETROATIVAS ====================

@require_GET
@login_required
def listar_vendas_retroativas(request):
    """
    Lista apenas vendas retroativas (que não são do dia atual)
    """
    if not request.user.is_superuser:
        messages.error(request, 'Apenas administradores podem visualizar vendas retroativas.')
        return redirect('listar_vendas')
    
    hoje = datetime.now().date()
    vendas_retroativas = Venda.objects.filter(data_venda__date__lt=hoje).order_by('-data_venda')
    
    # Filtros
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    loja_id = request.GET.get('loja')
    tipo = request.GET.get('tipo')
    
    if data_inicio:
        vendas_retroativas = vendas_retroativas.filter(data_venda__date__gte=data_inicio)
    if data_fim:
        vendas_retroativas = vendas_retroativas.filter(data_venda__date__lte=data_fim)
    if loja_id:
        vendas_retroativas = vendas_retroativas.filter(
            Q(estoque_loja__loja_id=loja_id) | Q(estoque_recarga__loja_id=loja_id)
        )
    if tipo and tipo != 'todos':
        vendas_retroativas = vendas_retroativas.filter(item_type=tipo)
    
    # Estatísticas
    total_vendas = vendas_retroativas.count()
    valor_total = vendas_retroativas.aggregate(total=Sum('valor_total'))['total'] or 0
    quantidade_total = vendas_retroativas.aggregate(total=Sum('quantidade'))['total'] or 0
    
    # Paginação
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    page = request.GET.get('page', 1)
    paginator = Paginator(vendas_retroativas, 20)
    
    try:
        vendas_paginadas = paginator.page(page)
    except PageNotAnInteger:
        vendas_paginadas = paginator.page(1)
    except EmptyPage:
        vendas_paginadas = paginator.page(paginator.num_pages)
    
    lojas = Loja.objects.all() if request.user.is_superuser else Loja.objects.filter(gerentes=request.user)
    
    context = {
        'vendas': vendas_paginadas,
        'total_vendas': total_vendas,
        'valor_total': valor_total,
        'quantidade_total': quantidade_total,
        'lojas': lojas,
        'filtros': {
            'data_inicio': data_inicio,
            'data_fim': data_fim,
            'loja_id': loja_id,
            'tipo': tipo,
        }
    }
    return render(request, 'vendas/listar_vendas_retroativas.html', context)

# ==================== FUNÇÕES EXISTENTES (mantidas) ====================

@require_GET
@csrf_exempt
def api_totais_vendas(request):
    """API simplificada para retornar os totais de vendas"""
    try:
        loja_id = request.GET.get('loja_id')
        data_relatorio = request.GET.get('data_relatorio')
        
        if not loja_id:
            return JsonResponse({
                'status': 'error',
                'message': 'Parâmetro loja_id é obrigatório'
            }, status=400)
        
        try:
            loja = Loja.objects.get(id=loja_id)
        except Loja.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': f'Loja com ID {loja_id} não encontrada'
            }, status=404)
        
        vendas_query = Venda.objects.filter(
            Q(estoque_loja__loja=loja) | Q(estoque_recarga__loja=loja)
        ).exclude(status='devolvida')
        
        if data_relatorio:
            try:
                data_obj = datetime.strptime(data_relatorio, '%Y-%m-%d').date()
                vendas_query = vendas_query.filter(data_venda__date=data_obj)
            except ValueError:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Formato de data inválido. Use YYYY-MM-DD'
                }, status=400)
        
        total_quantidade = vendas_query.aggregate(total=Sum('quantidade'))['total'] or 0
        total_valor = vendas_query.aggregate(total=Sum('valor_total'))['total'] or 0
        total_vendas = vendas_query.count()
        
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

@login_required
def detalhes_loja(request, loja_id):
    loja = get_object_or_404(Loja, id=loja_id)
    
    if not request.user.is_superuser and request.user not in loja.gerentes.all():
        messages.error(request, 'Você não tem permissão para acessar esta loja.')
        return redirect('listar_lojas')
    
    estoque_loja = EstoqueLoja.objects.filter(loja=loja)
    total_produtos = estoque_loja.count()
    total_estoque = estoque_loja.aggregate(total=Sum('quantidade'))['total'] or 0
    
    vendas_recentes = Venda.objects.filter(
        Q(estoque_loja__loja=loja) | Q(estoque_recarga__loja=loja)
    ).order_by('-data_venda')[:10]
    
    ranking_produtos = loja.get_ranking_produtos()
    
    context = {
        'loja': loja,
        'total_produtos': total_produtos,
        'total_estoque': total_estoque,
        'vendas_recentes': vendas_recentes,
        'ranking_produtos': ranking_produtos,
    }
    return render(request, 'lojas/detalhes_loja.html', context)

@login_required
def listar_estoque(request):
    tipo_selecionado = request.GET.get('tipo', 'todos')
    
    if request.user.is_superuser:
        produtos_estoque = EstoqueLoja.objects.all()
        recargas_estoque = EstoqueRecarga.objects.all() if hasattr(EstoqueRecarga, 'objects') else []
        lojas = Loja.objects.all()
    else:
        lojas_usuario = Loja.objects.filter(gerentes=request.user)
        produtos_estoque = EstoqueLoja.objects.filter(loja__in=lojas_usuario)
        recargas_estoque = EstoqueRecarga.objects.filter(loja__in=lojas_usuario) if hasattr(EstoqueRecarga, 'objects') else []
        lojas = lojas_usuario
    
    loja_id = request.GET.get('loja')
    if loja_id:
        produtos_estoque = produtos_estoque.filter(loja_id=loja_id)
        if recargas_estoque:
            recargas_estoque = recargas_estoque.filter(loja_id=loja_id)
    
    produto_nome = request.GET.get('produto')
    if produto_nome:
        produtos_estoque = produtos_estoque.filter(produto__nome__icontains=produto_nome)
        if recargas_estoque:
            recargas_estoque = recargas_estoque.filter(recarga__nome__icontains=produto_nome)
    
    context = {
        'produtos_estoque': produtos_estoque,
        'recargas_estoque': recargas_estoque,
        'lojas': lojas,
        'tipo_selecionado': tipo_selecionado,
    }
    return render(request, 'estoque/listar_estoque.html', context)

@login_required
def adicionar_estoque(request):
    if request.method == 'POST':
        try:
            tipo_item = request.POST.get('tipo_item', 'produto')
            loja_id = request.POST.get('loja')
            quantidade = request.POST.get('quantidade')
            
            loja = get_object_or_404(Loja, id=loja_id)
            
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
                    defaults={'quantidade': 0}
                )
                
                quantidade_anterior = estoque.quantidade
                estoque.quantidade += int(quantidade)
                estoque.save()
                
                # Registrar movimentação
                MovimentacaoEstoque.objects.create(
                    loja=loja,
                    tipo_movimentacao='entrada',
                    tipo_item='produto',
                    produto=produto,
                    quantidade=int(quantidade),
                    quantidade_anterior=quantidade_anterior,
                    quantidade_nova=estoque.quantidade,
                    valor_unitario=produto.preco,
                    valor_total=int(quantidade) * produto.preco,
                    observacao=f"Adicionado via formulário de estoque",
                    usuario=request.user
                )
                
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
                    defaults={'quantidade': 0}
                )
                
                quantidade_anterior = estoque.quantidade
                estoque.quantidade += int(quantidade)
                estoque.save()
                
                # Registrar movimentação
                MovimentacaoEstoque.objects.create(
                    loja=loja,
                    tipo_movimentacao='entrada',
                    tipo_item='recarga',
                    recarga=recarga,
                    quantidade=int(quantidade),
                    quantidade_anterior=quantidade_anterior,
                    quantidade_nova=estoque.quantidade,
                    valor_unitario=recarga.preco,
                    valor_total=int(quantidade) * recarga.preco,
                    observacao=f"Adicionado via formulário de estoque",
                    usuario=request.user
                )
                
                messages.success(request, f'Estoque da recarga {recarga.nome} atualizado com sucesso!')
            
            return redirect('listar_estoque')
            
        except Exception as e:
            messages.error(request, f'Erro ao adicionar estoque: {str(e)}')
    
    lojas = Loja.objects.all() if request.user.is_superuser else Loja.objects.filter(gerentes=request.user)
    
    context = {
        'lojas': lojas,
        'produtos': Produto.objects.all(),
        'recargas': Recarga.objects.all()
    }
    return render(request, 'estoque/adicionar_estoque.html', context)

@login_required
def editar_estoque(request, estoque_id):
    try:
        estoque = get_object_or_404(EstoqueLoja, id=estoque_id)
        tipo = 'produto'
    except:
        try:
            estoque = get_object_or_404(EstoqueRecarga, id=estoque_id)
            tipo = 'recarga'
        except:
            messages.error(request, 'Estoque não encontrado.')
            return redirect('listar_estoque')
    
    if not request.user.is_superuser and request.user not in estoque.loja.gerentes.all():
        messages.error(request, 'Você não tem permissão para editar este estoque.')
        return redirect('listar_estoque')
    
    if request.method == 'POST':
        try:
            nova_quantidade = int(request.POST.get('quantidade'))
            observacao = request.POST.get('observacao', '')
            
            quantidade_antiga = estoque.quantidade
            
            if nova_quantidade > quantidade_antiga:
                tipo_mov = 'entrada'
                quantidade_mov = nova_quantidade - quantidade_antiga
                valor_unitario = estoque.produto.preco if tipo == 'produto' else estoque.recarga.preco
                valor_total = quantidade_mov * valor_unitario
            elif nova_quantidade < quantidade_antiga:
                tipo_mov = 'saida'
                quantidade_mov = quantidade_antiga - nova_quantidade
                valor_unitario = estoque.produto.preco if tipo == 'produto' else estoque.recarga.preco
                valor_total = quantidade_mov * valor_unitario
            else:
                messages.info(request, 'A quantidade não foi alterada.')
                return redirect('listar_estoque')
            
            estoque.quantidade = nova_quantidade
            estoque.save()
            
            # Registrar movimentação
            MovimentacaoEstoque.objects.create(
                loja=estoque.loja,
                tipo_movimentacao=tipo_mov,
                tipo_item=tipo,
                produto=estoque.produto if tipo == 'produto' else None,
                recarga=estoque.recarga if tipo == 'recarga' else None,
                quantidade=quantidade_mov,
                quantidade_anterior=quantidade_antiga,
                quantidade_nova=nova_quantidade,
                valor_unitario=valor_unitario,
                valor_total=valor_total,
                observacao=f"Edição manual: {observacao}",
                usuario=request.user
            )
            
            messages.success(request, 'Estoque atualizado com sucesso!')
            return redirect('listar_estoque')
            
        except Exception as e:
            messages.error(request, f'Erro ao atualizar estoque: {str(e)}')
    
    context = {'estoque': estoque}
    return render(request, 'estoque/editar_estoque.html', context)

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

@login_required
def listar_vendas(request):
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
    
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    loja_id = request.GET.get('loja')
    
    if data_inicio:
        vendas = vendas.filter(data_venda__date__gte=data_inicio)
    if data_fim:
        vendas = vendas.filter(data_venda__date__lte=data_fim)
    if loja_id:
        vendas = vendas.filter(
            Q(estoque_loja__loja_id=loja_id) | Q(estoque_recarga__loja_id=loja_id)
        )
    
    total_vendas = vendas.count()
    valor_total = vendas.aggregate(total=Sum('valor_total'))['total'] or 0
    quantidade_total = vendas.aggregate(total=Sum('quantidade'))['total'] or 0
    ticket_medio = valor_total / total_vendas if total_vendas > 0 else 0
    
    page = request.GET.get('page', 1)
    paginator = Paginator(vendas, 5)
    
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
        'hoje': datetime.now().date().isoformat(),
    }
    return render(request, 'vendas/listar_vendas.html', context)

@login_required
def detalhes_venda(request, venda_id):
    venda = get_object_or_404(Venda, id=venda_id)
    
    if not request.user.is_superuser:
        loja = venda.loja
        if loja and request.user not in loja.gerentes.all():
            messages.error(request, 'Você não tem permissão para visualizar esta venda.')
            return redirect('listar_vendas')
    
    context = {
        'venda': venda,
    }
    return render(request, 'vendas/detalhes_venda.html', context)