import re
from decimal import Decimal

from django.db import models
from django.db.models import Sum, F, DecimalField, ExpressionWrapper
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

class Empresa(models.Model):
    empresa_id = models.AutoField("ID", primary_key=True)
    empresa_nome = models.CharField("Empresa",max_length=45)

    class Meta:
        db_table = 'empresa'
        verbose_name = 'Emmpresa'
        verbose_name_plural = 'Empresas'

    def __str__(self):
        return self.empresa_nome

class Fornecedor(models.Model):
    fornecedor_id = models.AutoField("ID", primary_key=True)
    fornecedor_nome = models.CharField("Fornecedor", max_length=100)

    class Meta:
        db_table = 'fornecedor'
        verbose_name = 'Fornecedor'
        verbose_name_plural = 'Fornecedores'

    def __str__(self):
        return self.fornecedor_nome

class Cliente(models.Model):
    cliente_id = models.AutoField("ID", primary_key=True)
    cliente_nome = models.CharField("Cliente", max_length=45)

    class Meta:
        db_table = 'cliente'
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'

    def __str__(self):
        return self.cliente_nome

class Convenio(models.Model):
    convenio_id = models.AutoField("ID", primary_key=True)
    convenio_nome = models.CharField("Convênio",max_length=45)
    convenio_preco = models.FloatField("Preço", )

    class Meta:
        db_table = 'convenio'
        verbose_name = 'Convênio'
        verbose_name_plural = 'Convênios'

    def __str__(self):
        return self.convenio_nome

class GrupoMercadoria(models.Model):
    grupo_mercadoria_id = models.AutoField("ID", primary_key=True)
    grupo_mercadoria_nome = models.CharField("Grupo", max_length=45)

    class Meta:
        db_table = 'grupo_mercadoria'
        verbose_name = 'Grupo de Mercadoria'
        verbose_name_plural = 'Grupos de Mercadorias'

    def __str__(self):
        return self.grupo_mercadoria_nome

class Funcionario(models.Model):
    funcionario_id = models.AutoField("ID", primary_key=True)
    funcionario_nome = models.CharField("Funcionário", max_length=100)

    class Meta:
        db_table = 'funcionario'
        verbose_name = 'Funcionário'
        verbose_name_plural = 'Funcionários'

    def __str__(self):
        return self.funcionario_nome

class Veiculo(models.Model):
    veiculo_id = models.AutoField("ID", primary_key=True)
    veiculo_placa = models.CharField("Placa", max_length=45)
    veiculo_modelo = models.CharField("Modelo", max_length=45)

    class Meta:
        db_table = 'veiculo'
        verbose_name = 'Veículo'
        verbose_name_plural = 'Veículos'

    def __str__(self):
        return f'{self.veiculo_modelo} - {self.veiculo_placa}'

class PlanoConta(models.Model):
    plano_conta_id = models.AutoField("ID", primary_key=True)
    plano_conta_numero = models.CharField("Número da Conta", max_length=20, null=True, blank=True, help_text="1=Receita, 3=Despesa, 5=Banco")
    plano_conta_nome = models.CharField("Conta", max_length=50)

    class Meta:
        db_table = 'plano_conta'
        verbose_name = 'Plano de Conta'
        verbose_name_plural = 'Planos de Conta'
        ordering = ['plano_conta_numero', 'plano_conta_nome']

    def __str__(self):
        if self.plano_conta_numero:
            return f"{self.plano_conta_numero} - {self.plano_conta_nome}"
        return self.plano_conta_nome
    
    def get_primeiro_digito(self):
        """Retorna o primeiro dígito do número da conta."""
        if self.plano_conta_numero and len(self.plano_conta_numero) > 0:
            # Remove espaços e pega o primeiro caractere
            numero_limpo = str(self.plano_conta_numero).strip()
            if numero_limpo and numero_limpo[0].isdigit():
                return numero_limpo[0]
        return None
    
    def is_receita(self):
        """
        Verifica se é conta de receita (entrada).
        Contas que iniciam com 1 são receitas e devem ser exibidas em vendas.
        """
        return self.get_primeiro_digito() == '1'
    
    def is_despesa(self):
        """
        Verifica se é conta de despesa (saída).
        Contas que iniciam com 3 são despesas e devem ser exibidas em compras.
        """
        return self.get_primeiro_digito() == '3'
    
    def is_banco(self):
        """
        Verifica se é conta bancária.
        Contas que iniciam com 5 são relacionadas a bancos.
        """
        return self.get_primeiro_digito() == '5'
    
    def get_tipo_conta(self):
        """Retorna o tipo da conta de forma legível."""
        primeiro_digito = self.get_primeiro_digito()
        if primeiro_digito == '1':
            return 'Receita (Entrada)'
        elif primeiro_digito == '3':
            return 'Despesa (Saída)'
        elif primeiro_digito == '5':
            return 'Banco'
        else:
            return 'Outros'
    
    @staticmethod
    def get_contas_receita():
        """Retorna todas as contas de receita (iniciam com 1)."""
        return PlanoConta.objects.filter(plano_conta_numero__startswith='1')
    
    @staticmethod
    def get_contas_despesa():
        """Retorna todas as contas de despesa (iniciam com 3)."""
        return PlanoConta.objects.filter(plano_conta_numero__startswith='3')
    
    @staticmethod
    def get_contas_banco():
        """Retorna todas as contas bancárias (iniciam com 5)."""
        return PlanoConta.objects.filter(plano_conta_numero__startswith='5')

