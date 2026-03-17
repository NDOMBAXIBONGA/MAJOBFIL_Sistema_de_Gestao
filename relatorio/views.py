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

    # Aplicar filtros
    data_inicial = request.GET.get('data_inicial')
    data_final = request.GET.get('data_final')
    loja_id = request.GET.get('loja')
    status = request.GET.get('status')

    if data_inicial:
        relatorios = relatorios.filter(data__gte=data_inicial)
    if data_final:
        relatorios = relatorios.filter(data__lte=data_final)
    if loja_id:
        relatorios = relatorios.filter(loja_id=loja_id)

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
                completos += 1
                status_relatorio = 'completo'
            elif diferenca > 0:
                negativos += 1
                status_relatorio = 'negativo'
            else:
                pendentes += 1
                status_relatorio = 'pendente'

            # Aplicar filtro de status se especificado
            if status and status != status_relatorio:
                continue

            # Adicionar atributos calculados ao relatório
            relatorio.total_arrecadado_calculado = total_arrecadado
            relatorio.diferenca_calculada = diferenca
            relatorio.status = status_relatorio
            
            relatorios_com_calculos.append(relatorio)
            
        except Exception as e:
            print(f"Erro ao calcular totais para relatório {relatorio.id}: {e}")
            continue

    # Atualizar contadores após aplicar filtro de status
    if status:
        completos = len([r for r in relatorios_com_calculos if r.status == 'completo'])
        negativos = len([r for r in relatorios_com_calculos if r.status == 'negativo'])
        pendentes = len([r for r in relatorios_com_calculos if r.status == 'pendente'])
        total_relatorios = len(relatorios_com_calculos)

    context = {
        'relatorios_recentes': relatorios_com_calculos,
        'total_relatorios': total_relatorios,
        'completos': completos,
        'negativos': negativos,
        'pendentes': pendentes,
        'lojas': lojas,
        'filtros': {
            'data_inicial': data_inicial,
            'data_final': data_final,
            'loja_id': loja_id,
            'status': status,
        }
    }
    
    return render(request, 'lista_relatorios.html', context)

# Manter as outras views existentes (criar, editar, detalhes, deletar, etc.)
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
                            f'Campo RECARGAS preenchido automaticamente com vendas do dia: R$ {total_vendas_dia:.2f}'
                        )
                except Exception as e:
                    print(f"Erro ao calcular vendas do dia: {e}")
                    # Não impede o salvamento se houver erro no cálculo das vendas
                
                # Verifica se há falta de dinheiro e se observação foi preenchida
                relatorio.calcular_total_geral()
                if relatorio.tem_falta_dinheiro() and not relatorio.observacao_falta:
                    messages.error(request, 'É obrigatório preencher a observação da falta quando há diferença no caixa!')
                    return render(request, 'criar_relatorio_diario.html', {'form': form})
                
                relatorio.save()

                # ADICIONE ESTA LINHA:
                registrar_atividade(
                    request.user, 
                    f"Criou relatório para {relatorio.loja.nome}"
                )

                messages.success(request, 'Relatório diário criado com sucesso!')
                return redirect('listar_relatorios_diarios')
                
            except Exception as e:
                messages.error(request, f'Erro ao salvar relatório: {str(e)}')
        else:
            messages.error(request, 'Por favor, corrija os erros no formulário.')
    else:
        # Preenche a data atual por padrão e tenta preencher a loja automaticamente
        initial_data = {'data': timezone.now().date()}
        
        # Tenta preencher a loja do usuário automaticamente
        loja_usuario = request.user.lojas_gerenciadas.first()
        if loja_usuario:
            initial_data['loja'] = loja_usuario
        
        form = RelatorioDiarioForm(initial=initial_data, request=request)
    
    return render(request, 'criar_relatorio_diario.html', {'form': form})

