# conta/utils.py
from .models import Atividade

def registrar_atividade(usuario, descricao):
    """Função simples para registrar qualquer atividade"""
    return Atividade.objects.create(usuario=usuario, descricao=descricao)