class Cfop(models.Model):
    class TipoCfop(models.IntegerChoices):
        ENTRADA = 1, 'Entrada'
        SAIDA = 2, 'Saída'
    
    class IntegracaoChoice(models.TextChoices):
        RECEBER = 'receber', 'Contas a Receber'
        PAGAR = 'pagar', 'Contas a Pagar'
        CAIXA = 'caixa', 'Livro Caixa'
        ESTOQUE = 'estoque', 'Não Movimenta Estoque'
        CAIXA_CHEQUE = 'caixa/cheque', 'Caixa/Cheque Pré-datado'
        ESTOQUE_CAIXA = 'estoque/caixa', 'Não Movimenta Estoque + Livro Caixa'
        ESTOQUE_PAGAR = 'estoque/pagar', 'Não Movimenta Estoque + Contas a Pagar'
        ESTOQUE_RECEBER = 'estoque/receber', 'Não Movimenta Estoque + Contas a Receber'

    cfop_id = models.AutoField("ID", primary_key=True)
    cfop_codigo = models.CharField("Código", max_length=10, null=True, blank=True)
    cfop_operacao = models.CharField("Operação",max_length=255, null=True, blank=True)
    cfop_integracao = models.CharField("Integração", max_length=50, choices=IntegracaoChoice.choices, null=True, blank=True)
    cfop_tipo = models.IntegerField("Tipo", choices=TipoCfop.choices, null=True, blank=True)

    class Meta:
        db_table = 'cfop'
        verbose_name = 'CFOP'
        verbose_name_plural = 'CFOPs'
        ordering = ['cfop_codigo']

    def __str__(self):
        return f'{self.cfop_codigo} - {self.cfop_operacao}'
    
    def get_first_digit(self):
        """Retorna o primeiro dígito do código CFOP."""
        if self.cfop_codigo and len(self.cfop_codigo) > 0:
            return self.cfop_codigo[0]
        return None
    
    def is_venda_operation(self):
        """
        Verifica se é operação de venda (códigos iniciados com 5 ou 6).
        Código azul - disponível apenas para notas fiscais de venda.
        """
        first_digit = self.get_first_digit()
        return first_digit in ['5', '6']
    
    def is_compra_operation(self):
        """
        Verifica se é operação de compra (códigos iniciados com 1 ou 2).
        Código vermelho - disponível apenas para notas fiscais de compra.
        """
        first_digit = self.get_first_digit()
        return first_digit in ['1', '2']
    
    def is_export_operation(self):
        """
        Verifica se é operação de exportação (códigos iniciados com 7).
        Código verde - disponível para vendas.
        """
        first_digit = self.get_first_digit()
        return first_digit == '7'
    
    def is_import_operation(self):
        """
        Verifica se é operação de importação (códigos iniciados com 3).
        Código verde - disponível para compras.
        """
        first_digit = self.get_first_digit()
        return first_digit == '3'
    
    def get_color_code(self):
        """
        Retorna a cor associada ao tipo de operação:
        - Azul: Vendas (5, 6)
        - Vermelho: Compras (1, 2)
        - Verde: Importação/Exportação (3, 7)
        """
        first_digit = self.get_first_digit()
        if first_digit in ['5', '6']:
            return 'blue'
        elif first_digit in ['1', '2']:
            return 'red'
        elif first_digit in ['3', '7']:
            return 'green'
        return 'black'
    
    def is_available_for_venda(self):
        """CFOPs disponíveis para venda: 5, 6 (vendas) e 7 (exportação)."""
        return self.is_venda_operation() or self.is_export_operation()
    
    def is_available_for_compra(self):
        """CFOPs disponíveis para compra: 1, 2 (compras) e 3 (importação)."""
        return self.is_compra_operation() or self.is_import_operation()

