# core/signals.py

from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Compra, CompraItem, ContaPagar, Venda, VendaItem, ContasReceber, PlanoConta, Caixa

# -----------------------------------------------------------------------------
# LÓGICA CENTRALIZADA
# Esta função auxiliar contém toda a lógica para evitar repetição de código.
# -----------------------------------------------------------------------------
def _atualizar_conta_para_compra(compra_instance):
    """
    Função auxiliar que recebe uma instância de Compra e cria/atualiza/deleta
    as Contas a Pagar correspondentes conforme o prazo de pagamento.
    """
    valor_total = compra_instance.calcular_total_pagar()
    contas_existentes = ContaPagar.objects.filter(compra=compra_instance)

    if valor_total is None or valor_total <= 0:
        contas_existentes.delete()
        return

    plano_conta_utilizada = compra_instance.plano_conta
    if plano_conta_utilizada is None:
        try:
            plano_conta_utilizada = PlanoConta.objects.get(pk=1)
        except PlanoConta.DoesNotExist:
            print(f"AVISO: Plano de Contas padrão (ID=1) não encontrado. Compra ID {compra_instance.pk} não gerou contas a pagar.")
            return

    data_base = compra_instance.compra_data_base or compra_instance.compra_data_entrada
    if not data_base:
        contas_existentes.delete()
        return

    prazo_bruto = compra_instance.compra_prazo_pagamento or ''
    prazos = []
    for parte in prazo_bruto.split(','):
        parte = parte.strip()
        if not parte:
            continue
        try:
            prazos.append(int(parte))
        except ValueError:
            continue
    if not prazos:
        prazos = [0]

    quantize_unit = Decimal('0.01')
    valor_total_decimal = Decimal(valor_total).quantize(quantize_unit, rounding=ROUND_HALF_UP)
    numero_parcelas = len(prazos)

    valor_base_parcela = (valor_total_decimal / numero_parcelas).quantize(quantize_unit, rounding=ROUND_HALF_UP)
    valores_parcelas = [valor_base_parcela for _ in prazos]
    ajuste = valor_total_decimal - sum(valores_parcelas)
    if ajuste:
        valores_parcelas[-1] = (valores_parcelas[-1] + ajuste).quantize(quantize_unit, rounding=ROUND_HALF_UP)

    contas_existentes.delete()

    historico_base = f"Referente à compra Número {compra_instance.compra_numero}"
    for indice, (prazo_dias, valor_parcela) in enumerate(zip(prazos, valores_parcelas), start=1):
        prazo_dias = max(prazo_dias, 0)
        data_vencimento = data_base + timedelta(days=prazo_dias)
        ContaPagar.objects.create(
            empresa=compra_instance.empresa,
            fornecedor=compra_instance.fornecedor,
            compra=compra_instance,
            plano_conta=plano_conta_utilizada,
            conta_pagar_historico=f"{historico_base} - Parcela {indice}/{numero_parcelas}",
            conta_pagar_numero_documento=f"{compra_instance.compra_numero}-{indice:02d}",
            conta_pagar_data_emissao=data_base,
            conta_pagar_data_vencimento=data_vencimento,
            conta_pagar_valor=valor_parcela,
        )

# -----------------------------------------------------------------------------
# ATUALIZAÇÃO DE PREÇO DE CUSTO DO PRODUTO
# -----------------------------------------------------------------------------
def _atualizar_preco_custo_produto(compra_item_instance):
    """
    Atualiza o preço de custo do produto quando um item de compra é salvo.
    O preço de custo sempre reflete o preço da última compra.
    """
    try:
        if compra_item_instance.produto and compra_item_instance.compra_item_preco:
            produto = compra_item_instance.produto
            preco_compra = compra_item_instance.compra_item_preco
            
            # Atualiza o preço de custo do produto com o preço da compra
            produto.produto_preco_custo = preco_compra
            produto.save(update_fields=['produto_preco_custo'])
            
            print(f"✅ Preço de custo do produto '{produto.produto_nome}' atualizado para R$ {preco_compra}")
    except Exception as e:
        print(f"⚠️ Erro ao atualizar preço de custo do produto: {e}")


# -----------------------------------------------------------------------------
# SINAIS (RECEIVERS)
# Cada sinal agora simplesmente chama a função auxiliar centralizada.
# -----------------------------------------------------------------------------

