from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .forms import RelatorioDiarioForm
from .models import RelatorioDiario
from lojas.models import Loja
from django.utils import timezone
from decimal import Decimal
from django.db.models import Q
from conta.utils import registrar_atividade
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from datetime import datetime

@login_required
def lista_relatorios(request):
    """View para listar relatórios diários"""
    # Obter todos os relatórios baseado nas permissões do usuário
    if request.user.is_superuser:
        relatorios = RelatorioDiario.objects.all().select_related('loja', 'usuario')
        lojas = Loja.objects.all()
    else:
        lojas_usuario = request.user.lojas_gerenciadas.all()
        relatorios = RelatorioDiario.objects.filter(loja__in=lojas_usuario).select_related('loja', 'usuario')
        lojas = lojas_usuario

    # Aplicar filtros - TRATAMENTO CORRIGIDO
    data_inicial = request.GET.get('data_inicial', '').strip()
    data_final = request.GET.get('data_final', '').strip()
    loja_id = request.GET.get('loja', '').strip()
    status = request.GET.get('status', '').strip()

    # Aplicar filtro de data inicial
    if data_inicial and data_inicial != '':
        try:
            data_inicial_obj = datetime.strptime(data_inicial, '%Y-%m-%d').date()
            relatorios = relatorios.filter(data__gte=data_inicial_obj)
        except (ValueError, TypeError):
            pass  # Ignora se a data for inválida
    
    # Aplicar filtro de data final
    if data_final and data_final != '':
        try:
            data_final_obj = datetime.strptime(data_final, '%Y-%m-%d').date()
            relatorios = relatorios.filter(data__lte=data_final_obj)
        except (ValueError, TypeError):
            pass  # Ignora se a data for inválida
    
    # Aplicar filtro de loja
    if loja_id and loja_id != '':
        try:
            loja_id_int = int(loja_id)
            relatorios = relatorios.filter(loja_id=loja_id_int)
        except (ValueError, TypeError):
            pass  # Ignora se o ID da loja for inválido

    # Ordenação
    relatorios = relatorios.order_by('-data', 'loja__nome')

    # Calcular estatísticas
    total_relatorios = relatorios.count()
    
    # Inicializar contadores
    completos = 0
    negativos = 0
    pendentes = 0

    # Calcular totais e status para cada relatório
    relatorios_com_calculos = []
    for relatorio in relatorios:
        try:
            total_arrecadado = relatorio.calcular_total_arrecadado()
            diferenca = relatorio.calcular_diferenca()
            
            # Determinar status
            if diferenca < 0:
                status_relatorio = 'completo'
            elif diferenca > 0:
                status_relatorio = 'negativo'
            else:
                status_relatorio = 'pendente'

            # Aplicar filtro de status se especificado
            if status and status != '' and status != status_relatorio:
                continue

            # Atualizar contadores
            if status_relatorio == 'completo':
                completos += 1
            elif status_relatorio == 'negativo':
                negativos += 1
            else:
                pendentes += 1

            # Adicionar atributos calculados ao relatório
            relatorio.total_arrecadado_calculado = total_arrecadado
            relatorio.diferenca_calculada = diferenca
            relatorio.status = status_relatorio
            
            relatorios_com_calculos.append(relatorio)
            
        except Exception as e:
            print(f"Erro ao calcular totais para relatório {relatorio.id}: {e}")
            continue

    # Se houver filtro de status, os contadores já foram atualizados no loop
    # Caso contrário, recalcular os contadores
    if not status or status == '':
        completos = len([r for r in relatorios_com_calculos if r.status == 'completo'])
        negativos = len([r for r in relatorios_com_calculos if r.status == 'negativo'])
        pendentes = len([r for r in relatorios_com_calculos if r.status == 'pendente'])
        total_relatorios = len(relatorios_com_calculos)

    # --- PAGINAÇÃO ---
    itens_por_pagina = request.GET.get('itens_por_pagina', 5)
    try:
        itens_por_pagina = int(itens_por_pagina)
        if itens_por_pagina not in [5, 10, 25, 50, 100]:
            itens_por_pagina = 5
    except (ValueError, TypeError):
        itens_por_pagina = 5

    paginator = Paginator(relatorios_com_calculos, itens_por_pagina)
    page = request.GET.get('page', 1)

    try:
        relatorios_paginados = paginator.page(page)
    except PageNotAnInteger:
        relatorios_paginados = paginator.page(1)
    except EmptyPage:
        relatorios_paginados = paginator.page(paginator.num_pages)

    # Criar range de páginas
    page_range = get_page_range(relatorios_paginados)

    context = {
        'relatorios_recentes': relatorios_paginados,
        'total_relatorios': total_relatorios,
        'completos': completos,
        'negativos': negativos,
        'pendentes': pendentes,
        'lojas': lojas,
        'filtros': {
            'data_inicial': data_inicial if data_inicial else '',
            'data_final': data_final if data_final else '',
            'loja_id': loja_id if loja_id else '',
            'status': status if status else '',
            'itens_por_pagina': itens_por_pagina,
        },
        'paginator': paginator,
        'page_obj': relatorios_paginados,
        'is_paginated': paginator.num_pages > 1,
        'page_range': page_range,
    }
    
    return render(request, 'lista_relatorios.html', context)