class Produto(models.Model):
    produto_id = models.AutoField(primary_key=True)
    #empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, db_column='empresa_id')
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.CASCADE, db_column='fornecedor_id')
    grupo_mercadoria = models.ForeignKey(GrupoMercadoria, on_delete=models.CASCADE, db_column='grupo_mercadoria_id')
    produto_nome = models.CharField(max_length=100)
    produto_unidade_medida = models.CharField(max_length=20)
    produto_preco = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Preço de Venda")
    produto_preco_custo = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name="Preço de Custo",
        help_text="Preço de custo usado quando a venda não tem romaneio",
        null=True,
        blank=True
    )

    class Meta:
        db_table = 'produto'
        verbose_name = 'Produto'
        verbose_name_plural = 'Produtos'

    def __str__(self):
        return self.produto_nome

class Compra(models.Model):
    compra_id = models.AutoField("ID", primary_key=True)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, db_column='empresa_id')
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.CASCADE, db_column='fornecedor_id')
    plano_conta = models.ForeignKey(PlanoConta, on_delete=models.CASCADE, db_column='plano_conta_id')
    compra_numero = models.CharField("Número da Compra", max_length=10)
    compra_data_entrada = models.DateField("Data de Entrada")
    compra_data_saida_fornecedor = models.DateField("Data de Saída do Fornecedor", null=True, blank=True)
    compra_prazo_pagamento = models.CharField("Prazo de Pagamento", max_length=50)
    compra_data_base = models.DateField("Data Base", null=True, blank=True)

    class Meta:
        db_table = 'compra'
        verbose_name = 'Compra'
        verbose_name_plural = 'Compras'

    def __str__(self):
        return f'Compra {self.compra_numero} - {self.fornecedor.fornecedor_nome}'

    def calcular_total_pagar(self):
        from .models import CompraItem  # evitar import circular
        total = CompraItem.objects.filter(
            compra=self,
            cfop__cfop_integracao__icontains="pagar"
        ).aggregate(
            total=Sum(
                ExpressionWrapper(
                    F('compra_item_qtd') * F('compra_item_preco'),
                    output_field=DecimalField()
                )
            )
        )['total'] or 0
        return total

class CompraItem(models.Model):
    compra_item_id = models.AutoField("ID", primary_key=True)
    compra = models.ForeignKey(Compra, on_delete=models.CASCADE, db_column='compra_id')
    cfop = models.ForeignKey(Cfop, on_delete=models.CASCADE, db_column='cfop_id')
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, db_column='produto_id')
    compra_item_qtd = models.DecimalField("Qtde", max_digits=10, decimal_places=2)
    compra_item_preco = models.DecimalField("Preço", max_digits=10, decimal_places=2)
    compra_item_volume = models.IntegerField("Volume")

    class Meta:
        db_table = 'compra_item'
        verbose_name = 'Compra Item'
        verbose_name_plural = 'Compra Itens'

    def __str__(self):
        return f'Item {self.produto.produto_nome} da Compra {self.compra.compra_id}'

class ContaPagar(models.Model):
    conta_pagar_id = models.AutoField(primary_key=True)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, db_column='empresa_id')
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.CASCADE, db_column='fornecedor_id')
    compra = models.ForeignKey(Compra, on_delete=models.CASCADE, db_column='compra_id', null=True)
    plano_conta = models.ForeignKey(PlanoConta, on_delete=models.CASCADE, db_column='plano_conta_id')
    conta_pagar_historico = models.CharField(max_length=255, null=True, blank=True)
    conta_pagar_numero_documento = models.CharField(max_length=50, null=True, blank=True)
    conta_pagar_data_emissao = models.DateField(null=True, blank=True)
    conta_pagar_data_vencimento = models.DateField(null=True, blank=True)
    conta_pagar_valor = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    conta_pagar_portador = models.CharField(max_length=50, null=True, blank=True)
    conta_pagar_nosso_numero = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = 'conta_pagar'
        verbose_name = 'Conta a Pagar'
        verbose_name_plural = 'Contas a Pagar'

    def __str__(self):
        return f'Conta a Pagar {self.conta_pagar_id} - {self.fornecedor.fornecedor_nome}'

