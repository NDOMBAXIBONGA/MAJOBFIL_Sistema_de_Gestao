from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.db.models import Sum, Q
from datetime import datetime, timedelta

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('O email é obrigatório')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)

class Conta(AbstractBaseUser, PermissionsMixin):
    username = models.CharField('Nome de usuário', max_length=30, unique=True)
    email = models.EmailField('Email', unique=True)
    nome = models.CharField('Nome completo', max_length=100)
    telemovel = models.CharField('Telemóvel', max_length=15, blank=True, null=True)
    data_nascimento = models.DateField('Data de nascimento', blank=True, null=True)
    bilhete_identidade = models.CharField('Bilhete de Identidade', max_length=20, blank=True, null=True)
    bairro = models.CharField('Bairro', max_length=100, blank=True, null=True)
    cidade = models.CharField('Cidade', max_length=100, blank=True, null=True)
    provincia = models.CharField('Província', max_length=100, blank=True, null=True)
    municipio = models.CharField('Município', max_length=100, blank=True, null=True)
    
    is_active = models.BooleanField('Ativo', default=True)
    is_staff = models.BooleanField('Staff', default=False)
    is_superuser = models.BooleanField('superuser', default=False)
    date_joined = models.DateTimeField('Data de registro', default=timezone.now)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'nome']

    # Métodos para cálculo de vendas
    def total_vendas_usuario(self, data_relatorio=None):
        """
        Calcula o total de vendas realizadas por este usuário
        """
        vendas_query = self.venda_set.all()
        
        if data_relatorio:
            if isinstance(data_relatorio, str):
                data_relatorio = datetime.strptime(data_relatorio, '%Y-%m-%d').date()
            vendas_query = vendas_query.filter(data_venda__date=data_relatorio)
        
        total = vendas_query.aggregate(
            total_vendas=Sum('valor_total')
        )['total_vendas'] or 0
        return total
    
    def total_quantidade_vendida(self, data_relatorio=None):
        """
        Calcula a quantidade total de produtos vendidos por este usuário
        """
        vendas_query = self.venda_set.all()
        
        if data_relatorio:
            if isinstance(data_relatorio, str):
                data_relatorio = datetime.strptime(data_relatorio, '%Y-%m-%d').date()
            vendas_query = vendas_query.filter(data_venda__date=data_relatorio)
        
        total = vendas_query.aggregate(
            total_quantidade=Sum('quantidade')
        )['total_quantidade'] or 0
        return total
    
    def get_vendas_por_periodo(self, data_inicio, data_fim):
        """
        Retorna vendas do usuário por período específico
        """
        return self.venda_set.filter(
            data_venda__date__range=[data_inicio, data_fim]
        )
    
    def vendas_ultimos_30_dias(self):
        """
        Calcula o total de vendas dos últimos 30 dias
        """
        data_inicio = datetime.now().date() - timedelta(days=30)
        data_fim = datetime.now().date()
        vendas = self.get_vendas_por_periodo(data_inicio, data_fim)
        total = vendas.aggregate(total=Sum('valor_total'))['total'] or 0
        return total
    
    def quantidade_ultimos_30_dias(self):
        """
        Calcula a quantidade vendida nos últimos 30 dias
        """
        data_inicio = datetime.now().date() - timedelta(days=30)
        data_fim = datetime.now().date()
        vendas = self.get_vendas_por_periodo(data_inicio, data_fim)
        total = vendas.aggregate(total=Sum('quantidade'))['total'] or 0
        return total
    
    def lojas_gerenciadas_list(self):
        """
        Retorna lista de lojas gerenciadas pelo usuário
        """
        lojas = self.lojas_gerenciadas.all()
        if lojas:
            return ", ".join([loja.nome for loja in lojas[:3]]) + ("..." if lojas.count() > 3 else "")
        return "Nenhuma"
    
    def numero_vendas_realizadas(self, data_relatorio=None):
        """
        Retorna o número total de vendas realizadas pelo usuário
        """
        vendas_query = self.venda_set.all()
        
        if data_relatorio:
            if isinstance(data_relatorio, str):
                data_relatorio = datetime.strptime(data_relatorio, '%Y-%m-%d').date()
            vendas_query = vendas_query.filter(data_venda__date=data_relatorio)
        
        return vendas_query.count()

    class Meta:
        verbose_name = 'Conta'
        verbose_name_plural = 'Contas'

    def __str__(self):
        return self.email

    def get_full_name(self):
        return self.nome

    def get_short_name(self):
        return self.nome.split()[0] if self.nome else self.username


# conta/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class Atividade(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='atividades')
    descricao = models.CharField(max_length=200)
    data = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-data']
    
    def __str__(self):
        return f"{self.usuario.username}: {self.descricao}"
    
    def tempo_atras(self):
        """Retorna tempo em formato amigável"""
        from datetime import datetime
        now = datetime.now(timezone.utc)
        diff = now - self.data
        
        if diff.days > 0:
            return f"{diff.days} dia{'s' if diff.days > 1 else ''} atrás"
        elif diff.seconds >= 3600:
            horas = diff.seconds // 3600
            return f"{horas} hora{'s' if horas > 1 else ''} atrás"
        elif diff.seconds >= 60:
            minutos = diff.seconds // 60
            return f"{minutos} minuto{'s' if minutos > 1 else ''} atrás"
        return "Agora mesmo"