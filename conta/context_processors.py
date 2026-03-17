# conta/context_processors.py
from relatorio.models import RelatorioDiario  # ou onde está seu modelo

def estatisticas_relatorios(request):
    """Context processor para disponibilizar estatísticas de relatórios"""
    if not request.user.is_authenticated:
        return {
            'estatisticas': {
                'total_relatorios': 0,
                'completos': 0,
                'pendentes': 0,
                'negativos': 0,
            }
        }
    
    # Lógica similar à da view lista_relatorios
    if request.user.is_superuser:
        relatorios = RelatorioDiario.objects.all()
    else:
        lojas_usuario = request.user.lojas_gerenciadas.all()
        relatorios = RelatorioDiario.objects.filter(loja__in=lojas_usuario)
    
    # Calcular estatísticas
    total_relatorios = relatorios.count()
    completos = 0
    negativos = 0
    pendentes = 0
    
    for relatorio in relatorios:
        try:
            diferenca = relatorio.calcular_diferenca()
            if diferenca > 0:
                completos += 1
            elif diferenca < 0:
                negativos += 1
            else:
                pendentes += 1
        except Exception:
            continue
    
    return {
        'estatisticas': {
            'total_relatorios': total_relatorios,
            'completos': completos,
            'pendentes': pendentes,
            'negativos': negativos,
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