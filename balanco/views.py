from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse, HttpResponse
import csv
from django.db.models import Q, Sum, Avg
from django.contrib import messages
from datetime import datetime, timedelta
from decimal import Decimal
import json
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import Balanco, MovimentoEstoque
from produtos.models import Produto
from lojas.models import Venda, Loja, EstoqueLoja

@login_required
@permission_required('balanco.views', raise_exception=True)
def lista_balancos(request):
    """Lista todos os balanços com filtros e paginação"""
    # SEMPRE buscar todas as lojas para o modal de criação
    todas_lojas = Loja.objects.all().prefetch_related('gerentes')
    
    # Mas para a tabela de balanços, filtrar baseado no usuário
    if request.user.is_superuser:
        balancos_queryset = Balanco.objects.all().select_related('loja').prefetch_related('loja__gerentes')
        lojas_para_tabela = todas_lojas
    else:
        lojas_gerenciadas = request.user.lojas_gerenciadas.all().prefetch_related('gerentes')
        balancos_queryset = Balanco.objects.filter(loja__in=lojas_gerenciadas).select_related('loja').prefetch_related('loja__gerentes')
        lojas_para_tabela = lojas_gerenciadas
    
    # Filtros
    periodo_tipo = request.GET.get('periodo_tipo', '')
    loja_id = request.GET.get('loja', '')
    ano = request.GET.get('ano', '')
    mes = request.GET.get('mes', '')
    
    if periodo_tipo:
        balancos_queryset = balancos_queryset.filter(periodo_tipo=periodo_tipo)
    if loja_id:
        balancos_queryset = balancos_queryset.filter(loja_id=loja_id)
    if ano and ano != 'todos':
        balancos_queryset = balancos_queryset.filter(data_inicio__year=ano)
    if mes:
        balancos_queryset = balancos_queryset.filter(data_inicio__month=mes)
    
    # Ordenar por data de início (mais recente primeiro)
    balancos_queryset = balancos_queryset.order_by('-data_inicio')
    
    # PAGINAÇÃO - 4 balanços por página
    page = request.GET.get('page', 1)
    paginator = Paginator(balancos_queryset, 4)  # 4 itens por página
    
    try:
        balancos = paginator.page(page)
    except PageNotAnInteger:
        balancos = paginator.page(1)
    except EmptyPage:
        balancos = paginator.page(paginator.num_pages)
    
    # Calcular a diferença para cada balanço na página atual e obter o primeiro gerente
    for balanco in balancos:
        total_geral = balanco.total_geral_relatorios or 0
        total_arrecadado = balanco.total_arrecadado or 0
        balanco.diferenca = total_geral - total_arrecadado
        balanco.sobra = total_arrecadado - total_geral
        
        # Obter o primeiro gerente da loja
        if hasattr(balanco.loja, 'gerentes') and balanco.loja.gerentes.exists():
            balanco.primeiro_gerente = balanco.loja.gerentes.first()
        else:
            balanco.primeiro_gerente = None
    
    # Calcular totais CORRIGIDOS - usar aggregate para evitar múltiplas queries
    totais = balancos_queryset.aggregate(
        total_vendas=Sum('total_vendas_geral'),
        total_geral=Sum('total_geral_relatorios'),
        total_arrecadado=Sum('total_arrecadado')
    )
    
    # Anos disponíveis
    anos_disponiveis = Balanco.objects.dates('data_inicio', 'year').values_list('data_inicio__year', flat=True).distinct()
    
    context = {
        'balancos': balancos,  # Agora é um objeto Page, não um QuerySet
        'lojas': lojas_para_tabela,  # Para a tabela/filtros
        'todas_lojas': todas_lojas,  # Para o modal de criação (TODAS as lojas)
        'periodo_tipo_selecionado': periodo_tipo,
        'loja_selecionada': loja_id,
        'ano_selecionado': ano,
        'mes_selecionado': mes,
        'anos_disponiveis': anos_disponiveis,
        'total_vendas': totais['total_vendas'] or 0,
        'total_geral': totais['total_geral'] or 0,  # NOVO: Total Geral
        'total_arrecadado': totais['total_arrecadado'] or 0,  # NOVO: Total Arrecadado
        'total_balancos': balancos_queryset.count(),  # Total de balanços (sem paginação)
        'periodo_choices': Balanco.PERIODO_CHOICES,
    }
    
    return render(request, 'lista_balancos.html', context)