@receiver(post_save, sender=Compra)
def atualizar_conta_apos_salvar_compra(sender, instance, **kwargs):
    """Sinal para quando a Compra principal é salva."""
    _atualizar_conta_para_compra(instance)


@receiver(post_save, sender=CompraItem)
def atualizar_conta_apos_salvar_item(sender, instance, **kwargs):
    """NOVO SINAL: para quando um CompraItem é criado ou atualizado."""
    if instance.compra:
        _atualizar_conta_para_compra(instance.compra)
    
    # Atualiza o preço de custo do produto com base no preço da compra
    _atualizar_preco_custo_produto(instance)


@receiver(post_delete, sender=CompraItem)
def atualizar_conta_apos_deletar_item(sender, instance, **kwargs):
    """NOVO SINAL: para quando um CompraItem é deletado."""
    # Verificar se a compra ainda existe (não foi deletada em cascata)
    if instance.compra_id:
        try:
            compra = Compra.objects.get(pk=instance.compra_id)
            _atualizar_conta_para_compra(compra)
        except Compra.DoesNotExist:
            # Compra foi deletada, não há nada a fazer
            pass


# -----------------------------------------------------------------------------
# LÓGICA PARA VENDA -> CONTAS A RECEBER
# Similar à lógica de Compra -> Contas a Pagar
# -----------------------------------------------------------------------------
def _atualizar_conta_receber_para_venda(venda_instance):
    """
    Função auxiliar que recebe uma instância de Venda e cria/atualiza/deleta
    as Contas a Receber correspondentes.
    
    Gera uma conta a receber para cada combinação única de (cliente, plano_conta)
    nos itens da venda que tenham CFOP com "receber" na integração.
    """
    from django.db.models import Sum, F, DecimalField, ExpressionWrapper
    from .models import Empresa
    
    contas_existentes = ContasReceber.objects.filter(venda=venda_instance)

    # Buscar empresa através do romaneio->compra, ou usar a primeira empresa cadastrada
    empresa = None
    if venda_instance.romaneio and venda_instance.romaneio.compra:
        empresa = venda_instance.romaneio.compra.empresa
    
    # Se não encontrou empresa através do romaneio, tenta buscar a primeira empresa cadastrada
    if not empresa:
        try:
            empresa = Empresa.objects.first()
        except:
            pass
    
    if not empresa:
        print(f"AVISO: Nenhuma empresa encontrada para a Venda ID {venda_instance.pk}. Contas a receber não foram geradas.")
        contas_existentes.delete()
        return

    data_base = venda_instance.venda_data_emissao
    if not data_base:
        contas_existentes.delete()
        return

    # Buscar plano de contas padrão para fallback
    plano_conta_padrao = None
    if venda_instance.romaneio and venda_instance.romaneio.compra:
        plano_conta_padrao = venda_instance.romaneio.compra.plano_conta
    if plano_conta_padrao is None:
        try:
            plano_conta_padrao = PlanoConta.objects.get(pk=1)
        except PlanoConta.DoesNotExist:
            print(f"AVISO: Plano de Contas padrão (ID=1) não encontrado.")
            plano_conta_padrao = None

    # Buscar todos os itens da venda com CFOP de "receber"
    itens_receber = venda_instance.vendaitem_set.filter(
        cfop__cfop_integracao__icontains="receber"
    ).select_related('cliente', 'plano_conta', 'cfop')

    print(f"DEBUG: Venda ID {venda_instance.pk} - Total de itens: {venda_instance.vendaitem_set.count()}")
    print(f"DEBUG: Venda ID {venda_instance.pk} - Itens com CFOP 'receber': {itens_receber.count()}")
    
    if itens_receber.exists():
        for item in itens_receber:
            print(f"DEBUG: Item - Cliente: {item.cliente}, CFOP: {item.cfop.cfop_codigo}, Integração: {item.cfop.cfop_integracao}")

    if not itens_receber.exists():
        print(f"AVISO: Venda ID {venda_instance.pk} não possui itens com CFOP de 'receber'. Contas a receber não foram geradas.")
        contas_existentes.delete()
        return

    # Calcular data de vencimento
    data_vencimento = venda_instance.venda_data_vencimento
    if data_vencimento and data_base:
        prazo_dias = max(0, (data_vencimento - data_base).days)
    else:
        prazo_dias = 0
    
    data_venc = data_base + timedelta(days=prazo_dias)

    # Deletar contas existentes antes de criar novas
    contas_existentes.delete()

    # Criar uma conta a receber para CADA ITEM (SEM AGRUPAR)
    quantize_unit = Decimal('0.01')
    numero_venda = f"V{venda_instance.venda_id}"
    
    print(f"DEBUG: Venda ID {venda_instance.pk} - Criando {itens_receber.count()} contas a receber (uma por item)...")
    
    for idx, item in enumerate(itens_receber, start=1):
        if not item.cliente:
            print(f"DEBUG: Item {idx} - Sem cliente, pulando...")
            continue
            
        # Usar plano_conta do item, ou padrão
        plano = item.plano_conta or plano_conta_padrao
        if not plano:
            print(f"DEBUG: Item {idx} - Sem plano de contas, pulando...")
            continue
        
        # Calcular valor do item
        qtd = item.venda_item_qtd or Decimal('0')
        preco = item.venda_item_preco or Decimal('0')
        valor_item = (qtd * preco).quantize(quantize_unit, rounding=ROUND_HALF_UP)
        
        if valor_item <= 0:
            print(f"DEBUG: Item {idx} (ID {item.pk}) - Valor zero ou negativo ({valor_item}), pulando...")
            continue
        
        # Criar histórico detalhado com informações do item
        produto_nome = item.produto.produto_nome if item.produto else "Produto não informado"
        romaneio_info = str(venda_instance.romaneio) if venda_instance.romaneio else "Venda sem romaneio"
        historico = (
            f"{romaneio_info} "
            f"- Venda ID {venda_instance.venda_id} - Item ID {item.pk} "
            f"- Cliente: {item.cliente.cliente_nome} - Produto: {produto_nome}"
        )
        numero_doc = f"{numero_venda}-I{item.pk}"
        
        conta_receber = ContasReceber.objects.create(
            empresa=empresa,
            cliente=item.cliente,
            venda=venda_instance,
            plano_conta=plano,
            contas_receber_historico=historico,
            contas_receber_numero_documento=numero_doc,
            contas_receber_data_emissao=data_base,
            contas_receber_data_vencimento=data_venc,
            contas_receber_valor=valor_item,
        )
        print(f"DEBUG: Conta a Receber criada - ID: {conta_receber.pk}, Item ID {item.pk}, Cliente: {item.cliente.cliente_nome}, Produto: {produto_nome}, Valor: R$ {valor_item}")


