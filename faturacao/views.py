import json
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator
from django.utils import timezone
from .models import Fatura, SerieFiscal, ClienteFiscal, MotivoIsencaoIVA, ConfiguracaoEmpresa, validar_nif_angolano
from .services import ServicoFaturacaoAGT
from .saft import GeradorSaftAO


@login_required
def lista_faturas(request):
    """Lista todas as faturas fiscais emitidas com filtros e paginação"""
    query = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', '').strip()
    status = request.GET.get('status', '').strip()
    
    faturas = Fatura.objects.all().select_related('cliente', 'serie_fiscal', 'operador')
    
    if query:
        faturas = faturas.filter(
            numero_fatura__icontains=query
        ) | faturas.filter(
            cliente_nome__icontains=query
        ) | faturas.filter(
            cliente_nif__icontains=query
        )
        
    if tipo:
        faturas = faturas.filter(serie_fiscal__tipo_documento=tipo)
        
    if status:
        faturas = faturas.filter(status=status)
        
    paginator = Paginator(faturas, 15)
    page_number = request.GET.get('page', 1)
    faturas_paginadas = paginator.get_page(page_number)
    
    # Totais gerais
    totais = {
        'total_faturas': faturas.count(),
        'valor_total': sum(f.total_bruto for f in faturas[:100]),
    }
    
    context = {
        'faturas': faturas_paginadas,
        'query': query,
        'tipo': tipo,
        'status': status,
        'totais': totais,
        'tipos_documento': SerieFiscal.TIPO_DOC,
    }
    return render(request, 'faturacao/lista_faturas.html', context)


@login_required
def detalhe_fatura(request, fatura_id):
    """Visualização e impressão fiscal formatada da Fatura (A4 e Térmico)"""
    fatura = get_object_or_404(
        Fatura.objects.select_related('cliente', 'serie_fiscal', 'operador').prefetch_related('itens', 'itens__motivo_isencao'),
        id=fatura_id
    )
    config = ConfiguracaoEmpresa.get_solo()
    
    # Agrupamento de impostos para o rodapé fiscal
    resumo_iva = {}
    for item in fatura.itens.all():
        taxa = item.taxa_iva
        if taxa not in resumo_iva:
            resumo_iva[taxa] = {
                'taxa': taxa,
                'incidencia': Decimal('0.00'),
                'montante_iva': Decimal('0.00'),
                'tipo_taxa': item.tipo_taxa_iva,
                'motivo': item.motivo_isencao.mencao_legal if item.motivo_isencao else ''
            }
        resumo_iva[taxa]['incidencia'] += item.subtotal_liquido
        resumo_iva[taxa]['montante_iva'] += item.valor_iva

    context = {
        'fatura': fatura,
        'config': config,
        'resumo_iva': list(resumo_iva.values()),
    }
    return render(request, 'faturacao/detalhe_fatura.html', context)


@login_required
def emitir_fatura_view(request):
    """Interface para emissão de nova fatura fiscal"""
    ano_atual = timezone.now().year
    series_disponiveis = SerieFiscal.objects.filter(ano=ano_atual, ativa=True)
    clientes = ClienteFiscal.objects.filter(ativo=True).order_by('nome_razao_social')
    motivos_isencao = MotivoIsencaoIVA.objects.filter(ativo=True).order_by('codigo')
    
    if request.method == 'POST':
        try:
            serie_id = request.POST.get('serie_id')
            cliente_id = request.POST.get('cliente_id')
            observacoes = request.POST.get('observacoes', '')
            
            # Novo cliente criado inline se NIF novo fornecido
            novo_cliente_nif = request.POST.get('novo_cliente_nif', '').strip()
            if novo_cliente_nif:
                novo_nome = request.POST.get('novo_cliente_nome', 'Cliente').strip()
                validar_nif_angolano(novo_cliente_nif)
                cliente, _ = ClienteFiscal.objects.get_or_create(
                    nif=novo_cliente_nif,
                    defaults={'nome_razao_social': novo_nome}
                )
                cliente_id = cliente.id

            # Parse dos itens enviados via form
            itens_json = request.POST.get('itens_json', '[]')
            itens_dados = json.loads(itens_json)
            
            if not itens_dados:
                messages.error(request, "Adicione pelo menos um item à fatura.")
                return redirect('emitir_fatura')

            servico = ServicoFaturacaoAGT()
            fatura = servico.emitir_fatura(
                serie_id=int(serie_id),
                cliente_id=int(cliente_id),
                operador=request.user,
                itens_dados=itens_dados,
                observacoes=observacoes
            )
            
            messages.success(request, f"Fatura fiscal {fatura.numero_fatura} emitida e assinada digitalmente com sucesso!")
            return redirect('detalhe_fatura', fatura_id=fatura.id)
            
        except Exception as e:
            messages.error(request, f"Erro ao emitir fatura: {str(e)}")

    context = {
        'series': series_disponiveis,
        'clientes': clientes,
        'motivos_isencao': motivos_isencao,
        'hoje': timezone.now().date(),
    }
    return render(request, 'faturacao/emitir_fatura.html', context)