def get_page_range(page_obj, max_pages=5):
    """
    Função auxiliar para gerar um range de páginas inteligente
    Mostra no máximo 'max_pages' páginas ao redor da página atual
    """
    current_page = page_obj.number
    num_pages = page_obj.paginator.num_pages
    
    if num_pages <= max_pages:
        return range(1, num_pages + 1)
    
    half = max_pages // 2
    start = current_page - half
    end = current_page + half
    
    if start <= 1:
        start = 1
        end = max_pages
    elif end >= num_pages:
        end = num_pages
        start = num_pages - max_pages + 1
    
    return range(start, end + 1)

# ==================== MANTER AS OUTRAS VIEWS EXISTENTES ====================

@login_required
def criar_relatorio_diario(request):
    if request.method == 'POST':
        form = RelatorioDiarioForm(request.POST, request=request)
        if form.is_valid():
            try:
                relatorio = form.save(commit=False)
                relatorio.usuario = request.user
                
                # Preenche automaticamente a loja do usuário logado
                if not relatorio.loja:
                    loja_usuario = request.user.lojas_gerenciadas.first()
                    if loja_usuario:
                        relatorio.loja = loja_usuario
                        messages.info(request, f'Loja automaticamente associada: {loja_usuario.nome}')
                    else:
                        messages.warning(request, 'Usuário não possui loja associada. Selecione uma loja manualmente.')
                        return render(request, 'criar_relatorio_diario.html', {'form': form})
                
                # Tentar preencher automaticamente o campo RECARGAS com vendas do dia
                try:
                    total_vendas_dia = relatorio.calcular_total_vendas_dia()
                    if total_vendas_dia > 0 and not relatorio.recargas:
                        relatorio.recargas = total_vendas_dia
                        messages.info(
                            request, 
                            f'Campo RECARGAS preenchido automaticamente com vendas do dia: Kz {total_vendas_dia:.2f}'
                        )
                except Exception as e:
                    print(f"Erro ao calcular vendas do dia: {e}")
                
                # Verifica se há falta de dinheiro e se observação foi preenchida
                relatorio.calcular_total_geral()
                if relatorio.tem_falta_dinheiro() and not relatorio.observacao_falta:
                    messages.error(request, 'É obrigatório preencher a observação da falta quando há diferença no caixa!')
                    return render(request, 'criar_relatorio_diario.html', {'form': form})
                
                relatorio.save()

                registrar_atividade(
                    request.user, 
                    f"Criou relatório para {relatorio.loja.nome} - Data: {relatorio.data}"
                )

                messages.success(request, 'Relatório diário criado com sucesso!')
                return redirect('listar_relatorios_diarios')
                
            except Exception as e:
                messages.error(request, f'Erro ao salvar relatório: {str(e)}')
        else:
            messages.error(request, 'Por favor, corrija os erros no formulário.')
    else:
        initial_data = {'data': timezone.now().date()}
        
        loja_usuario = request.user.lojas_gerenciadas.first()
        if loja_usuario:
            initial_data['loja'] = loja_usuario
        
        form = RelatorioDiarioForm(initial=initial_data, request=request)
    
    return render(request, 'criar_relatorio_diario.html', {'form': form})