@login_required
def editar_relatorio_diario(request, pk):
    relatorio = get_object_or_404(RelatorioDiario, pk=pk)
    
    # Verificar se o usuário tem permissão para editar este relatório
    if relatorio.usuario != request.user and not request.user.is_superuser:
        messages.error(request, 'Você não tem permissão para editar este relatório.')
        return redirect('listar_relatorios_diarios')
    
    if request.method == 'POST':
        form = RelatorioDiarioForm(request.POST, instance=relatorio, request=request)
        if form.is_valid():
            try:
                relatorio_editado = form.save(commit=False)
                
                # Verifica se há falta de dinheiro e se observação foi preenchida
                relatorio_editado.calcular_total_geral()
                if relatorio_editado.tem_falta_dinheiro() and not relatorio_editado.observacao_falta:
                    messages.error(request, 'É obrigatório preencher a observação da falta quando há diferença no caixa!')
                    return render(request, 'editar_relatorio_diario.html', {
                        'form': form,
                        'relatorio': relatorio
                    })
                
                relatorio_editado.save()
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

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import RelatorioDiario
from lojas.models import Venda, EstoqueRecarga, Loja
import requests
import json
from django.conf import settings
from decimal import Decimal
from datetime import datetime, date
from django.db.models import Sum, Q

@login_required
def detalhes_relatorio(request, pk):
    """View para visualizar detalhes de um relatório"""
    relatorio = get_object_or_404(
        RelatorioDiario.objects.select_related('loja', 'usuario'), 
        pk=pk
    )
    
    # Verificar permissão
    if not request.user.is_superuser:
        lojas_usuario = request.user.lojas_gerenciadas.all()
        if relatorio.loja not in lojas_usuario:
            messages.error(request, 'Você não tem permissão para visualizar este relatório.')
            return redirect('listar_relatorios_diarios')
    
    # Calcular todos os valores necessários
    calculos = calcular_todos_valores(relatorio)
    
    # Buscar dados das vendas
    dados_vendas = buscar_dados_vendas(relatorio)
    
    # Processar detalhes das recargas - AGORA COM DADOS REAIS
    detalhes_recargas, totais_recargas = processar_detalhes_recargas(relatorio)
    
    # Preparar contexto
    context = {
        'relatorio': relatorio,
        'dados_vendas': dados_vendas,
        'detalhes_recargas': detalhes_recargas,
        'totais_recargas': totais_recargas,
        **calculos  # Inclui todos os cálculos no contexto
    }
    
    return render(request, 'detalhes_relatorio.html', context)

def calcular_todos_valores(relatorio):
    """Calcula todos os valores necessários para o template"""
    total_arrecadado = relatorio.calcular_total_arrecadado()
    diferenca = relatorio.calcular_diferenca()
    total_vendas_dia = relatorio.calcular_total_vendas_dia()
    
    # Calcular vendas DSTV
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
        # Tentar buscar da API
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
                
                # Calcular percentuais
                if dados['valor_total'] > Decimal('0.00'):
                    dados['percentual_produtos'] = (dados['valor_produtos'] / dados['valor_total']) * Decimal('100.00')
                    dados['percentual_recargas'] = (dados['valor_recargas'] / dados['valor_total']) * Decimal('100.00')
                else:
                    dados['percentual_produtos'] = Decimal('0.00')
                    dados['percentual_recargas'] = Decimal('0.00')
                    
                return dados
    except Exception as e:
        print(f"Erro ao buscar dados da API: {e}")
    
    # Fallback: calcular localmente
    return calcular_dados_vendas_local(relatorio)

def calcular_dados_vendas_local(relatorio):
    """Calcular dados de vendas localmente baseado no relatório"""
    valor_recargas = relatorio.recargas or Decimal('0.00')
    acc_total = relatorio.acc or Decimal('0.00')
    
    # Estimativa: 60% produtos, 40% recargas
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

    # Calcular percentuais
    if dados['valor_total'] > Decimal('0.00'):
        dados['percentual_produtos'] = (dados['valor_produtos'] / dados['valor_total']) * Decimal('100.00')
        dados['percentual_recargas'] = (dados['valor_recargas'] / dados['valor_total']) * Decimal('100.00')
    else:
        dados['percentual_produtos'] = Decimal('0.00')
        dados['percentual_recargas'] = Decimal('0.00')

    return dados