# -----------------------------------------------------------------------------
# SINAIS PARA VENDA
# -----------------------------------------------------------------------------

@receiver(post_save, sender=Venda)
def atualizar_conta_receber_apos_salvar_venda(sender, instance, **kwargs):
    """Sinal para quando a Venda principal é salva."""
    print(f"========== SIGNAL: Venda ID {instance.pk} foi salva ==========")
    _atualizar_conta_receber_para_venda(instance)


@receiver(post_save, sender=VendaItem)
def atualizar_conta_receber_apos_salvar_item(sender, instance, **kwargs):
    """Sinal para quando um VendaItem é criado ou atualizado."""
    print(f"========== SIGNAL: VendaItem ID {instance.pk} foi salvo (Venda: {instance.venda_id}) ==========")
    if instance.venda:
        # VendaItem vinculado a uma Venda - processa via Venda
        _atualizar_conta_receber_para_venda(instance.venda)
    else:
        # VendaItem standalone - processa diretamente
        print(f"DEBUG: VendaItem ID {instance.pk} é STANDALONE (sem venda)")
        _processar_vendaitem_standalone(instance)


@receiver(post_delete, sender=VendaItem)
def atualizar_conta_receber_apos_deletar_item(sender, instance, **kwargs):
    """Sinal para quando um VendaItem é deletado."""
    # Verificar se a venda ainda existe (não foi deletada em cascata)
    if instance.venda_id:
        try:
            venda = Venda.objects.get(pk=instance.venda_id)
            _atualizar_conta_receber_para_venda(venda)
        except Venda.DoesNotExist:
            # Venda foi deletada, não há nada a fazer
            pass


