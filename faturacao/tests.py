from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from conta.models import Conta
from faturacao.models import (
    ConfiguracaoEmpresa, SerieFiscal, ClienteFiscal, 
    MotivoIsencaoIVA, Fatura, ItemFatura, validar_nif_angolano
)
from faturacao.security import AssinadorFiscalAGT
from faturacao.services import ServicoFaturacaoAGT
from faturacao.saft import GeradorSaftAO


class FaturacaoAGTTestCase(TestCase):
    def setUp(self):
        # 1. Operador
        self.operador = Conta.objects.create_user(
            email='fiscal_admin@teste.com',
            username='fiscal1',
            nome='Operador Fiscal',
            password='SenhaValida123!@#'
        )

        # 2. Configuração da Empresa
        self.config = ConfiguracaoEmpresa.objects.create(
            razao_social='MAJOBFIL COMÉRCIO, LDA',
            nif='5412345678',
            regime_iva='GERAL',
            chave_privada_path='certs/test_privada.pem',
            chave_publica_path='certs/test_publica.pem',
            numero_certificado_agt='999/AGT/2026'
        )

        # 3. Chaves criptográficas para teste
        AssinadorFiscalAGT.gerar_par_chaves_rsa(
            self.config.chave_privada_path,
            self.config.chave_publica_path,
            tamanho_bits=2048
        )
        self.assinador = AssinadorFiscalAGT(self.config.chave_privada_path)
        self.servico = ServicoFaturacaoAGT(self.assinador)

        # 4. Motivos de Isenção
        self.motivo_m10 = MotivoIsencaoIVA.objects.create(
            codigo='M10',
            mencao_legal='Isenção nos termos do artigo 12.º do CIVA (Cesta Básica)',
            descricao='Cesta básica'
        )

        # 5. Série Fiscal
        self.serie_ft = SerieFiscal.objects.create(
            serie='TEST',
            tipo_documento='FT',
            ano=timezone.now().year,
            ativa=True
        )

        # 6. Cliente
        self.cliente = ClienteFiscal.objects.create(
            nome_razao_social='EMPRESA CLIENTE TESTE, LDA',
            nif='5498765432',
            regime_iva='GERAL',
            endereco='Rua Principal, Luanda'
        )

    def tearDown(self):
        # Limpar chaves temporárias criadas no teste
        import os
        for path in [self.config.chave_privada_path, self.config.chave_publica_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass

    def test_validacao_nif_angolano(self):
        """Testa regras estritas de NIF da AGT (10 dígitos empresa, 14 chars BI, ou 999999999)"""
        # NIFs Válidos
        validar_nif_angolano('5412345678')          # 10 dígitos numéricos
        validar_nif_angolano('004523189LA042')      # 14 chars (BI)
        validar_nif_angolano('999999999')          # Consumidor final
        
        # NIFs Inválidos
        with self.assertRaises(ValidationError):
            validar_nif_angolano('12345')           # Muito curto
        with self.assertRaises(ValidationError):
            validar_nif_angolano('ABCD12345678')    # Formato inválido

    def test_emissao_fatura_com_assinatura_rsa_e_chaining(self):
        """Testa emissão de faturas sequenciais e encadeamento criptográfico do hash anterior"""
        # 1. Primeira Fatura
        itens_1 = [{
            'codigo_produto': 'ART01',
            'descricao': 'Licença de Software',
            'quantidade': 1,
            'preco_unitario': 10000.00,
            'taxa_iva': 14.00
        }]
        
        fatura_1 = self.servico.emitir_fatura(
            serie_id=self.serie_ft.id,
            cliente_id=self.cliente.id,
            operador=self.operador,
            itens_dados=itens_1
        )

        self.assertEqual(fatura_1.numero_sequencial, 1)
        self.assertEqual(fatura_1.numero_fatura, f"FT TEST/{self.serie_ft.ano}/1")
        self.assertEqual(fatura_1.total_incidencia, Decimal('10000.00'))
        self.assertEqual(fatura_1.total_iva, Decimal('1400.00'))
        self.assertEqual(fatura_1.total_bruto, Decimal('11400.00'))
        self.assertEqual(fatura_1.hash_anterior, "") # Primeira fatura tem hash anterior vazio
        self.assertTrue(len(fatura_1.hash_assinatura) > 50)
        self.assertIn("Processado por programa validado", fatura_1.hash_curto)

        # Verificar se a assinatura bate com a chave pública
        valida = self.assinador.verificar_assinatura(
            fatura_1.dados_para_hash,
            fatura_1.hash_assinatura,
            self.config.chave_publica_path
        )
        self.assertTrue(valida)

        # 2. Segunda Fatura na mesma série -> DEVE encadear o hash da primeira!
        itens_2 = [{
            'codigo_produto': 'ART02',
            'descricao': 'Serviço de Consultoria',
            'quantidade': 2,
            'preco_unitario': 5000.00,
            'taxa_iva': 14.00
        }]
        fatura_2 = self.servico.emitir_fatura(
            serie_id=self.serie_ft.id,
            cliente_id=self.cliente.id,
            operador=self.operador,
            itens_dados=itens_2
        )

        self.assertEqual(fatura_2.numero_sequencial, 2)
        # Regra de Ouro AGT: Hash anterior da Fatura 2 é a assinatura da Fatura 1!
        self.assertEqual(fatura_2.hash_anterior, fatura_1.hash_assinatura)
        
        # Verificar estado final da série
        self.serie_ft.refresh_from_db()
        self.assertEqual(self.serie_ft.ultimo_numero, 2)
        self.assertEqual(self.serie_ft.ultimo_hash, fatura_2.hash_assinatura)

    def test_bloqueio_item_isento_sem_motivo_isencao(self):
        """Testa se a emissão com taxa 0% sem motivo de isenção é estritamente rejeitada"""
        itens_sem_motivo = [{
            'codigo_produto': 'ARROZ01',
            'descricao': 'Saco de Arroz 25kg',
            'quantidade': 1,
            'preco_unitario': 15000.00,
            'taxa_iva': 0.00,
            'codigo_isencao': '' # Vazio!
        }]

        with self.assertRaises(ValidationError):
            self.servico.emitir_fatura(
                serie_id=self.serie_ft.id,
                cliente_id=self.cliente.id,
                operador=self.operador,
                itens_dados=itens_sem_motivo
            )

    def test_geracao_saft_ao_xml(self):
        """Testa se o gerador SAF-T AO produz o XML com todos os nós requeridos pela AGT"""
        itens = [{
            'codigo_produto': 'ART-SAFT',
            'descricao': 'Produto Para Teste SAF-T',
            'quantidade': 1,
            'preco_unitario': 5000.00,
            'taxa_iva': 14.00
        }]
        self.servico.emitir_fatura(
            serie_id=self.serie_ft.id,
            cliente_id=self.cliente.id,
            operador=self.operador,
            itens_dados=itens
        )

        agora = timezone.now()
        gerador = GeradorSaftAO(ano=agora.year, mes=agora.month, config=self.config)
        xml_saft = gerador.gerar_xml()

        self.assertIn('<AuditFile', xml_saft)
        self.assertIn('<Header>', xml_saft)
        self.assertIn('<MasterFiles>', xml_saft)
        self.assertIn('<SalesInvoices>', xml_saft)
        self.assertIn('<InvoiceNo>', xml_saft)
        self.assertIn('<TaxRegistrationNumber>5412345678</TaxRegistrationNumber>', xml_saft)
