import os
import base64
from pathlib import Path
from decimal import Decimal
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key


class AssinadorFiscalAGT:
    """
    Motor criptográfico oficial em conformidade com as regras técnicas da AGT Angola:
    - Algoritmo: RSA com hash SHA-1 (padrão de certificação SAF-T AO)
    - Formato de entrada: InvoiceDate;SystemEntryDate;InvoiceNo;GrossTotal;PreviousHash
    - Formato de saída: Assinatura digital codificada em Base64
    """

    def __init__(self, caminho_chave_privada: str, senha_chave: bytes = None):
        self.caminho_chave = caminho_chave_privada
        
        # Se a chave não existir, gera automaticamente para ambiente de desenvolvimento/teste
        if not os.path.exists(caminho_chave_privada):
            caminho_pub = caminho_chave_privada.replace('privada', 'publica')
            self.gerar_par_chaves_rsa(caminho_chave_privada, caminho_pub)

        with open(caminho_chave_privada, 'rb') as key_file:
            self.private_key = load_pem_private_key(
                key_file.read(),
                password=senha_chave
            )

    @staticmethod
    def gerar_par_chaves_rsa(caminho_privada: str, caminho_publica: str, tamanho_bits: int = 2048):
        """Gera par de chaves RSA em formato PEM (PKCS#8 / SubjectPublicKeyInfo)"""
        os.makedirs(os.path.dirname(os.path.abspath(caminho_privada)), exist_ok=True)
        os.makedirs(os.path.dirname(os.path.abspath(caminho_publica)), exist_ok=True)
        
        chave_privada = rsa.generate_private_key(
            public_exponent=65537,
            key_size=tamanho_bits
        )
        
        pem_privada = chave_privada.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        with open(caminho_privada, 'wb') as f:
            f.write(pem_privada)

        chave_publica = chave_privada.public_key()
        pem_publica = chave_publica.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        with open(caminho_publica, 'wb') as f:
            f.write(pem_publica)

    @staticmethod
    def construir_string_dados(data_emissao: str, system_entry_date: str, 
                               numero_fatura: str, total_bruto: Decimal, 
                               hash_anterior: str) -> str:
        """
        Gera a string de dados conforme o padrão oficial da AGT:
        Exemplo: '2026-09-16;2026-09-16T10:30:00;FT 2026A/1;11400.00;hash_anterior_em_base64'
        """
        total_str = f"{Decimal(total_bruto):.2f}"
        hash_ant = hash_anterior if hash_anterior else ""
        return f"{data_emissao};{system_entry_date};{numero_fatura};{total_str};{hash_ant}"

    def assinar_documento(self, string_dados: str) -> str:
        """
        Assina a string com RSA-SHA1 e retorna a assinatura codificada em Base64.
        """
        dados_bytes = string_dados.encode('utf-8')
        assinatura_bytes = self.private_key.sign(
            dados_bytes,
            padding.PKCS1v15(),
            hashes.SHA1()
        )
        return base64.b64encode(assinatura_bytes).decode('utf-8')

    @staticmethod
    def extrair_hash_curto_impresso(assinatura_base64: str, num_validacao_agt="000/AGT/2026") -> str:
        """
        Extrai os 4 caracteres de validação impressa (posições 1, 11, 21 e 31, base 1)
        Exemplo retornado: 'Ab9Z-Processado por programa validado n.º 000/AGT/2026'
        """
        if len(assinatura_base64) >= 31:
            caracteres = (
                assinatura_base64[0] +
                assinatura_base64[10] +
                assinatura_base64[20] +
                assinatura_base64[30]
            )
        else:
            caracteres = assinatura_base64[:4]
            
        return f"{caracteres}-Processado por programa validado n.º {num_validacao_agt}"

    def verificar_assinatura(self, string_dados: str, assinatura_base64: str, caminho_chave_publica: str) -> bool:
        """Valida se uma assinatura bate exatamente com a chave pública comunicada à AGT"""
        with open(caminho_chave_publica, 'rb') as f:
            pub_key = load_pem_public_key(f.read())
            
        try:
            assinatura_bytes = base64.b64decode(assinatura_base64)
            pub_key.verify(
                assinatura_bytes,
                string_dados.encode('utf-8'),
                padding.PKCS1v15(),
                hashes.SHA1()
            )
            return True
        except Exception:
            return False