@login_required
def detalhe_balanco(request, balanco_id):
    """Detalhes de um balanço específico - VERSÃO COM PAGINAÇÃO"""
    balanco = get_object_or_404(Balanco, id=balanco_id)
    
    # Verificar permissão
    if not request.user.is_superuser and balanco.loja not in request.user.lojas_gerenciadas.all():
        messages.error(request, 'Sem permissão para visualizar este balanço.')
        return redirect('balancos:lista_balancos')
    
    # FORÇAR recálculo completo dos dados
    try:
        balanco.calcular_todos_dados()
        balanco.save()
    except Exception as e:
        print(f"Erro ao calcular dados do balanço: {e}")
        # Continua mesmo com erro
    
    # Obter TODOS os dados detalhados
    try:
        # Dados das vendas diárias (para paginação)
        todas_vendas_diarias = balanco.detalhes_vendas_diarias or []
        
        # Configurar paginação
        page = request.GET.get('page_vendas', 1)
        paginator = Paginator(todas_vendas_diarias, 30)  # 30 itens por página
        
        try:
            detalhes_vendas = paginator.page(page)
        except PageNotAnInteger:
            detalhes_vendas = paginator.page(1)
        except EmptyPage:
            detalhes_vendas = paginator.page(paginator.num_pages)
        
        # Top produtos
        top_produtos = balanco.detalhes_produtos or []
        
        # Top recargas
        top_recargas = balanco.detalhes_recargas or []
        
        # Top vendedores
        top_vendedores = balanco.detalhes_vendedores or []
        
        # Dados dos relatórios
        dados_relatorios = balanco.detalhes_relatorios or {}
        
    except Exception as e:
        print(f"Erro ao obter dados detalhados: {e}")
        # Criar estruturas vazias
        todas_vendas_diarias = []
        detalhes_vendas = Paginator([], 30).page(1)
        top_produtos = []
        top_recargas = []
        top_vendedores = []
        dados_relatorios = {}
    
    # Garantir que dados_relatorios tem estrutura completa
    if not dados_relatorios:
        dados_relatorios = criar_estrutura_dados_vazia(balanco)
    
    context = {
        'balanco': balanco,
        'detalhes_vendas': detalhes_vendas,
        'todas_vendas_diarias': todas_vendas_diarias,
        'top_produtos': top_produtos,
        'top_recargas': top_recargas,
        'top_vendedores': top_vendedores,
        'dados_relatorios': dados_relatorios,
    }
    
    return render(request, 'detalhe_balanco.html', context)

def criar_estrutura_dados_vazia(balanco):
    """Cria estrutura de dados vazia para evitar erros"""
    return {
        'dstv': {
            'total': float(getattr(balanco, 'total_dstv', 0)),
            'inicio': float(getattr(balanco, 'total_inicio_dstv', 0)),
            'resto': float(getattr(balanco, 'total_resto_dstv', 0)),
            'sem_resto': 0,
            'com_5_percent': 0,
            'diferenca': 0,
            'status': 'positivo'
        },
        'zap': {
            'total': float(getattr(balanco, 'total_zap', 0)),
            'resto': float(getattr(balanco, 'total_resto_zap', 0)),
            'sem_resto': 0
        },
        'unitel': {
            'total': float(getattr(balanco, 'total_unitel', 0)),
            'resto': float(getattr(balanco, 'total_resto_unitel', 0)),
            'sem_resto': 0
        },
        'africell': {
            'total': float(getattr(balanco, 'total_africell', 0)),
            'resto': float(getattr(balanco, 'total_resto_africell', 0)),
            'sem_resto': 0
        },
        'dm': float(getattr(balanco, 'total_dm', 0)),
        'moedas': float(getattr(balanco, 'total_moedas', 0)),
        'tpa': float(getattr(balanco, 'total_tpa', 0)),
        'gastos': float(getattr(balanco, 'total_gastos', 0)),
        'total_geral': float(getattr(balanco, 'total_geral_relatorios', 0)),
        'total_arrecadado': float(getattr(balanco, 'total_arrecadado', 0)),
        'diferenca_balanco': 0,
        'status_balanco': 'positivo'
    }