class ContasReceber(models.Model):
    contas_receber_id = models.AutoField(primary_key=True)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, db_column='empresa_id')
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, db_column='cliente_id')
    venda = models.ForeignKey('Venda', on_delete=models.CASCADE, db_column='venda_id', null=True, blank=True)
    plano_conta = models.ForeignKey(PlanoConta, on_delete=models.CASCADE, db_column='plano_conta_id')
    contas_receber_historico = models.CharField(max_length=255, null=True, blank=True)
    contas_receber_numero_documento = models.CharField(max_length=50, null=True, blank=True)
    contas_receber_data_emissao = models.DateField(null=True, blank=True)
    contas_receber_data_vencimento = models.DateField(null=True, blank=True)
    contas_receber_valor = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    contas_receber_portador = models.CharField(max_length=50, null=True, blank=True)
    contas_receber_nosso_numero = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = 'contas_receber'
        verbose_name = 'Conta a Receber'
        verbose_name_plural = 'Contas a Receber'    

    def __str__(self):
        return f'Conta a Receber {self.contas_receber_id}'

class Pagamento(models.Model):
    pagamento_id = models.AutoField("ID", primary_key=True)
    conta_pagar = models.ForeignKey(ContaPagar, on_delete=models.CASCADE, db_column='conta_pagar_id')
    pagamento_data_pagamento = models.DateField("Data de Pagamento", null=True, blank=True)
    pagamento_valor_pago = models.DecimalField("Valor Pago", max_digits=10, decimal_places=2, null=True, blank=True)
    pagamento_forma_pagamento = models.CharField("Forma de Pagamento", max_length=50, null=True, blank=True)
    pagamento_observacao = models.CharField("Observação", max_length=255, null=True, blank=True)

    class Meta:
        db_table = 'pagamento'
        verbose_name = 'Pagamento'      
        verbose_name_plural = 'Pagamentos'

    def __str__(self):
        return f'Pagamento Nº {self.pagamento_id}'

class Recebimento(models.Model):
    recebimento_id = models.AutoField(primary_key=True)
    contas_receber = models.ForeignKey(ContasReceber, on_delete=models.CASCADE, db_column='contas_receber_id')
    recebimento_data_recebimento = models.DateField(null=True, blank=True)
    recebimento_valor_recebido = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    recebimento_forma_recebimento = models.CharField(max_length=50, null=True, blank=True)
    recebimento_observacao = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = 'recebimento'
        verbose_name = 'Recebimento'
        verbose_name_plural = 'Recebimentos'

    def __str__(self):
        return f'Recebimento Nº {self.recebimento_id}'    

class Caixa(models.Model):
    caixa_id = models.AutoField(primary_key=True)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, db_column='empresa_id')
    plano_conta = models.ForeignKey(PlanoConta, on_delete=models.CASCADE, db_column='plano_conta_id')
    caixa_data_emissao = models.DateField(null=True, blank=True)
    caixa_historico = models.CharField(max_length=255, null=True, blank=True)
    caixa_valor_entrada = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    caixa_valor_saida = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        db_table = 'caixa'
        verbose_name = 'caixa'
        verbose_name_plural = 'Caixa'
        ordering = ['-caixa_data_emissao']

    def __str__(self):
        """Retorna uma representação legível do lançamento de caixa."""
        if self.caixa_data_emissao:
            # Formata a data para o padrão brasileiro
            data_formatada = self.caixa_data_emissao.strftime('%d/%m/%Y')
            return f"{data_formatada} - {self.caixa_historico or 'Sem histórico'}"
        return f"Lançamento {self.caixa_id}"

    @property
    def saldo(self):
        """Calcula o saldo do movimento (entrada - saída)."""
        return self.caixa_valor_entrada - self.caixa_valor_saida

