import json
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from conta.models import Conta
from produtos.models import Produto
from lojas.models import Loja, EstoqueLoja, Venda, MovimentacaoEstoque


class VendaEstoqueTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Criar usuário gerente
        self.gerente = Conta.objects.create_user(
            email='gerente@teste.com',
            username='gerente1',
            nome='Gerente Teste',
            password='SenhaForte123!@#'
        )
        
        # Criar outro usuário sem permissão
        self.outro_usuario = Conta.objects.create_user(
            email='outro@teste.com',
            username='outro1',
            nome='Outro Usuario',
            password='SenhaForte123!@#'
        )
        
        # Criar loja associada ao gerente
        self.loja = Loja.objects.create(
            nome='Loja Central',
            bairro='Centro',
            cidade='Luanda',
            provincia='Luanda',
            municipio='Luanda'
        )
        self.loja.gerentes.add(self.gerente)
        
        # Criar produto e estoque
        self.produto = Produto.objects.create(
            nome='Cartão Unitel 1000',
            preco=Decimal('1000.00')
        )
        self.estoque = EstoqueLoja.objects.create(
            loja=self.loja,
            produto=self.produto,
            quantidade=50
        )

    def test_registrar_venda_sucesso_com_baixa_de_estoque(self):
        """Testa se a venda com POST e CSRF reduz corretamente o estoque"""
        self.client.force_login(self.gerente)
        
        response = self.client.post(
            reverse('registrar_venda'),
            data=json.dumps({
                'estoque_id': self.estoque.id,
                'item_type': 'produto',
                'quantidade': 5,
                'observacao': 'Venda teste'
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        dados = response.json()
        self.assertTrue(dados.get('success'))
        
        # Verificar baixa no estoque
        self.estoque.refresh_from_db()
        self.assertEqual(self.estoque.quantidade, 45)
        
        # Verificar criação da venda
        venda = Venda.objects.get(id=dados['venda_id'])
        self.assertEqual(venda.quantidade, 5)
        self.assertEqual(venda.valor_total, Decimal('5000.00'))
        self.assertEqual(venda.vendedor, self.gerente)
        
        # Verificar movimentação de saída
        mov = MovimentacaoEstoque.objects.filter(venda=venda).first()
        self.assertIsNotNone(mov)
        self.assertEqual(mov.tipo_movimentacao, 'saida')
        self.assertEqual(mov.quantidade, 5)

    def test_bloquear_venda_com_estoque_insuficiente(self):
        """Testa se vendas com quantidade superior ao estoque são rejeitadas"""
        self.client.force_login(self.gerente)
        
        response = self.client.post(
            reverse('registrar_venda'),
            data=json.dumps({
                'estoque_id': self.estoque.id,
                'item_type': 'produto',
                'quantidade': 999,
                'observacao': 'Venda excessiva'
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        dados = response.json()
        self.assertFalse(dados.get('success'))
        self.assertIn('insuficiente', dados.get('error', '').lower())
        
        # Estoque deve permanecer inalterado
        self.estoque.refresh_from_db()
        self.assertEqual(self.estoque.quantidade, 50)

    def test_bloquear_venda_por_usuario_sem_permissao(self):
        """Testa se usuário que não é gerente da loja é impedido de vender"""
        self.client.force_login(self.outro_usuario)
        
        response = self.client.post(
            reverse('registrar_venda'),
            data=json.dumps({
                'estoque_id': self.estoque.id,
                'item_type': 'produto',
                'quantidade': 1
            }),
            content_type='application/json'
        )
        
        dados = response.json()
        self.assertFalse(dados.get('success'))
        self.assertIn('permissão', dados.get('error', '').lower())

    def test_api_totais_vendas_protegida(self):
        """Testa se a API de totais de vendas exige autenticação e permissão de gerente"""
        # Sem login -> redireciona para login
        url = f"{reverse('api_totais_vendas')}?loja_id={self.loja.id}"
        resp_anon = self.client.get(url)
        self.assertEqual(resp_anon.status_code, 302)
        
        # Com login de outro usuário -> 403 Forbidden
        self.client.force_login(self.outro_usuario)
        resp_outro = self.client.get(url)
        self.assertEqual(resp_outro.status_code, 403)
        
        # Com login do gerente -> 200 OK
        self.client.force_login(self.gerente)
        resp_gerente = self.client.get(url)
        self.assertEqual(resp_gerente.status_code, 200)