# -----------------------------------------------------------------------------
# LÓGICA PARA VENDA -> LANÇAMENTO NO CAIXA
# Quando CFOP tem integração com "caixa"
# -----------------------------------------------------------------------------
def _atualizar_lancamento_caixa_para_venda(venda_instance):
    """
    Função auxiliar que recebe uma instância de Venda e cria/atualiza/deleta
    os lançamentos no Caixa correspondentes.
    
    Gera um lançamento de caixa (ENTRADA) para cada combinação única de (cliente, plano_conta)
    nos itens da venda que tenham CFOP com "caixa" na integração.
    """
    from django.db.models import Sum, F, DecimalField, ExpressionWrapper
    from .models import Empresa
    
    # Buscar lançamentos existentes vinculados a esta venda
    # Vamos usar o histórico como identificador (contém "venda ID X")
    lancamentos_existentes = Caixa.objects.filter(
        caixa_historico__icontains=f"venda ID {venda_instance.venda_id}"
    )

    # Buscar empresa através do romaneio->compra, ou usar a primeira empresa cadastrada
    empresa = None
    if venda_instance.romaneio and venda_instance.romaneio.compra:
        empresa = venda_instance.romaneio.compra.empresa
    
    if not empresa:
        try:
            empresa = Empresa.objects.first()
        except:
            pass
    
    if not empresa:
        print(f"AVISO: Nenhuma empresa encontrada para a Venda ID {venda_instance.pk}. Lançamentos no caixa não foram gerados.")
        lancamentos_existentes.delete()
        return

    data_emissao = venda_instance.venda_data_emissao
    if not data_emissao:
        print(f"AVISO: Venda ID {venda_instance.pk} sem data de emissão. Lançamentos no caixa não foram gerados.")
        lancamentos_existentes.delete()
        return

    # Buscar plano de contas padrão para fallback
    plano_conta_padrao = venda_instance.plano_conta
    if plano_conta_padrao is None:
        if venda_instance.romaneio and venda_instance.romaneio.compra:
            plano_conta_padrao = venda_instance.romaneio.compra.plano_conta
    if plano_conta_padrao is None:
        try:
            plano_conta_padrao = PlanoConta.objects.get(pk=1)
        except PlanoConta.DoesNotExist:
            print(f"AVISO: Plano de Contas padrão não encontrado.")
            plano_conta_padrao = None

    # Buscar todos os itens da venda com CFOP de "caixa"
    itens_caixa = venda_instance.vendaitem_set.filter(
        cfop__cfop_integracao__icontains="caixa"
    ).select_related('cliente', 'plano_conta', 'cfop')

    print(f"DEBUG CAIXA: Venda ID {venda_instance.pk} - Total de itens: {venda_instance.vendaitem_set.count()}")
    print(f"DEBUG CAIXA: Venda ID {venda_instance.pk} - Itens com CFOP 'caixa': {itens_caixa.count()}")
    
    if itens_caixa.exists():
        for item in itens_caixa:
            print(f"DEBUG CAIXA: Item - Cliente: {item.cliente}, CFOP: {item.cfop.cfop_codigo}, Integração: {item.cfop.cfop_integracao}")

    if not itens_caixa.exists():
        print(f"AVISO: Venda ID {venda_instance.pk} não possui itens com CFOP de 'caixa'. Lançamentos no caixa não foram gerados.")
        lancamentos_existentes.delete()
        return

    # Deletar lançamentos existentes antes de criar novos
    lancamentos_existentes.delete()

    # Criar um lançamento de caixa (ENTRADA) para CADA ITEM (SEM AGRUPAR)
    quantize_unit = Decimal('0.01')
    
    print(f"DEBUG CAIXA: Venda ID {venda_instance.pk} - Criando {itens_caixa.count()} lançamentos no caixa (um por item)...")
    
    for idx, item in enumerate(itens_caixa, start=1):
        if not item.cliente:
            print(f"DEBUG CAIXA: Item {idx} - Sem cliente, pulando...")
            continue
            
        # Usar plano_conta do item, ou padrão
        plano = item.plano_conta or plano_conta_padrao
        if not plano:
            print(f"DEBUG CAIXA: Item {idx} - Sem plano de contas, pulando...")
            continue
        
        # Calcular valor do item
        qtd = item.venda_item_qtd or Decimal('0')
        preco = item.venda_item_preco or Decimal('0')
        valor_item = (qtd * preco).quantize(quantize_unit, rounding=ROUND_HALF_UP)
        
        if valor_item <= 0:
            print(f"DEBUG CAIXA: Item {idx} (ID {item.pk}) - Valor zero ou negativo ({valor_item}), pulando...")
            continue
        
        # Criar histórico detalhado com informações do item
        produto_nome = item.produto.produto_nome if item.produto else "Produto não informado"
        romaneio_info = str(venda_instance.romaneio) if venda_instance.romaneio else "Venda sem romaneio"
        historico = (
            f"{romaneio_info} "
            f"- Venda ID {venda_instance.venda_id} - Item ID {item.pk} "
            f"- Cliente: {item.cliente.cliente_nome} - Produto: {produto_nome}"
        )
        
        lancamento_caixa = Caixa.objects.create(
            empresa=empresa,
            plano_conta=plano,
            caixa_data_emissao=data_emissao,
            caixa_historico=historico,
            caixa_valor_entrada=valor_item,  # ENTRADA no caixa (venda = dinheiro entrando)
            caixa_valor_saida=Decimal('0.00'),
        )
        print(f"DEBUG CAIXA: Lançamento criado - ID: {lancamento_caixa.pk}, Item ID {item.pk}, Cliente: {item.cliente.cliente_nome}, Produto: {produto_nome}, Entrada: R$ {valor_item}")