class Romaneio(models.Model):
    romaneio_id = models.AutoField("ID", primary_key=True)
    compra = models.ForeignKey(Compra, on_delete=models.CASCADE, db_column='compra_id', null=True, blank=True)
    funcionario = models.ForeignKey(Funcionario, on_delete=models.CASCADE, db_column='funcionario_id')
    veiculo = models.ForeignKey(Veiculo, on_delete=models.CASCADE, db_column='veiculo_id')
    romaneio_data_emissao = models.DateField("Data de Emissão", null=True, blank=True)
    produto_item_qtd = models.FloatField("Quantidade", null=True, blank=True)
    produto_item_volume = models.FloatField("Volume", null=True, blank=True)

    class StatusChoices(models.TextChoices):
        ABERTO = 'ABERTO', 'ABERTO'
        FECHADO = 'FECHADO', 'FECHADO'

    status = models.CharField(
        "Status",
        max_length=10,
        choices=StatusChoices.choices,
        default=StatusChoices.ABERTO,
        help_text="Status definido manualmente: Aberto ou Fechado"
    )

    class Meta:
        db_table = 'romaneio'
        verbose_name = 'Romaneio'
        verbose_name_plural = 'Romaneios'

    def __str__(self):
        return f"{self.compra} - {self.funcionario} - {self.veiculo}"

class Venda(models.Model):
    venda_id = models.AutoField(primary_key=True)
    romaneio = models.ForeignKey(Romaneio, on_delete=models.CASCADE, db_column='romaneio_id', null=True, blank=True)
    plano_conta = models.ForeignKey(PlanoConta, on_delete=models.CASCADE, db_column='plano_conta_id', verbose_name="Plano de Contas")
    venda_data_emissao = models.DateField("Data de Emissão",)
    venda_data_vencimento = models.DateField("Data de Vencimento",)

    class Meta:
        db_table = 'venda'
        verbose_name = 'Venda'
        verbose_name_plural = 'Vendas'
    
    def __str__(self):
        return f"{self.romaneio} - {self.venda_data_emissao} - {self.venda_data_vencimento}"
    
    def calcular_total_receber(self):
        from django.db.models import Sum, F, DecimalField, ExpressionWrapper
        total = VendaItem.objects.filter(
            venda=self,
            cfop__cfop_integracao__icontains="receber"
        ).aggregate(
            total=Sum(
                ExpressionWrapper(
                    F('venda_item_qtd') * F('venda_item_preco'),
                    output_field=DecimalField()
                )
            )
        )['total'] or 0
        return total

class VendaItem(models.Model):
    vend_item_id = models.AutoField(primary_key=True)
    venda = models.ForeignKey(Venda, on_delete=models.CASCADE, db_column='venda_id', null=True, blank=True)
    cfop = models.ForeignKey(Cfop, on_delete=models.CASCADE, db_column='cfop_id')
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, db_column='cliente_id')
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, db_column='produto_id')
    plano_conta = models.ForeignKey(PlanoConta, on_delete=models.CASCADE, db_column='plano_conta_id')
    venda_item_qtd = models.DecimalField("Quantidade", max_digits=10, decimal_places=2)
    venda_item_preco = models.DecimalField("Preço", max_digits=10, decimal_places=2)
    venda_item_volume = models.IntegerField("Volume",   null=True, blank=True)

    class Meta:
        db_table = 'venda_item'
        verbose_name = 'Venda Item'
        verbose_name_plural = 'Venda Itens' 

class ConvenioGrupoMercadoria(models.Model):
    convenio_grupo_mercadoria_id = models.AutoField(primary_key=True)
    convenio = models.ForeignKey(Convenio, on_delete=models.CASCADE, db_column='convenio_id')
    grupo_mercadoria = models.ForeignKey(GrupoMercadoria, on_delete=models.CASCADE, db_column='grupo_mercadoria_id')

    class Meta:
        db_table = 'convenio_grupo_mercadoria'
        verbose_name = 'Convênio por Grupo de Mercadoria'
        verbose_name_plural = 'Convênios por Grupo de Mercadoria'

        # ADICIONE ESTE MÉTODO

    def __str__(self):
        return f"{self.convenio} - {self.grupo_mercadoria}"