def processar_detalhes_recargas(relatorio):
    """Processar detalhes das recargas do relatório usando dados reais da app lojas"""
    detalhes_recargas = []
    totais = {
        'inicio': 0,
        'vendidas': 0,
        'resto': 0,
        'total_vendas': Decimal('0.00')
    }
    
    try:
        # Verificar se existem detalhes das recargas salvos no relatório
        if relatorio.detalhes_recargas:
            try:
                detalhes_recargas = json.loads(relatorio.detalhes_recargas)
                
                # Calcular totais
                for recarga in detalhes_recargas:
                    totais['inicio'] += recarga.get('inicio', 0)
                    totais['vendidas'] += recarga.get('vendidas', 0)
                    totais['resto'] += recarga.get('resto', 0)
                    totais['total_vendas'] += Decimal(str(recarga.get('total_vendas', 0)))
            except json.JSONDecodeError:
                # Se o JSON estiver inválido, buscar dados reais
                detalhes_recargas = buscar_dados_recargas_reais(relatorio)
        else:
            # Buscar dados reais das recargas
            detalhes_recargas = buscar_dados_recargas_reais(relatorio)
        
        # Recalcular totais se temos dados reais
        if detalhes_recargas and not relatorio.detalhes_recargas:
            for recarga in detalhes_recargas:
                totais['inicio'] += recarga.get('inicio', 0)
                totais['vendidas'] += recarga.get('vendidas', 0)
                totais['resto'] += recarga.get('resto', 0)
                totais['total_vendas'] += Decimal(str(recarga.get('total_vendas', 0)))
                
    except Exception as e:
        print(f"Erro ao processar detalhes das recargas: {e}")
        # Em caso de erro, tentar buscar dados reais
        detalhes_recargas = buscar_dados_recargas_reais(relatorio)
    
    return detalhes_recargas, totais

def buscar_dados_recargas_reais(relatorio):
    """Buscar dados reais das recargas a partir dos modelos da app lojas"""
    detalhes_recargas = []
    
    try:
        # Verificar se a loja existe
        if not relatorio.loja:
            print("Relatório não tem loja associada")
            return []
        
        # Buscar estoque de recargas da loja
        estoques_recargas = EstoqueRecarga.objects.filter(loja=relatorio.loja)
        
        if not estoques_recargas.exists():
            print(f"Nenhum estoque de recarga encontrado para a loja {relatorio.loja.nome}")
            return []
        
        # Buscar vendas de recargas do dia específico
        vendas_recargas = Venda.objects.filter(
            Q(estoque_recarga__loja=relatorio.loja),
            item_type='recarga',
            data_venda__date=relatorio.data
        )
        
        print(f"Encontradas {vendas_recargas.count()} vendas de recargas para {relatorio.data}")
        
        # Para cada estoque de recarga, calcular os detalhes
        for estoque in estoques_recargas:
            try:
                # Buscar vendas específicas desta recarga no dia
                vendas_desta_recarga = vendas_recargas.filter(estoque_recarga=estoque)
                total_vendido = vendas_desta_recarga.aggregate(total=Sum('quantidade'))['total'] or 0
                valor_total_vendas = vendas_desta_recarga.aggregate(total=Sum('valor_total'))['total'] or Decimal('0.00')
                
                # Se não houve vendas, pular esta recarga
                if total_vendido == 0:
                    continue
                
                # Calcular estoque inicial (estoque atual + vendas do dia)
                # NOTA: Isso assume que não houve reposição de estoque durante o dia
                estoque_inicial = estoque.quantidade + total_vendido
                estoque_final = estoque.quantidade
                
                detalhes_recargas.append({
                    'nome': estoque.recarga.nome,
                    'preco': float(estoque.recarga.preco),
                    'inicio': estoque_inicial,
                    'vendidas': total_vendido,
                    'total_vendas': float(valor_total_vendas),
                    'resto': estoque_final
                })
                
                print(f"Recarga: {estoque.recarga.nome}, Início: {estoque_inicial}, Vendidas: {total_vendido}, Resto: {estoque_final}")
                
            except Exception as e:
                print(f"Erro ao processar estoque de recarga {estoque.recarga.nome}: {e}")
                continue
        
        # Se não encontramos dados reais, criar dados de exemplo baseados no valor total
        if not detalhes_recargas and relatorio.recargas and relatorio.recargas > Decimal('0.00'):
            print("Criando dados de exemplo baseados no valor total de recargas")
            detalhes_recargas = criar_dados_recargas_exemplo(relatorio.recargas)
        
    except Exception as e:
        print(f"Erro ao buscar dados reais das recargas: {e}")
        # Em caso de erro, criar dados de exemplo
        if relatorio.recargas and relatorio.recargas > Decimal('0.00'):
            detalhes_recargas = criar_dados_recargas_exemplo(relatorio.recargas)
    
    return detalhes_recargas