# -----------------------------------------------------------------------------
# LÓGICA PARA VENDAITEM STANDALONE (sem Venda)
# Processa VendaItems criados diretamente, sem venda associada
# -----------------------------------------------------------------------------
def _processar_vendaitem_standalone(vendaitem_instance):
    """
    Função auxiliar que processa um VendaItem standalone (sem venda vinculada).
    
    Dependendo da integração do CFOP:
    - "caixa" → Cria lançamento no Caixa (entrada)
    - "receber" → Cria Conta a Receber
    """
    from .models import Empresa
    from django.utils import timezone
    
    print(f"DEBUG STANDALONE: Processando VendaItem ID {vendaitem_instance.pk}")
    
    # Verificar se tem CFOP
    if not vendaitem_instance.cfop:
        print(f"AVISO: VendaItem ID {vendaitem_instance.pk} sem CFOP. Não foi processado.")
        return
    
    cfop_integracao = vendaitem_instance.cfop.cfop_integracao or ''
    print(f"DEBUG STANDALONE: CFOP {vendaitem_instance.cfop.cfop_codigo} - Integração: '{cfop_integracao}'")
    
    # Buscar empresa padrão
    empresa = None
    try:
        empresa = Empresa.objects.first()
    except:
        pass
    
    if not empresa:
        print(f"AVISO: Nenhuma empresa encontrada para VendaItem ID {vendaitem_instance.pk}.")
        return
    
    # Verificar cliente e plano_conta
    if not vendaitem_instance.cliente:
        print(f"AVISO: VendaItem ID {vendaitem_instance.pk} sem cliente.")
        return
    
    plano_conta = vendaitem_instance.plano_conta
    if not plano_conta:
        try:
            plano_conta = PlanoConta.objects.first()
        except:
            pass
    
    if not plano_conta:
        print(f"AVISO: VendaItem ID {vendaitem_instance.pk} sem plano de contas.")
        return
    
    # Calcular valor do item
    qtd = vendaitem_instance.venda_item_qtd or Decimal('0')
    preco = vendaitem_instance.venda_item_preco or Decimal('0')
    valor_total = (qtd * preco).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    if valor_total <= 0:
        print(f"AVISO: VendaItem ID {vendaitem_instance.pk} com valor zero ou negativo.")
        return
    
    data_emissao = timezone.now().date()
    cliente = vendaitem_instance.cliente
    
    # Processar baseado na integração do CFOP
    if 'caixa' in cfop_integracao.lower():
        # Criar lançamento no CAIXA
        print(f"DEBUG STANDALONE: Criando lançamento no CAIXA para VendaItem ID {vendaitem_instance.pk}")
        
        # Deletar lançamentos anteriores deste item
        Caixa.objects.filter(
            caixa_historico__icontains=f"VendaItem ID {vendaitem_instance.pk}"
        ).delete()
        
        historico = f"Referente à VendaItem ID {vendaitem_instance.pk} - Cliente: {cliente.cliente_nome} - Produto: {vendaitem_instance.produto}"
        
        lancamento = Caixa.objects.create(
            empresa=empresa,
            plano_conta=plano_conta,
            caixa_data_emissao=data_emissao,
            caixa_historico=historico,
            caixa_valor_entrada=valor_total,
            caixa_valor_saida=Decimal('0.00'),
        )
        print(f"DEBUG STANDALONE: Lançamento no CAIXA criado - ID: {lancamento.pk}, Valor: R$ {valor_total}")
        
    elif 'receber' in cfop_integracao.lower():
        # Criar Conta a RECEBER
        print(f"DEBUG STANDALONE: Criando CONTA A RECEBER para VendaItem ID {vendaitem_instance.pk}")
        
        # Deletar contas anteriores deste item
        ContasReceber.objects.filter(
            contas_receber_historico__icontains=f"VendaItem ID {vendaitem_instance.pk}"
        ).delete()
        
        # Data de vencimento padrão: 30 dias após emissão
        data_vencimento = data_emissao + timedelta(days=30)
        
        historico = f"Referente à VendaItem ID {vendaitem_instance.pk} - Cliente: {cliente.cliente_nome} - Produto: {vendaitem_instance.produto}"
        numero_documento = f"VI-{vendaitem_instance.pk}"
        
        conta = ContasReceber.objects.create(
            empresa=empresa,
            cliente=cliente,
            venda=None,  # VendaItem standalone não tem venda
            plano_conta=plano_conta,
            contas_receber_historico=historico,
            contas_receber_numero_documento=numero_documento,
            contas_receber_data_emissao=data_emissao,
            contas_receber_data_vencimento=data_vencimento,
            contas_receber_valor=valor_total,
        )
        print(f"DEBUG STANDALONE: Conta a Receber criada - ID: {conta.pk}, Valor: R$ {valor_total}, Vencimento: {data_vencimento}")
    
    else:
        print(f"DEBUG STANDALONE: CFOP sem integração 'caixa' ou 'receber'. Nenhum lançamento criado.")


