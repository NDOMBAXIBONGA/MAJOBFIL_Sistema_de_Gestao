from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import SerieFiscal, Fatura, ItemFatura, ClienteFiscal, MotivoIsencaoIVA, ConfiguracaoEmpresa
from .security import AssinadorFiscalAGT


class ServicoFaturacaoAGT:
    def __init__(self, assinador: AssinadorFiscalAGT = None):
        if assinador is None:
            config = ConfiguracaoEmpresa.get_solo()
            assinador = AssinadorFiscalAGT(caminho_chave_privada=config.chave_privada_path)
        self.assinador = assinador

    @transaction.atomic
    def emitir_fatura(self, *, serie_id: int, cliente_id: int, operador,
                      itens_dados: list, data_vencimento=None, observacoes="") -> Fatura:
        """
        Cria e assina uma fatura de forma atómica e sequencial à prova de concorrência.
        Garante conformidade com o Regime Jurídico das Faturas (Decreto Presidencial 71/25).
        """
        config = ConfiguracaoEmpresa.get_solo()
        
        # 1. Bloqueio pessimista da série fiscal concorrente
        serie = SerieFiscal.objects.select_for_update().get(id=serie_id, ativa=True)
        proximo_numero = serie.ultimo_numero + 1
        numero_fatura = f"{serie.tipo_documento} {serie.serie}/{serie.ano}/{proximo_numero}"
        
        # 2. Obter Adquirente
        cliente = ClienteFiscal.objects.get(id=cliente_id, ativo=True)
        
        # 3. Preparar datas oficiais
        agora = timezone.now()
        data_emissao_str = agora.strftime('%Y-%m-%d')
        system_entry_date_str = agora.strftime('%Y-%m-%dT%H:%M:%S')

        # 4. Cálculo de Itens, Base de Incidência e IVA
        total_incidencia = Decimal('0.00')
        total_iva = Decimal('0.00')
        total_descontos = Decimal('0.00')
        itens_para_salvar = []

        if not itens_dados:
            raise ValidationError("A fatura deve conter pelo menos um artigo/serviço.")

        for idx, item in enumerate(itens_dados, start=1):
            qtd = Decimal(str(item['quantidade']))
            preco_unit = Decimal(str(item['preco_unitario']))
            desconto = Decimal(str(item.get('desconto', '0.00')))
            
            # Tratamento fiscal por regime do emitente
            regime_emitente = config.regime_iva
            
            if regime_emitente == 'EXCLUSAO':
                taxa_iva = Decimal('0.00')
                tipo_taxa = 'ISE'
                motivo_cod = item.get('codigo_isencao', 'M04') # Regime de exclusão
                motivo = MotivoIsencaoIVA.objects.filter(codigo=motivo_cod).first()
            elif regime_emitente == 'SIMPLIFICADO':
                taxa_iva = Decimal('7.00')
                tipo_taxa = 'RED'
                motivo = None
            else:
                # Regime Geral: taxa configurada no produto (14%, 7%, 5% ou 0%)
                taxa_iva = Decimal(str(item.get('taxa_iva', '14.00')))
                if taxa_iva == Decimal('14.00'):
                    tipo_taxa = 'NOR'
                    motivo = None
                elif taxa_iva == Decimal('0.00'):
                    tipo_taxa = 'ISE'
                    motivo_cod = item.get('codigo_isencao')
                    if not motivo_cod:
                        raise ValidationError(f"O item '{item['descricao']}' tem taxa de IVA de 0%, sendo obrigatório o Código de Isenção da AGT.")
                    motivo = MotivoIsencaoIVA.objects.filter(codigo=motivo_cod).first()
                else:
                    tipo_taxa = 'RED'
                    motivo = None

            # Subtotal da linha
            subtotal_bruto = qtd * preco_unit
            subtotal_liquido = subtotal_bruto - desconto
            
            # Cálculo de IVA com arredondamento fiscal a 2 casas
            montante_iva = (subtotal_liquido * (taxa_iva / Decimal('100.00'))).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            total_linha = subtotal_liquido + montante_iva

            # Acumuladores
            total_incidencia += subtotal_liquido
            total_iva += montante_iva
            total_descontos += desconto

            itens_para_salvar.append({
                'numero_linha': idx,
                'codigo_produto': item.get('codigo_produto', f"ART{idx}"),
                'descricao': item['descricao'],
                'quantidade': qtd,
                'preco_unitario': preco_unit,
                'desconto_linha': desconto,
                'tipo_taxa_iva': tipo_taxa,
                'taxa_iva': taxa_iva,
                'valor_iva': montante_iva,
                'motivo_isencao': motivo,
                'subtotal_liquido': subtotal_liquido,
                'total_linha': total_linha
            })

        total_bruto = total_incidencia + total_iva

        # 5. Geração da Assinatura Criptográfica Fiscal (Chaining com Fatura Anterior)
        hash_anterior = serie.ultimo_hash
        string_dados = self.assinador.construir_string_dados(
            data_emissao=data_emissao_str,
            system_entry_date=system_entry_date_str,
            numero_fatura=numero_fatura,
            total_bruto=total_bruto,
            hash_anterior=hash_anterior
        )
        
        assinatura_base64 = self.assinador.assinar_documento(string_dados)
        hash_curto_impresso = self.assinador.extrair_hash_curto_impresso(
            assinatura_base64, 
            num_validacao_agt=config.numero_certificado_agt
        )

        # 6. Gravar Cabeçalho da Fatura
        fatura = Fatura.objects.create(
            serie_fiscal=serie,
            numero_sequencial=proximo_numero,
            numero_fatura=numero_fatura,
            data_emissao=agora.date(),
            system_entry_date=agora,
            data_vencimento=data_vencimento or agora.date(),
            emitente_nome=config.razao_social,
            emitente_nif=config.nif,
            emitente_endereco=config.endereco,
            emitente_regime_iva=config.regime_iva,
            cliente=cliente,
            cliente_nome=cliente.nome_razao_social,
            cliente_nif=cliente.nif,
            cliente_endereco=cliente.endereco,
            total_incidencia=total_incidencia,
            total_iva=total_iva,
            total_descontos=total_descontos,
            total_bruto=total_bruto,
            hash_anterior=hash_anterior,
            dados_para_hash=string_dados,
            hash_assinatura=assinatura_base64,
            hash_curto=hash_curto_impresso,
            versao_chave=config.versao_chave,
            operador=operador,
            observacoes=observacoes
        )

        # 7. Gravar Itens
        for dados_linha in itens_para_salvar:
            ItemFatura.objects.create(fatura=fatura, **dados_linha)

        # 8. Atualizar Estado da Série Fiscal
        serie.ultimo_numero = proximo_numero
        serie.ultimo_hash = assinatura_base64
        serie.save()

        return fatura

    def faturar_venda_pos(self, venda_id: int, cliente_id: int, operador, tipo_doc: str = 'FR') -> Fatura:
        """Converte uma venda registada no POS (Lojas) numa Fatura Fiscal AGT oficial"""
        from lojas.models import Venda
        venda = Venda.objects.get(id=venda_id)
        
        # Encontrar série fiscal ativa para o ano atual
        ano_atual = timezone.now().year
        serie = SerieFiscal.objects.filter(
            tipo_documento=tipo_doc,
            ano=ano_atual,
            ativa=True
        ).first()
        
        if not serie:
            serie = SerieFiscal.objects.create(
                serie='A',
                tipo_documento=tipo_doc,
                ano=ano_atual,
                ativa=True
            )
            
        item_dados = [{
            'codigo_produto': f"PRD-{venda.id}",
            'descricao': venda.item_nome,
            'quantidade': venda.quantidade,
            'preco_unitario': venda.preco_unitario,
            'desconto': Decimal('0.00'),
            'taxa_iva': Decimal('14.00')
        }]
        
        return self.emitir_fatura(
            serie_id=serie.id,
            cliente_id=cliente_id,
            operador=operador,
            itens_dados=item_dados,
            observacoes=f"Emitido a partir da Venda POS #{venda.id}"
        )