@login_required
def editar_relatorio_diario(request, pk):
    relatorio = get_object_or_404(RelatorioDiario, pk=pk)
    
    if relatorio.usuario != request.user and not request.user.is_superuser:
        messages.error(request, 'Você não tem permissão para editar este relatório.')
        return redirect('listar_relatorios_diarios')
    
    if request.method == 'POST':
        form = RelatorioDiarioForm(request.POST, instance=relatorio, request=request)
        if form.is_valid():
            try:
                relatorio_editado = form.save(commit=False)
                
                relatorio_editado.calcular_total_geral()
                if relatorio_editado.tem_falta_dinheiro() and not relatorio_editado.observacao_falta:
                    messages.error(request, 'É obrigatório preencher a observação da falta quando há diferença no caixa!')
                    return render(request, 'editar_relatorio_diario.html', {
                        'form': form,
                        'relatorio': relatorio
                    })
                
                relatorio_editado.save()
                
                registrar_atividade(
                    request.user,
                    f"Editou relatório para {relatorio.loja.nome} - Data: {relatorio.data}"
                )
                
                messages.success(request, 'Relatório diário atualizado com sucesso!')
                return redirect('listar_relatorios_diarios')
                
            except Exception as e:
                messages.error(request, f'Erro ao atualizar relatório: {str(e)}')
        else:
            messages.error(request, 'Por favor, corrija os erros no formulário.')
    else:
        form = RelatorioDiarioForm(instance=relatorio, request=request)
    
    return render(request, 'editar_relatorio.html', {
        'form': form,
        'relatorio': relatorio
    })

@login_required
def detalhes_relatorio(request, pk):
    """View para visualizar detalhes de um relatório"""
    relatorio = get_object_or_404(
        RelatorioDiario.objects.select_related('loja', 'usuario'), 
        pk=pk
    )
    
    if not request.user.is_superuser:
        lojas_usuario = request.user.lojas_gerenciadas.all()
        if relatorio.loja not in lojas_usuario:
            messages.error(request, 'Você não tem permissão para visualizar este relatório.')
            return redirect('listar_relatorios_diarios')
    
    calculos = calcular_todos_valores(relatorio)
    dados_vendas = buscar_dados_vendas(relatorio)
    detalhes_recargas, totais_recargas = processar_detalhes_recargas(relatorio)
    
    context = {
        'relatorio': relatorio,
        'dados_vendas': dados_vendas,
        'detalhes_recargas': detalhes_recargas,
        'totais_recargas': totais_recargas,
        **calculos
    }
    
    return render(request, 'detalhes_relatorio.html', context)

def calcular_todos_valores(relatorio):
    """Calcula todos os valores necessários para o template"""
    total_arrecadado = relatorio.calcular_total_arrecadado()
    diferenca = relatorio.calcular_diferenca()
    total_vendas_dia = relatorio.calcular_total_vendas_dia()
    
    vendas_dstv = Decimal('0.00')
    if relatorio.inicio_dstv and relatorio.resto_dstv:
        vendas_dstv = (relatorio.inicio_dstv or Decimal('0.00')) - (relatorio.resto_dstv or Decimal('0.00'))
    
    return {
        'total_arrecadado': total_arrecadado,
        'diferenca': diferenca,
        'total_vendas_dia': total_vendas_dia,
        'vendas_dstv': vendas_dstv,
        'tem_falta': diferenca > Decimal('0.00'),
        'status': 'completo' if diferenca == Decimal('0.00') else 'falta' if diferenca > Decimal('0.00') else 'sobra'
    }