# -----------------------------------------------------------------------------
# SINAIS PARA VENDA -> CAIXA
# -----------------------------------------------------------------------------

@receiver(post_save, sender=Venda)
def atualizar_caixa_apos_salvar_venda(sender, instance, **kwargs):
    """Sinal para quando a Venda principal é salva - gera lançamento no caixa se necessário."""
    print(f"========== SIGNAL CAIXA: Venda ID {instance.pk} foi salva ==========")
    _atualizar_lancamento_caixa_para_venda(instance)


@receiver(post_save, sender=VendaItem)
def atualizar_caixa_apos_salvar_item(sender, instance, **kwargs):
    """Sinal para quando um VendaItem é criado ou atualizado - atualiza caixa."""
    print(f"========== SIGNAL CAIXA: VendaItem ID {instance.pk} foi salvo (Venda: {instance.venda_id}) ==========")
    if instance.venda:
        # VendaItem vinculado a uma Venda - processa via Venda
        _atualizar_lancamento_caixa_para_venda(instance.venda)
    else:
        # VendaItem standalone já é processado por _processar_vendaitem_standalone
        # chamado pelo signal atualizar_conta_receber_apos_salvar_item
        pass


@receiver(post_delete, sender=VendaItem)
def atualizar_caixa_apos_deletar_item(sender, instance, **kwargs):
    """Sinal para quando um VendaItem é deletado - atualiza caixa."""
    if instance.venda_id:
        try:
            venda = Venda.objects.get(pk=instance.venda_id)
            _atualizar_lancamento_caixa_para_venda(venda)
        except Venda.DoesNotExist:
            pass
    else:
        # VendaItem standalone foi deletado - deletar lançamentos associados
        print(f"DEBUG STANDALONE DELETE: Deletando lançamentos do VendaItem ID {instance.pk}")
        Caixa.objects.filter(caixa_historico__icontains=f"VendaItem ID {instance.pk}").delete()
        ContasReceber.objects.filter(contas_receber_historico__icontains=f"VendaItem ID {instance.pk}").delete()