@login_required
def criar_balanco_personalizado(request):
    """Cria balanço com período personalizado - VERSAO CORRIGIDA"""
    if request.method == 'POST':
        try:
            # Obter dados do formulário
            loja_id = request.POST.get('loja_id')
            periodo_tipo = request.POST.get('periodo_tipo')
            data_inicio_str = request.POST.get('data_inicio')
            data_fim_str = request.POST.get('data_fim')
            descricao = request.POST.get('descricao', '')
            
            # Validações básicas
            if not all([loja_id, periodo_tipo, data_inicio_str, data_fim_str]):
                messages.error(request, 'Preencha todos os campos obrigatórios.')
                return redirect('lista_balancos')
            
            # Buscar a loja
            try:
                loja = Loja.objects.get(id=loja_id)
            except Loja.DoesNotExist:
                messages.error(request, 'Loja não encontrada.')
                return redirect('lista_balancos')
            
            # Converter datas
            data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
            data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
            
            # Verificar datas
            if data_inicio > data_fim:
                messages.error(request, 'A data de início deve ser anterior à data de fim.')
                return redirect('lista_balancos')
            
            # VERIFICAÇÃO DE PERMISSÃO SIMPLIFICADA
            if not request.user.is_superuser:
                # Usuário normal - verificar se gerencia a loja selecionada
                if not request.user.lojas_gerenciadas.filter(id=loja_id).exists():
                    messages.error(request, f'Você não tem permissão para criar balanços para a loja {loja.nome}.')
                    return redirect('lista_balancos')
            
            # Verificar se já existe balanço idêntico
            balanco_existente = Balanco.objects.filter(
                loja=loja,
                periodo_tipo=periodo_tipo,
                data_inicio=data_inicio,
                data_fim=data_fim
            ).first()
            
            if balanco_existente:
                messages.info(request, f'Já existe um balanço para este período. <a href="{balanco_existente.get_absolute_url()}">Ver balanço</a>')
                return redirect('lista_balancos')
            
            # CRIAR O BALANÇO
            balanco = Balanco.objects.create(
                loja=loja,
                periodo_tipo=periodo_tipo,
                data_inicio=data_inicio,
                data_fim=data_fim,
                descricao_periodo=descricao or f"Balanço {periodo_tipo.capitalize()} - {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}",
                criado_por=request.user
            )
            
            messages.success(request, f'✅ Balanço criado com sucesso para {loja.nome}!')
            return redirect('detalhe_balanco', balanco_id=balanco.id)
            
        except Exception as e:
            messages.error(request, f'❌ Erro ao criar balanço: {str(e)}')
            print(f"ERRO ao criar balanço: {str(e)}")  # Log para debug
    
    # Se não for POST, redirecionar
    return redirect('lista_balancos')