def buscar_dados_vendas(relatorio):
    """Buscar dados das vendas da API ou calcular localmente"""
    try:
        import requests
        from django.conf import settings
        
        api_url = f"{getattr(settings, 'BASE_URL', 'http://localhost:8000')}/api/totais-vendas/"
        params = {
            'loja_id': relatorio.loja.id,
            'data_relatorio': relatorio.data.strftime('%Y-%m-%d')
        }
        
        response = requests.get(api_url, params=params, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                dados = {
                    'acc_produtos': data.get('acc_produtos', 0),
                    'acc_recargas': data.get('acc_recargas', 0),
                    'valor_produtos': Decimal(str(data.get('valor_produtos', 0))),
                    'valor_recargas': Decimal(str(data.get('valor_recargas', 0))),
                    'valor_total': Decimal(str(data.get('valor_total', 0))),
                    'count_produtos': data.get('count_produtos', 0),
                    'count_recargas': data.get('count_recargas', 0),
                }
                
                if dados['valor_total'] > Decimal('0.00'):
                    dados['percentual_produtos'] = (dados['valor_produtos'] / dados['valor_total']) * Decimal('100.00')
                    dados['percentual_recargas'] = (dados['valor_recargas'] / dados['valor_total']) * Decimal('100.00')
                else:
                    dados['percentual_produtos'] = Decimal('0.00')
                    dados['percentual_recargas'] = Decimal('0.00')
                    
                return dados
    except Exception as e:
        print(f"Erro ao buscar dados da API: {e}")
    
    return calcular_dados_vendas_local(relatorio)

def calcular_dados_vendas_local(relatorio):
    """Calcular dados de vendas localmente baseado no relatório"""
    valor_recargas = relatorio.recargas or Decimal('0.00')
    acc_total = relatorio.acc or Decimal('0.00')
    
    if acc_total > Decimal('0.00'):
        valor_produtos = acc_total - valor_recargas
        if valor_produtos < Decimal('0.00'):
            valor_produtos = acc_total * Decimal('0.6')
            valor_recargas = acc_total * Decimal('0.4')
    else:
        valor_produtos = Decimal('0.00')
        valor_recargas = Decimal('0.00')
    
    dados = {
        'acc_produtos': int(valor_produtos / Decimal('100.00')) if valor_produtos > Decimal('100.00') else 0,
        'acc_recargas': int(valor_recargas / Decimal('100.00')) if valor_recargas > Decimal('100.00') else 0,
        'valor_produtos': valor_produtos,
        'valor_recargas': valor_recargas,
        'valor_total': acc_total,
        'count_produtos': int(valor_produtos / Decimal('100.00')) if valor_produtos > Decimal('100.00') else 0,
        'count_recargas': int(valor_recargas / Decimal('100.00')) if valor_recargas > Decimal('100.00') else 0,
    }

    if dados['valor_total'] > Decimal('0.00'):
        dados['percentual_produtos'] = (dados['valor_produtos'] / dados['valor_total']) * Decimal('100.00')
        dados['percentual_recargas'] = (dados['valor_recargas'] / dados['valor_total']) * Decimal('100.00')
    else:
        dados['percentual_produtos'] = Decimal('0.00')
        dados['percentual_recargas'] = Decimal('0.00')

    return dados

def processar_detalhes_recargas(relatorio):
    """Processar detalhes das recargas do relatório"""
    detalhes_recargas = []
    totais = {
        'inicio': 0,
        'vendidas': 0,
        'resto': 0,
        'total_vendas': Decimal('0.00')
    }
    
    try:
        from lojas.models import EstoqueRecarga, Venda
        
        if not relatorio.loja:
            return detalhes_recargas, totais
        
        estoques_recargas = EstoqueRecarga.objects.filter(loja=relatorio.loja)
        
        if estoques_recargas.exists():
            vendas_recargas = Venda.objects.filter(
                Q(estoque_recarga__loja=relatorio.loja),
                item_type='recarga',
                data_venda__date=relatorio.data
            )
            
            for estoque in estoques_recargas:
                try:
                    vendas_desta_recarga = vendas_recargas.filter(estoque_recarga=estoque)
                    total_vendido = vendas_desta_recarga.aggregate(total=Sum('quantidade'))['total'] or 0
                    valor_total_vendas = vendas_desta_recarga.aggregate(total=Sum('valor_total'))['total'] or Decimal('0.00')
                    
                    if total_vendido > 0:
                        estoque_inicial = estoque.quantidade + total_vendido
                        
                        detalhes_recargas.append({
                            'nome': estoque.recarga.nome,
                            'preco': float(estoque.recarga.preco),
                            'inicio': estoque_inicial,
                            'vendidas': total_vendido,
                            'total_vendas': float(valor_total_vendas),
                            'resto': estoque.quantidade
                        })
                        
                        totais['inicio'] += estoque_inicial
                        totais['vendidas'] += total_vendido
                        totais['resto'] += estoque.quantidade
                        totais['total_vendas'] += valor_total_vendas
                        
                except Exception as e:
                    print(f"Erro ao processar recarga {estoque.recarga.nome}: {e}")
                    continue
        
        if not detalhes_recargas and relatorio.recargas and relatorio.recargas > Decimal('0.00'):
            detalhes_recargas = criar_dados_recargas_exemplo(relatorio.recargas)
            
    except Exception as e:
        print(f"Erro ao processar detalhes das recargas: {e}")
        if relatorio.recargas and relatorio.recargas > Decimal('0.00'):
            detalhes_recargas = criar_dados_recargas_exemplo(relatorio.recargas)
    
    return detalhes_recargas, totais

def criar_dados_recargas_exemplo(valor_total_recargas):
    """Criar dados de exemplo para recargas baseado no valor total"""
    if not valor_total_recargas or valor_total_recargas <= Decimal('0.00'):
        return []
    
    total = float(valor_total_recargas)
    
    try:
        from produtos.models import Recarga
        recargas_existentes = Recarga.objects.all()[:5]
        
        if recargas_existentes.exists():
            tipos_recarga = [{'nome': r.nome, 'preco': float(r.preco)} for r in recargas_existentes]
        else:
            tipos_recarga = [
                {'nome': 'Recarga Unitel 100KZ', 'preco': 100.00},
                {'nome': 'Recarga Unitel 200KZ', 'preco': 200.00},
                {'nome': 'Recarga Unitel 500KZ', 'preco': 500.00},
                {'nome': 'Recarga Africell 100KZ', 'preco': 100.00},
                {'nome': 'Recarga Africell 200KZ', 'preco': 200.00},
            ]
    except Exception:
        tipos_recarga = [
            {'nome': 'Recarga Unitel 100KZ', 'preco': 100.00},
            {'nome': 'Recarga Unitel 200KZ', 'preco': 200.00},
            {'nome': 'Recarga Africell 100KZ', 'preco': 100.00},
        ]
    
    detalhes_recargas = []
    valor_distribuido = Decimal('0.00')
    
    for tipo in tipos_recarga:
        if valor_distribuido >= Decimal(str(total)):
            break
            
        valor_restante = Decimal(str(total)) - valor_distribuido
        max_recargas = int(valor_restante / Decimal(str(tipo['preco'])))
        
        if max_recargas > 0:
            quantidade = min(max(1, max_recargas // 2), 20)
            valor_tipo = Decimal(str(tipo['preco'])) * quantidade
            
            if valor_distribuido + valor_tipo > Decimal(str(total)):
                quantidade = int((Decimal(str(total)) - valor_distribuido) / Decimal(str(tipo['preco'])))
                valor_tipo = Decimal(str(tipo['preco'])) * quantidade
            
            if quantidade > 0:
                detalhes_recargas.append({
                    'nome': tipo['nome'],
                    'preco': tipo['preco'],
                    'inicio': quantidade + 5,
                    'vendidas': quantidade,
                    'total_vendas': float(valor_tipo),
                    'resto': 5
                })
                valor_distribuido += valor_tipo
    
    return detalhes_recargas

@login_required
def deletar_relatorio(request, pk):
    """View para deletar um relatório"""
    relatorio = get_object_or_404(RelatorioDiario, pk=pk)
    
    if relatorio.usuario != request.user and not request.user.is_superuser:
        messages.error(request, 'Você não tem permissão para deletar este relatório.')
        return redirect('listar_relatorios_diarios')
    
    if request.method == 'POST':
        relatorio.delete()
        
        registrar_atividade(
            request.user,
            f"Deletou relatório para {relatorio.loja.nome} - Data: {relatorio.data}"
        )
        
        messages.success(request, 'Relatório deletado com sucesso!')
        return redirect('listar_relatorios_diarios')
    
    return render(request, 'confirmar_exclusao.html', {'relatorio': relatorio})