class ClienteConvenioGrupoMercadoria(models.Model):
    cliente_convenio_grupo_mercadoria_id = models.AutoField(primary_key=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, db_column='cliente_id')
    convenio_grupo_mercadoria = models.ForeignKey(ConvenioGrupoMercadoria, on_delete=models.CASCADE,
                                                  db_column='convenio_grupo_mercadoria_id')

    class Meta:
        db_table = 'cliente_convenio_grupo_mercadoria'
        verbose_name = 'Convênio do Cliente'
        verbose_name_plural = 'Convênios dos Clientes'

    def __str__(self):
        return f"{self.cliente} -> {self.convenio_grupo_mercadoria}"

_PLANO_CONTA_PADRAO_CACHE = None

def _obter_plano_para_pagamento(conta_pagar):
    if conta_pagar is None:
        return None
    if getattr(conta_pagar, 'plano_conta_id', None):
        return conta_pagar.plano_conta
    compra = getattr(conta_pagar, 'compra', None)
    if compra and getattr(compra, 'plano_conta_id', None):
        return compra.plano_conta
    global _PLANO_CONTA_PADRAO_CACHE
    if _PLANO_CONTA_PADRAO_CACHE is None:
        _PLANO_CONTA_PADRAO_CACHE = PlanoConta.objects.filter(pk=1).first()
    return _PLANO_CONTA_PADRAO_CACHE

def _historico_pagamento(pagamento):
    conta = pagamento.conta_pagar
    numero = getattr(conta, 'conta_pagar_numero_documento', None) or conta.conta_pagar_id
    return f'Pagamento #{pagamento.pk} da conta {numero}'

def _remover_pagamento_do_caixa(pagamento):
    conta = getattr(pagamento, 'conta_pagar', None)
    if not getattr(conta, 'pk', None) or not getattr(conta, 'empresa_id', None):
        return
    historico = _historico_pagamento(pagamento)
    Caixa.objects.filter(empresa=conta.empresa, caixa_historico=historico).delete()

def _registrar_pagamento_no_caixa(pagamento):
    conta = getattr(pagamento, 'conta_pagar', None)
    if not getattr(conta, 'pk', None) or not getattr(conta, 'empresa_id', None):
        _remover_pagamento_do_caixa(pagamento)
        return
    valor = pagamento.pagamento_valor_pago or Decimal('0')
    if valor <= Decimal('0'):
        _remover_pagamento_do_caixa(pagamento)
        return
    plano = _obter_plano_para_pagamento(conta)
    if plano is None:
        return
    historico = _historico_pagamento(pagamento)
    data_pagamento = pagamento.pagamento_data_pagamento or timezone.localdate()
    Caixa.objects.update_or_create(
        empresa=conta.empresa,
        caixa_historico=historico,
        defaults={
            'plano_conta': plano,
            'caixa_data_emissao': data_pagamento,
            'caixa_valor_entrada': Decimal('0'),
            'caixa_valor_saida': valor,
        },
    )

@receiver(post_save, sender=Pagamento)
def sincronizar_caixa_apos_salvar_pagamento(sender, instance, **kwargs):
    _registrar_pagamento_no_caixa(instance)

@receiver(post_delete, sender=Pagamento)
def sincronizar_caixa_apos_excluir_pagamento(sender, instance, **kwargs):
    _remover_pagamento_do_caixa(instance)

PAGAMENTO_HISTORICO_PATTERN = re.compile(r'^Pagamento #(\d+)')

@receiver(post_delete, sender=Caixa)
def sincronizar_pagamento_ao_excluir_caixa(sender, instance, **kwargs):
    historico = (instance.caixa_historico or '').strip()
    match = PAGAMENTO_HISTORICO_PATTERN.match(historico)
    if not match:
        return
    pagamento_id = match.group(1)
    try:
        pagamento = Pagamento.objects.select_related('conta_pagar').get(pk=pagamento_id)
    except Pagamento.DoesNotExist:
        return
    conta = pagamento.conta_pagar
    if conta.empresa_id != instance.empresa_id:
        return

    valor_pago_atual = pagamento.pagamento_valor_pago or Decimal('0')
    valor_saida = instance.caixa_valor_saida or Decimal('0')
    valor_liquido = valor_saida

    if valor_liquido <= Decimal('0'):
        pagamento.delete()
        return

    novo_valor = valor_pago_atual - valor_liquido
    if novo_valor <= Decimal('0'):
        pagamento.delete()
        return

    pagamento.pagamento_valor_pago = novo_valor
    pagamento.save(update_fields=['pagamento_valor_pago'])


