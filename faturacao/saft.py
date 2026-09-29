import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import date
from decimal import Decimal
from django.utils import timezone
from .models import Fatura, ClienteFiscal, ConfiguracaoEmpresa


class GeradorSaftAO:
    """
    Gerador do ficheiro SAF-T (AO) - Standard Audit File for Tax purposes (Angola)
    Estrutura estritamente compatível com a Portaria e XSD da AGT versão 1.01_01.
    """

    def __init__(self, ano: int, mes: int, config: ConfiguracaoEmpresa = None):
        self.ano = int(ano)
        self.mes = int(mes)
        self.config = config or ConfiguracaoEmpresa.get_solo()
        self.data_inicio = date(self.ano, self.mes, 1)
        
        # Último dia do mês
        if self.mes == 12:
            self.data_fim = date(self.ano, 12, 31)
        else:
            self.data_fim = date(self.ano, self.mes + 1, 1) - timezone.timedelta(days=1)

    def gerar_xml(self) -> str:
        root = ET.Element('AuditFile', xmlns="urn:OECD:StandardAuditFile-Tax:AO_1.01_01")
        
        # ======================================================================
        # 1. HEADER
        # ======================================================================
        header = ET.SubElement(root, 'Header')
        ET.SubElement(header, 'AuditFileVersion').text = "1.01_01"
        ET.SubElement(header, 'CompanyID').text = self.config.nif
        ET.SubElement(header, 'TaxRegistrationNumber').text = self.config.nif
        ET.SubElement(header, 'TaxAccountingBasis').text = "F" # F = Faturação
        ET.SubElement(header, 'CompanyName').text = self.config.razao_social
        ET.SubElement(header, 'BusinessName').text = self.config.nome_comercial
        
        comp_addr = ET.SubElement(header, 'CompanyAddress')
        ET.SubElement(comp_addr, 'AddressDetail').text = self.config.endereco
        ET.SubElement(comp_addr, 'City').text = self.config.cidade
        ET.SubElement(comp_addr, 'Province').text = self.config.provincia
        ET.SubElement(comp_addr, 'Country').text = self.config.pais
        
        ET.SubElement(header, 'FiscalYear').text = str(self.ano)
        ET.SubElement(header, 'StartDate').text = self.data_inicio.strftime('%Y-%m-%d')
        ET.SubElement(header, 'EndDate').text = self.data_fim.strftime('%Y-%m-%d')
        ET.SubElement(header, 'CurrencyCode').text = "AOA"
        ET.SubElement(header, 'DateCreated').text = timezone.now().strftime('%Y-%m-%d')
        ET.SubElement(header, 'TaxEntity').text = "Global"
        ET.SubElement(header, 'ProductCompanyTaxID').text = self.config.nif_produtor_software
        ET.SubElement(header, 'SoftwareCertificateNumber').text = self.config.numero_certificado_agt
        ET.SubElement(header, 'ProductID').text = self.config.nome_software
        ET.SubElement(header, 'ProductVersion').text = self.config.versao_software

        # ======================================================================
        # 2. MASTERFILES
        # ======================================================================
        master_files = ET.SubElement(root, 'MasterFiles')
        
        # Buscar faturas do período
        faturas_periodo = Fatura.objects.filter(
            data_emissao__range=[self.data_inicio, self.data_fim]
        ).select_related('cliente', 'serie_fiscal').prefetch_related('itens', 'itens__motivo_isencao').order_by('system_entry_date')

        # 2.1 Clientes
        clientes_ids = faturas_periodo.values_list('cliente_id', flat=True).distinct()
        for cliente in ClienteFiscal.objects.filter(id__in=clientes_ids):
            c_elem = ET.SubElement(master_files, 'Customer')
            ET.SubElement(c_elem, 'CustomerID').text = str(cliente.id)
            ET.SubElement(c_elem, 'AccountID').text = "Desconhecido"
            ET.SubElement(c_elem, 'CustomerTaxID').text = cliente.nif
            ET.SubElement(c_elem, 'CompanyName').text = cliente.nome_razao_social
            
            c_addr = ET.SubElement(c_elem, 'BillingAddress')
            ET.SubElement(c_addr, 'AddressDetail').text = cliente.endereco
            ET.SubElement(c_addr, 'City').text = cliente.cidade
            ET.SubElement(c_addr, 'Country').text = cliente.pais
            ET.SubElement(c_elem, 'SelfBillingIndicator').text = "0"

        # 2.2 Tabela de Impostos (TaxTable)
        tax_table = ET.SubElement(master_files, 'TaxTable')
        
        impostos_padrao = [
            ('NOR', 'Taxa Normal', '14.00'),
            ('RED', 'Taxa Reduzida', '7.00'),
            ('ISE', 'Isenta', '0.00'),
        ]
        for codigo_taxa, desc, percentual in impostos_padrao:
            entry = ET.SubElement(tax_table, 'TaxTableEntry')
            ET.SubElement(entry, 'TaxType').text = "IVA"
            ET.SubElement(entry, 'TaxCountryRegion').text = "AO"
            ET.SubElement(entry, 'TaxCode').text = codigo_taxa
            ET.SubElement(entry, 'Description').text = desc
            ET.SubElement(entry, 'TaxPercentage').text = percentual

        # ======================================================================
        # 3. SOURCEDOCUMENTS (SalesInvoices)
        # ======================================================================
        source_docs = ET.SubElement(root, 'SourceDocuments')
        sales_inv = ET.SubElement(source_docs, 'SalesInvoices')
        
        ET.SubElement(sales_inv, 'NumberOfEntries').text = str(faturas_periodo.count())
        total_credit = Decimal('0.00')
        total_debit = Decimal('0.00')
        
        for fatura in faturas_periodo:
            if fatura.serie_fiscal.tipo_documento == 'NC':
                total_debit += fatura.total_incidencia
            else:
                total_credit += fatura.total_incidencia

            inv = ET.SubElement(sales_inv, 'Invoice')
            ET.SubElement(inv, 'InvoiceNo').text = fatura.numero_fatura
            
            doc_status = ET.SubElement(inv, 'DocumentStatus')
            ET.SubElement(doc_status, 'InvoiceStatus').text = fatura.status
            ET.SubElement(doc_status, 'InvoiceStatusDate').text = fatura.system_entry_date.strftime('%Y-%m-%dT%H:%M:%S')
            ET.SubElement(doc_status, 'SourceID').text = str(fatura.operador_id)
            ET.SubElement(doc_status, 'SourceBilling').text = "P" # P = Produzido pelo programa

            ET.SubElement(inv, 'Hash').text = fatura.hash_assinatura
            ET.SubElement(inv, 'HashControl').text = str(fatura.versao_chave)
            ET.SubElement(inv, 'Period').text = str(self.mes)
            ET.SubElement(inv, 'InvoiceDate').text = fatura.data_emissao.strftime('%Y-%m-%d')
            ET.SubElement(inv, 'InvoiceType').text = fatura.serie_fiscal.tipo_documento
            
            special_regimes = ET.SubElement(inv, 'SpecialRegimes')
            ET.SubElement(special_regimes, 'SelfBillingIndicator').text = "0"
            ET.SubElement(special_regimes, 'CashVATSchemeIndicator').text = "0"
            ET.SubElement(special_regimes, 'ThirdPartiesBillingIndicator').text = "0"

            ET.SubElement(inv, 'SourceID').text = str(fatura.operador_id)
            ET.SubElement(inv, 'SystemEntryDate').text = fatura.system_entry_date.strftime('%Y-%m-%dT%H:%M:%S')
            ET.SubElement(inv, 'CustomerID').text = str(fatura.cliente_id)

            # Linhas da Fatura
            for linha in fatura.itens.all():
                l_elem = ET.SubElement(inv, 'Line')
                ET.SubElement(l_elem, 'LineNumber').text = str(linha.numero_linha)
                ET.SubElement(l_elem, 'ProductCode').text = linha.codigo_produto
                ET.SubElement(l_elem, 'ProductDescription').text = linha.descricao
                ET.SubElement(l_elem, 'Quantity').text = f"{linha.quantidade:.2f}"
                ET.SubElement(l_elem, 'UnitOfMeasure').text = "Un"
                ET.SubElement(l_elem, 'UnitPrice').text = f"{linha.preco_unitario:.2f}"
                ET.SubElement(l_elem, 'TaxPointDate').text = fatura.data_emissao.strftime('%Y-%m-%d')
                ET.SubElement(l_elem, 'Description').text = linha.descricao
                
                if fatura.serie_fiscal.tipo_documento == 'NC':
                    ET.SubElement(l_elem, 'DebitAmount').text = f"{linha.subtotal_liquido:.2f}"
                else:
                    ET.SubElement(l_elem, 'CreditAmount').text = f"{linha.subtotal_liquido:.2f}"
                
                tax = ET.SubElement(l_elem, 'Tax')
                ET.SubElement(tax, 'TaxType').text = "IVA"
                ET.SubElement(tax, 'TaxCountryRegion').text = "AO"
                ET.SubElement(tax, 'TaxCode').text = linha.tipo_taxa_iva
                ET.SubElement(tax, 'TaxPercentage').text = f"{linha.taxa_iva:.2f}"

                if linha.taxa_iva == Decimal('0.00') and linha.motivo_isencao:
                    ET.SubElement(l_elem, 'TaxExemptionReason').text = linha.motivo_isencao.mencao_legal
                    ET.SubElement(l_elem, 'TaxExemptionCode').text = linha.motivo_isencao.codigo

            # Totais do Documento
            doc_totals = ET.SubElement(inv, 'DocumentTotals')
            ET.SubElement(doc_totals, 'TaxPayable').text = f"{fatura.total_iva:.2f}"
            ET.SubElement(doc_totals, 'NetTotal').text = f"{fatura.total_incidencia:.2f}"
            ET.SubElement(doc_totals, 'GrossTotal').text = f"{fatura.total_bruto:.2f}"

        ET.SubElement(sales_inv, 'TotalDebit').text = f"{total_debit:.2f}"
        ET.SubElement(sales_inv, 'TotalCredit').text = f"{total_credit:.2f}"

        # Pretty print com indentação padrão
        raw_xml = ET.tostring(root, encoding='utf-8')
        reparsed = minidom.parseString(raw_xml)
        return reparsed.toprettyxml(indent="  ", encoding="utf-8").decode('utf-8')
