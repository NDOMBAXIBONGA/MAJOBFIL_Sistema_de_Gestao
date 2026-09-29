from django.test import TestCase, Client
from django.urls import reverse
from conta.models import Conta


class ContaSecurityTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = Conta.objects.create_superuser(
            email='admin@teste.com',
            username='admin1',
            nome='Administrador',
            password='AdminForte123!@#'
        )
        self.user = Conta.objects.create_user(
            email='operador@teste.com',
            username='operador1',
            nome='Operador Normal',
            password='Operador123!@#'
        )

    def test_toggle_status_bloqueia_metodo_get(self):
        """Testa se requisições GET para toggle_status são rejeitadas com 405 Method Not Allowed"""
        self.client.force_login(self.admin)
        url = reverse('toggle_usuario_status', kwargs={'user_id': self.user.id})
        
        # GET deve ser proibido
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)
        
        # POST deve funcionar
        response_post = self.client.post(url)
        self.assertEqual(response_post.status_code, 302)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_redefinir_senha_admin_valida_politicas(self):
        """Testa se a redefinição de senha aplica as regras de complexidade do Django"""
        self.client.force_login(self.admin)
        url = reverse('redefinir_senha_admin')
        
        # Tentativa com senha comum ou muito simples (ex: 12345678)
        resp_fraca = self.client.post(url, {
            'user_id': self.user.id,
            'nova_senha': 'password',
            'confirmar_senha': 'password'
        })
        dados = resp_fraca.json()
        self.assertFalse(dados['success'])
        self.assertTrue(len(dados['errors']) > 0)
        
        # Tentativa com senha forte válida
        resp_forte = self.client.post(url, {
            'user_id': self.user.id,
            'nova_senha': 'SenhaMtoSegura#2026!',
            'confirmar_senha': 'SenhaMtoSegura#2026!'
        })
        dados_forte = resp_forte.json()
        self.assertTrue(dados_forte['success'])
