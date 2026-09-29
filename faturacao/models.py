import re
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone


def validar_nif_angolano(nif: str):
    """
    Validação de NIF em conformidade com as regras fiscais de Angola (AGT):
    - Pessoas Coletivas (Empresas): 10 dígitos numéricos (ex: 5412345678)
    - Pessoas Singulares: Formato do Bilhete de Identidade (9 dígitos + 2 letras + 3 dígitos = 14 caracteres)
      ou número de identificação fiscal atribuído com 10 dígitos.
    - Consumidor Final genérico: 999999999
    """
    if not nif:
        raise ValidationError("O NIF é obrigatório.")
    
    nif_limpo = re.sub(r'[^a-zA-Z0-9]', '', str(nif)).strip().upper()
    
    if nif_limpo in ('999999999', 'CONSUMIDORFINAL'):
        return
    
    # 10 dígitos numéricos
    padrao_empresa = r'^\d{10}$'
    # 9 dígitos + 2 letras + 3 dígitos (BI Angolano)
    padrao_singular_bi = r'^\d{9}[A-Z]{2}\d{3}$'
    
    if not (re.match(padrao_empresa, nif_limpo) or re.match(padrao_singular_bi, nif_limpo)):
        raise ValidationError(
            f"O NIF '{nif}' é inválido para a jurisdição fiscal de Angola. "
            "Deve conter 10 dígitos numéricos (Empresas) ou formato BI de 14 caracteres (Singulares)."
        )


class ConfiguracaoEmpresa(models.Model):
    """Configurações fiscais da entidade emitente (MAJOBFIL)"""
    REGIMES_IVA = [
        ('GERAL', 'Regime Geral'),
        ('SIMPLIFICADO', 'Regime Simplificado'),
        ('EXCLUSAO', 'Regime de Exclusão'),
    ]
    
    razao_social = models.CharField('Razão Social', max_length=200, default='MAJOBFIL COMÉRCIO E SERVIÇOS, LDA')
    nome_comercial = models.CharField('Nome Comercial', max_length=200, default='MAJOBFIL')
    nif = models.CharField('NIF do Emitente', max_length=20, default='5412345678', validators=[validar_nif_angolano])
    regime_iva = models.CharField('Regime de IVA', max_length=15, choices=REGIMES_IVA, default='GERAL')
    endereco = models.CharField('Endereço', max_length=255, default='Luanda, Angola')
    cidade = models.CharField('Cidade', max_length=100, default='Luanda')
    provincia = models.CharField('Província', max_length=50, default='Luanda')
    pais = models.CharField('País', max_length=2, default='AO')
    telefone = models.CharField('Telefone', max_length=50, default='+244 923 000 000')
    email = models.EmailField('Email', default='contato@majobfil.ao')
    
    # Certificação AGT
    numero_certificado_agt = models.CharField('N.º Certificado do Software AGT', max_length=50, default='000/AGT/2026')
    nif_produtor_software = models.CharField('NIF do Produtor de Software', max_length=20, default='5412345678')
    nome_software = models.CharField('Nome do Software', max_length=100, default='MAJOBFIL ERP/POS')
    versao_software = models.CharField('Versão do Software', max_length=20, default='1.0.0')
    
    # Certificados Criptográficos
    chave_privada_path = models.CharField('Caminho da Chave Privada PEM', max_length=255, default='certs/chave_privada_agt.pem')
    chave_publica_path = models.CharField('Caminho da Chave Pública PEM', max_length=255, default='certs/chave_publica_agt.pem')
    versao_chave = models.PositiveIntegerField('Versão da Chave', default=1)

    class Meta:
        verbose_name = 'Configuração da Empresa (AGT)'
        verbose_name_plural = 'Configurações da Empresa (AGT)'

    def __str__(self):
        return f"{self.razao_social} ({self.nif})"

    @classmethod
    def get_solo(cls):
        """Retorna a configuração existente ou cria a padrão"""
        obj = cls.objects.first()
        if not obj:
            obj = cls.objects.create()
        return obj


