from decimal import Decimal
from datetime import date
from django.test import TestCase
from conta.models import Conta
from lojas.models import Loja, EstoqueLoja, Venda
from produtos.models import Produto
from relatorio.models import RelatorioDiario


class RelatorioDiarioTestCase(TestCase):
    def setUp(self):
        self.usuario = Conta.objects.create_user(
            email='relatorio_user@teste.com',
            username='rel_user',
            nome='Usuario Relatorio',
            password='SenhaValida123!@#'
        )
        self.loja = Loja.objects.create(
            nome='Loja Relatório',
            bairro='Bairro 1',
            cidade='Luanda',
            provincia='Luanda',
            municipio='Luanda'
        )
        self.loja.gerentes.add(self.usuario)
        
        self.produto = Produto.objects.create(
            nome='Produto Teste',
            preco=Decimal('500.00')
        )
        self.estoque = EstoqueLoja.objects.create(
            loja=self.loja,
            produto=self.produto,
            quantidade=100
        )

    def test_calcular_total_vendas_dia_com_vendas_reais(self):
        """Testa se calcular_total_vendas_dia agora soma as vendas da loja corretamente"""
        hoje = date.today()
        
        # Criar uma venda na data de hoje
        venda1 = Venda.objects.create(
            estoque_loja=self.estoque,
            item_type='produto',
            quantidade=2,
            valor_total=Decimal('1000.00'),
            vendedor=self.usuario,
            status='normal'
        )
        venda2 = Venda.objects.create(
            estoque_loja=self.estoque,
            item_type='produto',
            quantidade=3,
            valor_total=Decimal('1500.00'),
            vendedor=self.usuario,
            status='normal'
        )
        
        relatorio = RelatorioDiario.objects.create(
            loja=self.loja,
            usuario=self.usuario,
            data=hoje
        )
        
        total_vendas = relatorio.calcular_total_vendas_dia()
        self.assertEqual(total_vendas, Decimal('2500.00'))

    def test_status_relatorio_completo_e_negativo(self):
        """Testa cálculo de diferença e classificação correta de status"""
        # Relatório preenchido com sobra de caixa
        relatorio_completo = RelatorioDiario.objects.create(
            loja=self.loja,
            usuario=self.usuario,
            data=date(2026, 1, 1),
            tpa=Decimal('100.00'),
            dstv=Decimal('50.00'),
            zap=Decimal('50.00'),
            unitel=Decimal('50.00'),
            africell=Decimal('50.00'),
            recargas=Decimal('50.00'),
            acc=Decimal('50.00'),
            dm=Decimal('300.00'),
            moedas=Decimal('50.00'),
            gastos=Decimal('20.00'),
        )
        # Total geral previsto: 50*6 = 300.00
        # Total arrecadado: 300 + 50 + 100 + 20 = 470.00
        # Diferença: 470 - 300 = +170.00 (sobra)
        self.assertEqual(relatorio_completo.get_status(), 'completo')
        self.assertFalse(relatorio_completo.tem_falta_dinheiro())
        self.assertGreater(relatorio_completo.calcular_diferenca(), Decimal('0.00'))
