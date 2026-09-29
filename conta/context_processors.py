# conta/context_processors.py
from django.db.models import Count, Case, When, IntegerField, F, Q
from relatorio.models import RelatorioDiario

def estatisticas_relatorios(request):
    """Context processor otimizado para disponibilizar estatísticas de relatórios via SQL direto"""
    if not request.user.is_authenticated:
        return {
            'estatisticas': {
                'total_relatorios': 0,
                'completos': 0,
                'pendentes': 0,
                'negativos': 0,
            }
        }
    
    if request.user.is_superuser:
        relatorios = RelatorioDiario.objects.all()
    else:
        lojas_usuario = request.user.lojas_gerenciadas.all()
        relatorios = RelatorioDiario.objects.filter(loja__in=lojas_usuario)
    
    # Condição para campos obrigatórios zerados ou nulos (Pendente)
    campos_zerados = (
        Q(tpa=0) | Q(tpa__isnull=True) |
        Q(dstv=0) | Q(dstv__isnull=True) |
        Q(zap=0) | Q(zap__isnull=True) |
        Q(unitel=0) | Q(unitel__isnull=True) |
        Q(africell=0) | Q(africell__isnull=True) |
        Q(recargas=0) | Q(recargas__isnull=True) |
        Q(acc=0) | Q(acc__isnull=True) |
        Q(dm=0) | Q(dm__isnull=True) |
        Q(moedas=0) | Q(moedas__isnull=True) |
        Q(gastos=0) | Q(gastos__isnull=True)
    )
    
    total_arrecadado_expr = F('dm') + F('moedas') + F('tpa') + F('gastos')
    
    stats = relatorios.aggregate(
        total=Count('id'),
        pendentes=Count(Case(When(campos_zerados, then=1), output_field=IntegerField())),
        completos=Count(Case(When(~campos_zerados & Q(total_geral__lte=total_arrecadado_expr), then=1), output_field=IntegerField())),
        negativos=Count(Case(When(~campos_zerados & Q(total_geral__gt=total_arrecadado_expr), then=1), output_field=IntegerField())),
    )
    
    return {
        'estatisticas': {
            'total_relatorios': stats['total'] or 0,
            'completos': stats['completos'] or 0,
            'pendentes': stats['pendentes'] or 0,
            'negativos': stats['negativos'] or 0,
        }
    }

# conta/context_processors.py
from .models import Atividade

def atividades_recentes_context(request):
    """Pega apenas as 5 atividades mais recentes do usuário"""
    if not request.user.is_authenticated:
        return {'atividades_recentes': []}
    
    atividades = Atividade.objects.filter(
        usuario=request.user
    ).order_by('-data')[:5]
    
    return {'atividades_recentes': atividades}