class SerieFiscal(models.Model):
    TIPO_DOC = [
        ('FT', 'Fatura'),
        ('FR', 'Fatura-Recibo'),
        ('NC', 'Nota de Crédito'),
        ('ND', 'Nota de Débito'),
    ]
    
    serie = models.CharField('Série', max_length=10) # Ex: 'A', '2026A', 'POS1'
    tipo_documento = models.CharField('Tipo de Documento', max_length=2, choices=TIPO_DOC)
    ano = models.PositiveIntegerField('Ano Fiscal', default=timezone.now().year)
    ultimo_numero = models.PositiveIntegerField('Último Número Emitido', default=0)
    ultimo_hash = models.TextField('Último Hash Emitido (Base64)', blank=True, default='')
    ativa = models.BooleanField('Série Ativa', default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Série Fiscal'
        verbose_name_plural = 'Séries Fiscais'
        unique_together = ['serie', 'tipo_documento', 'ano']
        ordering = ['tipo_documento', 'serie', '-ano']

    def __str__(self):
        return f"{self.get_tipo_documento_display()} {self.serie}/{self.ano} (Último: #{self.ultimo_numero})"


class MotivoIsencaoIVA(models.Model):
    codigo = models.CharField('Código AGT', max_length=5, primary_key=True) # Ex: M00, M02, M04, M10
    mencao_legal = models.CharField('Menção Legal', max_length=255)
    descricao = models.TextField('Descrição Jurídica')
    ativo = models.BooleanField('Ativo', default=True)

    class Meta:
        verbose_name = 'Motivo de Isenção de IVA (AGT)'
        verbose_name_plural = 'Motivos de Isenção de IVA (AGT)'
        ordering = ['codigo']

    def __str__(self):
        return f"{self.codigo} - {self.mencao_legal}"


class ClienteFiscal(models.Model):
    REGIMES_IVA = [
        ('GERAL', 'Regime Geral'),
        ('SIMPLIFICADO', 'Regime Simplificado'),
        ('EXCLUSAO', 'Regime de Exclusão'),
    ]
    
    nome_razao_social = models.CharField('Nome / Razão Social', max_length=200)
    nif = models.CharField('NIF', max_length=20, validators=[validar_nif_angolano], db_index=True)
    regime_iva = models.CharField('Regime de IVA', max_length=15, choices=REGIMES_IVA, default='GERAL')
    email = models.EmailField('Email', blank=True, null=True)
    telefone = models.CharField('Telefone', max_length=50, blank=True, null=True)
    endereco = models.CharField('Endereço', max_length=255, default='Luanda, Angola')
    cidade = models.CharField('Cidade', max_length=100, default='Luanda')
    provincia = models.CharField('Província', max_length=50, default='Luanda')
    pais = models.CharField('País', max_length=2, default='AO')
    ativo = models.BooleanField('Ativo', default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Cliente Fiscal'
        verbose_name_plural = 'Clientes Fiscais'
        ordering = ['nome_razao_social']

    def __str__(self):
        return f"{self.nome_razao_social} ({self.nif})"


class Fatura(models.Model):
    STATUS_CHOICES = [
        ('N', 'Normal'),
        ('A', 'Anulada'),
        ('R', 'Retificada'),
    ]
    
    # Identificação Única Exigida pela AGT (ex: "FT 2026A/1")
    serie_fiscal = models.ForeignKey(SerieFiscal, on_delete=models.PROTECT, related_name='faturas')
    numero_sequencial = models.PositiveIntegerField('Número Sequencial')
    numero_fatura = models.CharField('Número da Fatura', max_length=50, unique=True, db_index=True)
    
    status = models.CharField('Estado', max_length=1, choices=STATUS_CHOICES, default='N')
    data_emissao = models.DateField('Data de Emissão', default=timezone.now)
    system_entry_date = models.DateTimeField('Data/Hora de Gravação no Sistema', default=timezone.now)
    data_vencimento = models.DateField('Data de Vencimento', blank=True, null=True)
    
    # Snapshot dos Dados do Emitente
    emitente_nome = models.CharField('Razão Social Emitente', max_length=200)
    emitente_nif = models.CharField('NIF Emitente', max_length=20)
    emitente_endereco = models.CharField('Endereço Emitente', max_length=255)
    emitente_regime_iva = models.CharField('Regime IVA Emitente', max_length=20)
    
    # Snapshot dos Dados do Adquirente
    cliente = models.ForeignKey(ClienteFiscal, on_delete=models.PROTECT, related_name='faturas')
    cliente_nome = models.CharField('Razão Social Cliente', max_length=200)
    cliente_nif = models.CharField('NIF Cliente', max_length=20)
    cliente_endereco = models.CharField('Endereço Cliente', max_length=255)
    
    # Totais Fiscais
    total_incidencia = models.DecimalField('Total de Incidência Líquida', max_digits=15, decimal_places=2, default=0)
    total_iva = models.DecimalField('Total de IVA Liquidado', max_digits=15, decimal_places=2, default=0)
    total_descontos = models.DecimalField('Total de Descontos', max_digits=15, decimal_places=2, default=0)
    total_retencao_fonte = models.DecimalField('Retenção na Fonte', max_digits=15, decimal_places=2, default=0)
    total_bruto = models.DecimalField('Total Bruto / A Pagar', max_digits=15, decimal_places=2, default=0)
    
    # Assinatura Criptográfica Fiscal (AGT)
    hash_anterior = models.TextField('Hash da Fatura Anterior', blank=True)
    dados_para_hash = models.TextField('String de Entrada da Assinatura')
    hash_assinatura = models.TextField('Assinatura Digital RSA-SHA1 (Base64)')
    hash_curto = models.CharField('Hash de 4 Caracteres (Exibição)', max_length=150)
    versao_chave = models.PositiveIntegerField('Versão da Chave Pública AGT', default=1)
    
    operador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name='Operador')
    observacoes = models.TextField('Observações', blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Fatura Fiscal'
        verbose_name_plural = 'Faturas Fiscais'
        ordering = ['-system_entry_date']
        indexes = [
            models.Index(fields=['numero_fatura']),
            models.Index(fields=['data_emissao']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.numero_fatura} - {self.cliente_nome} ({self.total_bruto} Kz)"


class ItemFatura(models.Model):
    TIPO_TAXA_IVA = [
        ('NOR', 'Normal (14%)'),
        ('RED', 'Reduzida (7% ou 5%)'),
        ('INT', 'Intermédia'),
        ('ISE', 'Isenta (0%)'),
        ('OUT', 'Outros'),
    ]
    
    fatura = models.ForeignKey(Fatura, on_delete=models.CASCADE, related_name='itens')
    numero_linha = models.PositiveIntegerField('N.º da Linha')
    codigo_produto = models.CharField('Código do Artigo', max_length=50)
    descricao = models.CharField('Descrição do Produto/Serviço', max_length=200)
    
    quantidade = models.DecimalField('Quantidade', max_digits=12, decimal_places=3)
    preco_unitario = models.DecimalField('Preço Unitário (s/ IVA)', max_digits=15, decimal_places=2)
    desconto_linha = models.DecimalField('Desconto Comercial', max_digits=15, decimal_places=2, default=0)
    
    tipo_taxa_iva = models.CharField('Código Taxa', max_length=3, choices=TIPO_TAXA_IVA, default='NOR')
    taxa_iva = models.DecimalField('Taxa de IVA (%)', max_digits=5, decimal_places=2, default=Decimal('14.00'))
    valor_iva = models.DecimalField('Montante do IVA', max_digits=15, decimal_places=2, default=0)
    
    motivo_isencao = models.ForeignKey(
        MotivoIsencaoIVA,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name='Motivo de Isenção (Obrigatório se IVA=0)'
    )
    
    subtotal_liquido = models.DecimalField('Subtotal s/ IVA', max_digits=15, decimal_places=2)
    total_linha = models.DecimalField('Total c/ IVA', max_digits=15, decimal_places=2)

    class Meta:
        verbose_name = 'Item da Fatura'
        verbose_name_plural = 'Itens da Fatura'
        unique_together = ['fatura', 'numero_linha']
        ordering = ['fatura', 'numero_linha']

    def clean(self):
        # Validação Fiscal Estrita da AGT: se taxa de IVA for 0%, motivo de isenção é obrigatório!
        if self.taxa_iva == Decimal('0.00') and not self.motivo_isencao:
            raise ValidationError(
                f"Artigo '{self.descricao}' está configurado com taxa de IVA de 0%, "
                "sendo obrigatório indicar o respetivo Código de Motivo de Isenção da AGT."
            )
        if self.taxa_iva > Decimal('0.00') and self.motivo_isencao:
            raise ValidationError(
                f"Artigo '{self.descricao}' possui taxa de IVA positiva ({self.taxa_iva}%). "
                "Não pode conter Motivo de Isenção."
            )