@login_required
def exportar_saft_view(request):
    """Gera e faz download do ficheiro XML SAF-T (AO) mensal"""
    ano_atual = timezone.now().year
    mes_atual = timezone.now().month
    
    if request.method == 'POST':
        ano = int(request.POST.get('ano', ano_atual))
        mes = int(request.POST.get('mes', mes_atual))
        
        try:
            gerador = GeradorSaftAO(ano=ano, mes=mes)
            xml_content = gerador.gerar_xml()
            
            nome_arquivo = f"SAF-T_AO_{ano}_{mes:02d}.xml"
            response = HttpResponse(xml_content, content_type='application/xml')
            response['Content-Disposition'] = f'attachment; filename="{nome_arquivo}"'
            return response
        except Exception as e:
            messages.error(request, f"Erro ao gerar SAF-T (AO): {str(e)}")
            
    context = {
        'ano_atual': ano_atual,
        'mes_atual': mes_atual,
        'anos': range(ano_atual - 3, ano_atual + 2),
        'meses': [
            (1, 'Janeiro'), (2, 'Fevereiro'), (3, 'Março'), (4, 'Abril'),
            (5, 'Maio'), (6, 'Junho'), (7, 'Julho'), (8, 'Agosto'),
            (9, 'Setembro'), (10, 'Outubro'), (11, 'Novembro'), (12, 'Dezembro')
        ]
    }
    return render(request, 'faturacao/exportar_saft.html', context)


@login_required
def api_validar_nif(request):
    """API JSON para validação assíncrona de NIF no frontend"""
    nif = request.GET.get('nif', '').strip()
    try:
        validar_nif_angolano(nif)
        cliente = ClienteFiscal.objects.filter(nif=nif).first()
        return JsonResponse({
            'valido': True,
            'existe': cliente is not None,
            'nome': cliente.nome_razao_social if cliente else ''
        })
    except Exception as e:
        return JsonResponse({'valido': False, 'erro': str(e)})


@login_required
def faturar_venda_view(request, venda_id):
    """Converte uma venda existente do PDV em Fatura-Recibo (FR) ou Fatura (FT) certificada pela AGT"""
    from lojas.models import Venda
    venda = get_object_or_404(Venda, id=venda_id)
    
    # Verificar se já existe fatura emitida para esta venda
    fatura_existente = Fatura.objects.filter(observacoes__contains=f"Venda PDV #{venda.id}").first()
    if fatura_existente:
        messages.info(request, f"Esta venda já possui a fatura fiscal {fatura_existente.numero_fatura} associada.")
        return redirect('detalhe_fatura', fatura_id=fatura_existente.id)
        
    tipo_doc = request.GET.get('tipo', 'FR')  # Padrão FR (Fatura-Recibo) para vendas de balcão
    cliente_fiscal = ClienteFiscal.objects.filter(nif='999999999').first()
    if not cliente_fiscal:
        cliente_fiscal = ClienteFiscal.objects.create(
            nome_razao_social='Consumidor Final',
            nif='999999999',
            regime_iva='EXCLUSAO'
        )
        
    try:
        servico = ServicoFaturacaoAGT()
        fatura = servico.faturar_venda_pos(
            venda=venda,
            tipo_documento=tipo_doc,
            cliente_fiscal=cliente_fiscal,
            emitido_por=request.user
        )
        messages.success(request, f"Fatura fiscal {fatura.numero_fatura} gerada e assinada com sucesso para a venda #{venda.id}!")
        return redirect('detalhe_fatura', fatura_id=fatura.id)
    except Exception as e:
        messages.error(request, f"Erro ao faturar venda fiscalmente: {str(e)}")
        return redirect('detalhes_venda', venda_id=venda.id)