@login_required
def gerar_balanco_rapido(request, periodo_tipo):
    """Gera balanço rápido para o período atual"""
    try:
        # Determinar datas baseado no período
        hoje = datetime.now().date()
        
        if periodo_tipo == 'diario':
            data_inicio = hoje
            data_fim = hoje
            descricao = f"Balanço Diário - {hoje.strftime('%d/%m/%Y')}"
        elif periodo_tipo == 'semanal':
            data_inicio = hoje - timedelta(days=hoje.weekday())
            data_fim = data_inicio + timedelta(days=6)
            descricao = f"Balanço Semanal - {data_inicio.strftime('%d/%m')} a {data_fim.strftime('%d/%m/%Y')}"
        elif periodo_tipo == 'mensal':
            data_inicio = hoje.replace(day=1)
            if hoje.month == 12:
                data_fim = hoje.replace(year=hoje.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                data_fim = hoje.replace(month=hoje.month + 1, day=1) - timedelta(days=1)
            descricao = f"Balanço Mensal - {hoje.strftime('%B %Y')}"
        elif periodo_tipo == 'anual':
            data_inicio = hoje.replace(month=1, day=1)
            data_fim = hoje.replace(month=12, day=31)
            descricao = f"Balanço Anual - {hoje.year}"
        else:
            messages.error(request, 'Tipo de período inválido.')
            return redirect('lista_balancos')
        
        # Para superusuários, usar primeira loja disponível
        # Para usuários normais, usar primeira loja gerenciada
        if request.user.is_superuser:
            loja = Loja.objects.first()
        else:
            loja = request.user.lojas_gerenciadas.first()
        
        if not loja:
            messages.error(request, 'Nenhuma loja disponível para gerar balanço.')
            return redirect('lista_balancos')
        
        # Verificar se já existe balanço
        balanco_existente = Balanco.objects.filter(
            loja=loja,
            periodo_tipo=periodo_tipo,
            data_inicio=data_inicio,
            data_fim=data_fim
        ).first()
        
        if balanco_existente:
            messages.info(request, f'Balanço {periodo_tipo} já existe para este período.')
            return redirect('detalhe_balanco', balanco_id=balanco_existente.id)
        
        # Criar balanço
        balanco = Balanco.objects.create(
            loja=loja,
            periodo_tipo=periodo_tipo,
            data_inicio=data_inicio,
            data_fim=data_fim,
            descricao_periodo=descricao,
            criado_por=request.user
        )
        
        messages.success(request, f'Balanço {periodo_tipo} criado com sucesso para {loja.nome}!')
        return redirect('detalhe_balanco', balanco_id=balanco.id)
        
    except Exception as e:
        messages.error(request, f'Erro ao gerar balanço: {str(e)}')
        return redirect('lista_balancos')

@login_required
def excluir_balanco(request, balanco_id):
    """Exclui um balanço"""
    balanco = get_object_or_404(Balanco, id=balanco_id)
    
    if not request.user.is_superuser and balanco.loja not in request.user.lojas_gerenciadas.all():
        messages.error(request, 'Sem permissão para excluir este balanço.')
        return redirect('lista_balancos')
    
    balanco.delete()
    messages.success(request, 'Balanço excluído com sucesso!')
    return redirect('lista_balancos')

# Views para períodos específicos
@login_required
def balanco_diario(request):
    return render_balanco_periodo(request, 'diario')

@login_required
def balanco_semanal(request):
    return render_balanco_periodo(request, 'semanal')

@login_required
def balanco_mensal(request):
    return render_balanco_periodo(request, 'mensal')

@login_required
def balanco_anual(request):
    return render_balanco_periodo(request, 'anual')

def render_balanco_periodo(request, periodo_tipo):
    """Renderiza página de balanço por período"""
    if request.user.is_superuser:
        balancos = Balanco.objects.filter(periodo_tipo=periodo_tipo).select_related('loja', 'criado_por')
        lojas = Loja.objects.all()
    else:
        lojas_gerenciadas = request.user.lojas_gerenciadas.all()
        balancos = Balanco.objects.filter(
            periodo_tipo=periodo_tipo,
            loja__in=lojas_gerenciadas
        ).select_related('loja', 'criado_por')
        lojas = lojas_gerenciadas
    
    # Filtros
    loja_id = request.GET.get('loja', '')
    ano = request.GET.get('ano', '')
    mes = request.GET.get('mes', '')
    
    if loja_id:
        balancos = balancos.filter(loja_id=loja_id)
    if ano and ano != 'todos':
        balancos = balancos.filter(data_inicio__year=ano)
    if mes:
        balancos = balancos.filter(data_inicio__month=mes)
    
    # Calcular totais
    total_vendas = sum(b.total_vendas_geral for b in balancos)
    total_lucro = sum(b.lucro_bruto for b in balancos)
    total_relatorios = sum(b.total_geral_relatorios for b in balancos)
    
    # Anos disponíveis
    anos_disponiveis = Balanco.objects.filter(periodo_tipo=periodo_tipo).dates('data_inicio', 'year').values_list('data_inicio__year', flat=True).distinct()
    
    context = {
        'balancos': balancos.order_by('-data_inicio'),
        'lojas': lojas,
        'periodo_tipo': periodo_tipo,
        'loja_selecionada': loja_id,
        'ano_selecionado': ano,
        'mes_selecionado': mes,
        'anos_disponiveis': anos_disponiveis,
        'total_vendas': total_vendas,
        'total_lucro': total_lucro,
        'total_relatorios': total_relatorios,
    }
    
    return render(request, f'balanco_{periodo_tipo}.html', context)

# APIs
@login_required
def api_dados_balanco(request, balanco_id):
    """API para dados do balanço"""
    balanco = get_object_or_404(Balanco, id=balanco_id)
    
    if not request.user.is_superuser and balanco.loja not in request.user.lojas_gerenciadas.all():
        return JsonResponse({'error': 'Sem permissão'}, status=403)
    
    return JsonResponse({
        'success': True,
        'balanco': {
            'total_vendas': float(balanco.total_vendas_geral),
            'total_relatorios': float(balanco.total_geral_relatorios),
            'lucro_bruto': float(balanco.lucro_bruto),
            'margem_lucro': float(balanco.margem_lucro),
            'total_arrecadado': float(balanco.total_arrecadado),
            'diferenca_caixa': float(balanco.diferenca_caixa),
        },
        'detalhes_vendas': balanco.detalhes_vendas_diarias,
        'detalhes_relatorios': balanco.detalhes_relatorios_diarios,
    })

###################################################################
#                                                                 #
#################### Movimentos de Produtos #######################
#                                                                 #
###################################################################

# estoque/views.py (versão atualizada)
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Sum, Count, Avg, Q, F
from django.http import JsonResponse, HttpResponse
from datetime import datetime, timedelta
from decimal import Decimal
import json
import csv

from produtos.models import Produto, Recarga
from lojas.models import Loja, EstoqueLoja, EstoqueRecarga, Venda

@login_required
def listar_produtos_estoque(request):
    """
    Lista todos os produtos de todas as lojas com informações de estoque.
    Versão consolidada usando os modelos existentes.
    """
    # Filtrar lojas baseado no usuário
    if request.user.is_superuser:
        lojas = Loja.objects.all().order_by('nome')
    else:
        lojas = request.user.lojas_gerenciadas.all().order_by('nome')
    
    # Filtros
    loja_id = request.GET.get('loja', '')
    tipo_produto = request.GET.get('tipo', 'produtos')  # produtos ou recargas
    status_estoque = request.GET.get('status', '')
    
    # Obter todos os produtos e recargas
    produtos = Produto.objects.all().order_by('nome')
    recargas = Recarga.objects.all().order_by('nome')
    
    # Dados para a tabela consolidada
    tabela_estoque = []
    
    if tipo_produto == 'produtos':
        items = produtos
        item_type = 'produto'
    else:
        items = recargas
        item_type = 'recarga'
    
    # Para cada item (produto ou recarga), coletar estoque em cada loja
    for item in items:
        item_data = {
            'id': item.id,
            'nome': item.nome,
            'preco': item.preco,
            'tipo': item_type,
            'estoques': [],
            'estoque_total': 0,
            'valor_total_estoque': Decimal('0.00')
        }
        
        # Coletar estoque em cada loja
        for loja in lojas:
            if loja_id and str(loja.id) != loja_id:
                continue  # Pular se filtro de loja ativo
                
            if item_type == 'produto':
                try:
                    estoque = EstoqueLoja.objects.get(loja=loja, produto=item)
                    quantidade = estoque.quantidade
                except EstoqueLoja.DoesNotExist:
                    quantidade = 0
            else:  # recarga
                try:
                    estoque = EstoqueRecarga.objects.get(loja=loja, recarga=item)
                    quantidade = estoque.quantidade
                except EstoqueRecarga.DoesNotExist:
                    quantidade = 0
            
            # Calcular valor do estoque nesta loja
            valor_estoque_loja = quantidade * item.preco
            
            # Adicionar ao estoque total
            item_data['estoque_total'] += quantidade
            item_data['valor_total_estoque'] += valor_estoque_loja
            
            # Status do estoque
            if quantidade == 0:
                status = 'esgotado'
                status_class = 'danger'
            elif quantidade < 10:
                status = 'baixo'
                status_class = 'warning'
            else:
                status = 'normal'
                status_class = 'success'
            
            # Filtrar por status se especificado
            if status_estoque and status != status_estoque:
                continue
            
            item_data['estoques'].append({
                'loja_id': loja.id,
                'loja_nome': loja.nome,
                'quantidade': quantidade,
                'valor_estoque': valor_estoque_loja,
                'status': status,
                'status_class': status_class,
                'cidade': loja.cidade
            })
        
        # Adicionar item à tabela apenas se tiver estoque ou se não houver filtro de loja
        if not loja_id or item_data['estoques']:
            tabela_estoque.append(item_data)
    
    # Ordenar por valor total de estoque (desc)
    tabela_estoque.sort(key=lambda x: x['valor_total_estoque'], reverse=True)
    
    # Paginação
    paginator = Paginator(tabela_estoque, 25)
    page = request.GET.get('page')
    tabela_paginada = paginator.get_page(page)
    
    # Estatísticas
    total_items = len(tabela_estoque)
    total_estoque = sum(item['estoque_total'] for item in tabela_estoque)
    total_valor_estoque = sum(item['valor_total_estoque'] for item in tabela_estoque)
    
    # Contar status
    contagem_status = {
        'normal': 0,
        'baixo': 0,
        'esgotado': 0
    }
    
    for item in tabela_estoque:
        for estoque in item['estoques']:
            contagem_status[estoque['status']] += 1
    
    context = {
        'tabela_estoque': tabela_paginada,
        'lojas': lojas,
        'loja_selecionada': loja_id,
        'tipo_selecionado': tipo_produto,
        'status_selecionado': status_estoque,
        'estatisticas': {
            'total_items': total_items,
            'total_estoque': total_estoque,
            'total_valor_estoque': total_valor_estoque,
            'contagem_status': contagem_status
        },
        'tipos': [
            ('produtos', 'Produtos'),
            ('recargas', 'Recargas')
        ],
        'status_opcoes': [
            ('', 'Todos'),
            ('normal', 'Normal'),
            ('baixo', 'Estoque Baixo'),
            ('esgotado', 'Esgotado')
        ]
    }
    
    return render(request, 'estoque/listar_movimentos_estoque.html', context)

@login_required
def detalhe_produto_loja(request, produto_id, loja_id=None):
    """
    Mostra detalhes de um produto em uma loja específica.
    Se loja_id não for especificado, mostra todas as lojas.
    """
    produto = get_object_or_404(Produto, id=produto_id)
    loja_selecionada = None
    
    # Se loja_id especificado, buscar loja e verificar permissões
    if loja_id:
        loja_selecionada = get_object_or_404(Loja, id=loja_id)
        # Verificar se usuário tem acesso à loja
        if not request.user.is_superuser and loja_selecionada not in request.user.lojas_gerenciadas.all():
            messages.error(request, 'Você não tem acesso a esta loja.')
            return redirect('listar_produtos_estoque')
    
    # Determinar quais lojas mostrar (baseado nas permissões)
    if request.user.is_superuser:
        lojas_disponiveis = Loja.objects.all()
    else:
        lojas_disponiveis = request.user.lojas_gerenciadas.all()
    
    # Se uma loja específica foi selecionada, usar apenas ela
    if loja_selecionada:
        lojas_query = [loja_selecionada]
    else:
        lojas_query = lojas_disponiveis
    
    # Coletar dados de estoque e vendas para cada loja
    estoques_lojas = []
    total_estoque = 0
    total_valor_estoque = Decimal('0.00')
    total_vendas = 0
    total_vendido = 0
    total_valor_vendido = Decimal('0.00')
    lojas_com_estoque = 0
    
    for loja in lojas_query:
        # Buscar estoque
        try:
            estoque = EstoqueLoja.objects.get(loja=loja, produto=produto)
            quantidade_estoque = estoque.quantidade
            status = estoque.status_estoque
        except EstoqueLoja.DoesNotExist:
            quantidade_estoque = 0
            status = 'esgotado'
        
        # Buscar vendas deste produto nesta loja
        vendas_loja = Venda.objects.filter(
            estoque_loja__loja=loja,
            estoque_loja__produto=produto,
            item_type='produto'
        )
        
        quantidade_vendida = vendas_loja.aggregate(total=Sum('quantidade'))['total'] or 0
        valor_vendido = vendas_loja.aggregate(total=Sum('valor_total'))['total'] or Decimal('0.00')
        num_vendas = vendas_loja.count()
        
        # Atualizar totais gerais
        total_estoque += quantidade_estoque
        total_valor_estoque += quantidade_estoque * produto.preco
        total_vendas += num_vendas
        total_vendido += quantidade_vendida
        total_valor_vendido += valor_vendido
        
        if quantidade_estoque > 0:
            lojas_com_estoque += 1
        
        # Adicionar dados da loja à lista
        estoques_lojas.append({
            'loja': loja,
            'quantidade': quantidade_estoque,
            'status': status,
            'total_vendas': num_vendas,
            'quantidade_vendida': quantidade_vendida,
            'valor_vendido': float(valor_vendido),
            'valor_estoque': float(quantidade_estoque * produto.preco)
        })
    
    # Buscar histórico de vendas (últimas 50 vendas deste produto)
    vendas = Venda.objects.filter(
        estoque_loja__produto=produto,
        item_type='produto'
    ).select_related(
        'estoque_loja__loja', 
        'vendedor'
    ).order_by('-data_venda')[:50]
    
    # Preparar dados para gráfico de vendas por mês (últimos 6 meses)
    hoje = datetime.now()
    meses_labels = []
    vendas_mensais = []
    
    for i in range(5, -1, -1):  # Últimos 6 meses
        data_referencia = hoje - timedelta(days=30*i)
        mes_label = data_referencia.strftime('%b/%Y')
        meses_labels.append(mes_label)
        
        # Calcular início e fim do mês
        inicio_mes = data_referencia.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        if data_referencia.month == 12:
            fim_mes = data_referencia.replace(
                year=data_referencia.year + 1, 
                month=1, 
                day=1
            )
        else:
            fim_mes = data_referencia.replace(
                month=data_referencia.month + 1, 
                day=1
            )
        
        # Buscar vendas do mês
        vendas_mes = Venda.objects.filter(
            estoque_loja__produto=produto,
            item_type='produto',
            data_venda__gte=inicio_mes,
            data_venda__lt=fim_mes
        ).aggregate(total=Sum('quantidade'))['total'] or 0
        
        vendas_mensais.append(vendas_mes)
    
    # Estatísticas consolidados
    estatisticas = {
        'total_estoque': total_estoque,
        'total_valor_estoque': float(total_valor_estoque),
        'total_lojas': len(lojas_query),
        'lojas_com_estoque': lojas_com_estoque,
        'total_vendas': total_vendas,
        'total_vendido': total_vendido,
        'valor_total_vendido': float(total_valor_vendido),
    }
    
    # Converter dados para JSON para uso no JavaScript
    grafico_meses = json.dumps(meses_labels)
    grafico_vendas = json.dumps(vendas_mensais)
    
    context = {
        'produto': produto,
        'loja_selecionada': loja_selecionada,
        'estoques_lojas': estoques_lojas,
        'vendas': vendas,
        'estatisticas': estatisticas,
        'grafico_meses': grafico_meses,
        'grafico_vendas': grafico_vendas,
    }
    
    return render(request, 'estoque/detalhe_produto_loja.html', context)

@login_required
def criar_entrada_estoque(request):
    """Cria uma entrada de estoque para um produto"""
    if request.method == 'POST':
        try:
            produto_id = request.POST.get('produto_id')
            loja_id = request.POST.get('loja_id')
            quantidade = int(request.POST.get('quantidade', 1))
            motivo = request.POST.get('motivo', 'Entrada manual')
            custo_unitario = Decimal(request.POST.get('custo_unitario', '0'))
            
            produto = Produto.objects.get(id=produto_id)
            loja = Loja.objects.get(id=loja_id)
            
            # Verificar permissão
            if not request.user.is_superuser and loja not in request.user.lojas_gerenciadas.all():
                messages.error(request, 'Você não tem permissão para adicionar estoque nesta loja.')
                return redirect('detalhe_produto_loja', produto_id=produto_id)
            
            # Buscar ou criar estoque
            estoque, created = EstoqueLoja.objects.get_or_create(
                loja=loja,
                produto=produto,
                defaults={'quantidade': 0}
            )
            
            # Atualizar estoque
            estoque.quantidade += quantidade
            estoque.save()
            
            # Registrar movimento se o modelo existir
            try:
                from .models import MovimentoEstoque
                MovimentoEstoque.registrar_entrada(
                    produto=produto,
                    loja=loja,
                    quantidade=quantidade,
                    custo_unitario=custo_unitario,
                    preco_venda_unitario=produto.preco,
                    motivo_tipo='compra',
                    motivo_detalhado=motivo,
                    criado_por=request.user
                )
            except:
                # Se não houver modelo MovimentoEstoque, apenas registrar no log
                pass
            
            messages.success(request, f'Entrada de {quantidade} unidades registrada com sucesso!')
            
        except Exception as e:
            messages.error(request, f'Erro ao registrar entrada: {str(e)}')
        
        return redirect('detalhe_produto_loja', produto_id=produto_id, loja_id=loja_id)
    
    return redirect('listar_produtos_estoque')

@login_required
def criar_saida_estoque(request):
    """Cria uma saída de estoque (venda) para um produto"""
    if request.method == 'POST':
        try:
            produto_id = request.POST.get('produto_id')
            loja_id = request.POST.get('loja_id')
            quantidade = int(request.POST.get('quantidade', 1))
            motivo = request.POST.get('motivo', 'Venda')
            vendedor_id = request.POST.get('vendedor_id', request.user.id)
            
            produto = Produto.objects.get(id=produto_id)
            loja = Loja.objects.get(id=loja_id)
            
            # Verificar permissão
            if not request.user.is_superuser and loja not in request.user.lojas_gerenciadas.all():
                messages.error(request, 'Você não tem permissão para registrar venda nesta loja.')
                return redirect('detalhe_produto_loja', produto_id=produto_id)
            
            # Buscar estoque
            try:
                estoque = EstoqueLoja.objects.get(loja=loja, produto=produto)
            except EstoqueLoja.DoesNotExist:
                messages.error(request, 'Produto não encontrado no estoque desta loja.')
                return redirect('detalhe_produto_loja', produto_id=produto_id, loja_id=loja_id)
            
            # Verificar estoque suficiente
            if estoque.quantidade < quantidade:
                messages.error(request, f'Estoque insuficiente. Disponível: {estoque.quantidade}')
                return redirect('detalhe_produto_loja', produto_id=produto_id, loja_id=loja_id)
            
            # Criar venda
            venda = Venda.objects.create(
                estoque_loja=estoque,
                item_type='produto',
                quantidade=quantidade,
                valor_total=quantidade * produto.preco,
                vendedor_id=vendedor_id,
                observacao=motivo
            )
            
            # Atualizar estoque
            estoque.quantidade -= quantidade
            estoque.save()
            
            messages.success(request, f'Saída de {quantidade} unidades registrada com sucesso! Venda #{venda.id}')
            
        except Exception as e:
            messages.error(request, f'Erro ao registrar saída: {str(e)}')
        
        return redirect('detalhe_produto_loja', produto_id=produto_id, loja_id=loja_id)
    
    return redirect('listar_produtos_estoque')

@login_required
def exportar_estoque(request):
    """Exporta o estoque para CSV"""
    # Filtros
    loja_id = request.GET.get('loja', '')
    tipo = request.GET.get('tipo', 'produtos')
    
    # Response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="estoque_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    writer = csv.writer(response)
    
    if tipo == 'produtos':
        writer.writerow(['Produto', 'Código', 'Preço', 'Loja', 'Quantidade', 'Valor Estoque', 'Status'])
        
        produtos = Produto.objects.all()
        lojas = Loja.objects.all()
        
        if loja_id:
            lojas = lojas.filter(id=loja_id)
        
        for produto in produtos:
            for loja in lojas:
                try:
                    estoque = EstoqueLoja.objects.get(loja=loja, produto=produto)
                    quantidade = estoque.quantidade
                    status = estoque.status_estoque
                except EstoqueLoja.DoesNotExist:
                    quantidade = 0
                    status = 'esgotado'
                
                valor_estoque = quantidade * produto.preco
                
                writer.writerow([
                    produto.nome,
                    f'PROD{produto.id:04d}',
                    f'{produto.preco:.2f}',
                    loja.nome,
                    quantidade,
                    f'{valor_estoque:.2f}',
                    status
                ])
    else:
        writer.writerow(['Recarga', 'Código', 'Preço', 'Loja', 'Quantidade', 'Valor Estoque', 'Status'])
        
        recargas = Recarga.objects.all()
        lojas = Loja.objects.all()
        
        if loja_id:
            lojas = lojas.filter(id=loja_id)
        
        for recarga in recargas:
            for loja in lojas:
                try:
                    estoque = EstoqueRecarga.objects.get(loja=loja, recarga=recarga)
                    quantidade = estoque.quantidade
                    status = estoque.status_estoque
                except EstoqueRecarga.DoesNotExist:
                    quantidade = 0
                    status = 'esgotado'
                
                valor_estoque = quantidade * recarga.preco
                
                writer.writerow([
                    recarga.nome,
                    f'REC{recarga.id:04d}',
                    f'{recarga.preco:.2f}',
                    loja.nome,
                    quantidade,
                    f'{valor_estoque:.2f}',
                    status
                ])
    
    return response