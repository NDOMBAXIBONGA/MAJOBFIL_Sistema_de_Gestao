import os
from django.core.management.base import BaseCommand
from django.utils import timezone
from faturacao.models import MotivoIsencaoIVA, SerieFiscal, ConfiguracaoEmpresa, ClienteFiscal
from faturacao.security import AssinadorFiscalAGT


class Command(BaseCommand):
    help = 'Inicializa os dados fiscais essenciais da AGT (Motivos de Isenção, Séries Fiscais, Chaves RSA e Configurações)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("=== Inicializando Módulo Fiscal AGT (Angola) ==="))
        
        # 1. Configuração da Empresa
        config = ConfiguracaoEmpresa.get_solo()
        self.stdout.write(self.style.SUCCESS(f"Configuração da Empresa pronta: {config.razao_social} (NIF: {config.nif})"))
        
        # 2. Geração de Chaves Criptográficas RSA se não existirem
        priv_path = config.chave_privada_path
        pub_path = config.chave_publica_path
        if not os.path.exists(priv_path) or not os.path.exists(pub_path):
            self.stdout.write("Gerando par de chaves criptográficas RSA de 2048 bits para assinatura fiscal...")
            AssinadorFiscalAGT.gerar_par_chaves_rsa(priv_path, pub_path, tamanho_bits=2048)
            self.stdout.write(self.style.SUCCESS(f"Chaves criadas com sucesso em: {priv_path} e {pub_path}"))
        else:
            self.stdout.write(self.style.SUCCESS("Par de chaves RSA já existente."))

        # 3. Tabela de Motivos de Isenção da AGT
        motivos = [
            ('M00', 'Regime transitório', 'Operações efetuadas durante período transitório legal.'),
            ('M02', 'Transmissão de bens e serviço não sujeita', 'Operações fora do campo de incidência do IVA.'),
            ('M04', 'Isenção nos termos da alínea a) do n.º 1 do artigo 12.º do CIVA', 'Regime de Exclusão (contribuintes com volume de faturação anual reduzido).'),
            ('M10', 'Isenção nos termos da alínea b) do artigo 12.º do CIVA', 'Produtos da Cesta Básica (arroz, óleo alimentar, leite, farinhas, açúcar, etc.).'),
            ('M11', 'Isenção nos termos do artigo 12.º do CIVA', 'Medicamentos, material sanitário e serviços médicos/hospitalares essenciais.'),
            ('M12', 'Isenção nos termos do artigo 13.º do CIVA', 'Livros escolares, material didático e publicações científicas.'),
            ('M14', 'Isenção nos termos do artigo 14.º do CIVA', 'Locação e operações de bens imóveis isentas.'),
            ('M15', 'Isenção nos termos do artigo 15.º do CIVA', 'Serviços financeiros e bancários.'),
            ('M16', 'Isenção nos termos do artigo 16.º do CIVA', 'Operações de exportação de mercadorias.'),
            ('M99', 'Outras isenções', 'Outras isenções com enquadramento legal específico.'),
        ]
        
        criados = 0
        for cod, mencao, desc in motivos:
            _, created = MotivoIsencaoIVA.objects.get_or_create(
                codigo=cod,
                defaults={'mencao_legal': mencao, 'descricao': desc, 'ativo': True}
            )
            if created:
                criados += 1
        self.stdout.write(self.style.SUCCESS(f"Motivos de Isenção da AGT sincronizados ({criados} novos criados)."))

        # 4. Séries Fiscais do Ano Vigente
        ano_atual = timezone.now().year
        series_iniciais = [
            ('A', 'FT', 'Fatura'),
            ('A', 'FR', 'Fatura-Recibo'),
            ('A', 'NC', 'Nota de Crédito'),
            ('A', 'ND', 'Nota de Débito'),
        ]
        
        series_criadas = 0
        for serie_cod, tipo_doc, nome in series_iniciais:
            _, created = SerieFiscal.objects.get_or_create(
                serie=serie_cod,
                tipo_documento=tipo_doc,
                ano=ano_atual,
                defaults={'ativa': True, 'ultimo_numero': 0, 'ultimo_hash': ''}
            )
            if created:
                series_criadas += 1
        self.stdout.write(self.style.SUCCESS(f"Séries Fiscais para o ano {ano_atual} preparadas ({series_criadas} novas criadas)."))

        # 5. Cliente Consumidor Final Padrão
        cliente_cf, created = ClienteFiscal.objects.get_or_create(
            nif='999999999',
            defaults={
                'nome_razao_social': 'Consumidor Final',
                'regime_iva': 'GERAL',
                'endereco': 'Luanda, Angola',
                'cidade': 'Luanda',
                'provincia': 'Luanda'
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS("Cliente padrão 'Consumidor Final' (NIF 999999999) criado com sucesso."))

        self.stdout.write(self.style.SUCCESS("=== Módulo Fiscal AGT pronto para operação e certificação! ==="))