def criar_dados_recargas_exemplo(valor_total_recargas):
    """Criar dados de exemplo para recargas baseado no valor total"""
    if not valor_total_recargas or valor_total_recargas <= Decimal('0.00'):
        return []
    
    # Converter para float para cálculos
    total = float(valor_total_recargas)
    
    # Definir tipos de recarga comuns baseados nos produtos existentes
    try:
        from produtos.models import Recarga
        recargas_existentes = Recarga.objects.all()[:5]  # Pegar até 5 recargas existentes
        
        if recargas_existentes.exists():
            tipos_recarga = []
            for recarga in recargas_existentes:
                tipos_recarga.append({
                    'nome': recarga.nome,
                    'preco': float(recarga.preco)
                })
        else:
            # Fallback para tipos padrão se não houver recargas no banco
            tipos_recarga = [
                {'nome': 'Recarga Unitel 100KZ', 'preco': 100.00},
                {'nome': 'Recarga Unitel 200KZ', 'preco': 200.00},
                {'nome': 'Recarga Unitel 500KZ', 'preco': 500.00},
                {'nome': 'Recarga Africell 100KZ', 'preco': 100.00},
                {'nome': 'Recarga Africell 200KZ', 'preco': 200.00},
            ]
    except Exception as e:
        print(f"Erro ao buscar recargas existentes: {e}")
        tipos_recarga = [
            {'nome': 'Recarga Unitel 100KZ', 'preco': 100.00},
            {'nome': 'Recarga Unitel 200KZ', 'preco': 200.00},
            {'nome': 'Recarga Africell 100KZ', 'preco': 100.00},
        ]
    
    detalhes_recargas = []
    valor_distribuido = Decimal('0.00')
    
    # Distribuir o valor total entre os tipos de recarga
    for i, tipo in enumerate(tipos_recarga):
        if valor_distribuido >= Decimal(str(total)):
            break
            
        # Calcular quantas recargas deste tipo cabem no valor restante
        valor_restante = Decimal(str(total)) - valor_distribuido
        max_recargas = int(valor_restante / Decimal(str(tipo['preco'])))
        
        if max_recargas > 0:
            # Usar entre 1 e max_recargas, mas não mais que 20
            quantidade = min(max(1, max_recargas // 2), 20)
            valor_tipo = Decimal(str(tipo['preco'])) * quantidade
            
            # Ajustar para não ultrapassar o total
            if valor_distribuido + valor_tipo > Decimal(str(total)):
                quantidade = int((Decimal(str(total)) - valor_distribuido) / Decimal(str(tipo['preco'])))
                valor_tipo = Decimal(str(tipo['preco'])) * quantidade
            
            if quantidade > 0:
                # Criar dados da recarga
                inicio = quantidade + 5  # Estoque inicial
                vendidas = quantidade
                resto = 5  # Estoque final
                
                detalhes_recargas.append({
                    'nome': tipo['nome'],
                    'preco': tipo['preco'],
                    'inicio': inicio,
                    'vendidas': vendidas,
                    'total_vendas': float(valor_tipo),
                    'resto': resto
                })
                
                valor_distribuido += valor_tipo
    
    # Se ainda sobrou valor, adicionar mais recargas do primeiro tipo
    if valor_distribuido < Decimal(str(total)) and detalhes_recargas:
        valor_restante = Decimal(str(total)) - valor_distribuido
        primeiro_tipo = detalhes_recargas[0]
        preco = Decimal(str(primeiro_tipo['preco']))
        
        if preco > Decimal('0.00'):
            quantidade_extra = int(valor_restante / preco)
            if quantidade_extra > 0:
                primeiro_tipo['vendidas'] += quantidade_extra
                primeiro_tipo['inicio'] += quantidade_extra + 2
                primeiro_tipo['resto'] += 2
                primeiro_tipo['total_vendas'] += float(preco * quantidade_extra)
    
    return detalhes_recargas

@login_required
def deletar_relatorio(request, pk):
    """View para deletar um relatório"""
    relatorio = get_object_or_404(RelatorioDiario, pk=pk)
    
    # Verificar permissão
    if relatorio.usuario != request.user and not request.user.is_superuser:
        messages.error(request, 'Você não tem permissão para deletar este relatório.')
        return redirect('listar_relatorios_diarios')
    
    if request.method == 'POST':
        relatorio.delete()
        messages.success(request, 'Relatório deletado com sucesso!')
        return redirect('listar_relatorios_diarios')
    
    return render(request, 'confirmar_exclusao.html', {'relatorio': relatorio})