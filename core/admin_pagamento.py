from django.contrib import admin
from django.utils.html import format_html
from decimal import Decimal
from rangefilter.filters import DateRangeFilter
from .models import Pagamento


@admin.register(Pagamento)
class PagamentoAdmin(admin.ModelAdmin):
    """
    Configuração do admin para Pagamento com list_display, filtros e busca completos.
    """
    
    # Campos exibidos na lista
    list_display = (
        'pagamento_id',
        'get_conta_info',
        'get_fornecedor',
        'get_empresa',
        'pagamento_data_pagamento',
        'get_valor_formatado',
        'pagamento_forma_pagamento',
        'get_status_badge',
    )
    
    # Filtros na barra lateral
    list_filter = (
        ('pagamento_data_pagamento', DateRangeFilter),
        'pagamento_forma_pagamento',
        'conta_pagar__fornecedor',
        'conta_pagar__empresa',
        'conta_pagar__plano_conta',
    )
    
    # Campos de busca
    search_fields = (
        'pagamento_id',
        'conta_pagar__conta_pagar_numero_documento',
        'conta_pagar__fornecedor__fornecedor_nome',
        'conta_pagar__conta_pagar_historico',
        'pagamento_observacao',
    )
    
    # Campos somente leitura (calculados)
    readonly_fields = ('get_info_conta_completa',)
    
    # Campos exibidos no formulário
    fields = (
        'conta_pagar',
        'get_info_conta_completa',
        'pagamento_data_pagamento',
        'pagamento_valor_pago',
        'pagamento_forma_pagamento',
        'pagamento_observacao',
    )
    
    # Hierarquia de data
    date_hierarchy = 'pagamento_data_pagamento'
    
    # Ordenação padrão
    ordering = ('-pagamento_data_pagamento', '-pagamento_id')
    
    # Melhorar performance com select_related
    list_select_related = ('conta_pagar', 'conta_pagar__fornecedor', 'conta_pagar__empresa', 'conta_pagar__plano_conta')
    
    # Paginação
    list_per_page = 50
    
    # Ações em massa
    actions = ['marcar_como_pago_hoje']
    
    # Valor padrão para campos vazios
    empty_value_display = '--'
    
    # ===== MÉTODOS CUSTOMIZADOS =====
    
    def get_conta_info(self, obj):
        """Exibe informações da conta a pagar."""
        if obj.conta_pagar:
            doc = obj.conta_pagar.conta_pagar_numero_documento or 'S/N'
            return f"Doc: {doc}"
        return "N/A"
    get_conta_info.short_description = 'Documento'
    get_conta_info.admin_order_field = 'conta_pagar__conta_pagar_numero_documento'
    
    def get_fornecedor(self, obj):
        """Exibe o nome do fornecedor."""
        if obj.conta_pagar and obj.conta_pagar.fornecedor:
            return obj.conta_pagar.fornecedor.fornecedor_nome
        return "N/A"
    get_fornecedor.short_description = 'Fornecedor'
    get_fornecedor.admin_order_field = 'conta_pagar__fornecedor__fornecedor_nome'
    
    def get_empresa(self, obj):
        """Exibe o nome da empresa."""
        if obj.conta_pagar and obj.conta_pagar.empresa:
            return obj.conta_pagar.empresa.empresa_nome
        return "N/A"
    get_empresa.short_description = 'Empresa'
    get_empresa.admin_order_field = 'conta_pagar__empresa__empresa_nome'
    
    def get_valor_formatado(self, obj):
        """Exibe o valor pago formatado em reais."""
        if obj.pagamento_valor_pago:
            valor = obj.pagamento_valor_pago
            return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return "R$ 0,00"
    get_valor_formatado.short_description = 'Valor Pago'
    get_valor_formatado.admin_order_field = 'pagamento_valor_pago'
    
    def get_status_badge(self, obj):
        """Exibe um badge colorido de status."""
        if obj.pagamento_data_pagamento and obj.pagamento_valor_pago:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; '
                'border-radius: 3px; font-size: 11px; font-weight: bold;">✓ PAGO</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #ffc107; color: black; padding: 3px 10px; '
                'border-radius: 3px; font-size: 11px; font-weight: bold;">⏳ PENDENTE</span>'
            )
    get_status_badge.short_description = 'Status'
    
    def get_info_conta_completa(self, obj):
        """Exibe informações completas da conta a pagar no formulário."""
        if obj.conta_pagar:
            conta = obj.conta_pagar
            info_parts = []
            
            if conta.empresa:
                info_parts.append(f"<strong>Empresa:</strong> {conta.empresa.empresa_nome}")
            
            if conta.fornecedor:
                info_parts.append(f"<strong>Fornecedor:</strong> {conta.fornecedor.fornecedor_nome}")
            
            if conta.conta_pagar_numero_documento:
                info_parts.append(f"<strong>Documento:</strong> {conta.conta_pagar_numero_documento}")
            
            if conta.conta_pagar_valor:
                valor = f"R$ {conta.conta_pagar_valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                info_parts.append(f"<strong>Valor da Conta:</strong> {valor}")
            
            if conta.conta_pagar_data_vencimento:
                data_venc = conta.conta_pagar_data_vencimento.strftime('%d/%m/%Y')
                info_parts.append(f"<strong>Vencimento:</strong> {data_venc}")
            
            if conta.plano_conta:
                info_parts.append(f"<strong>Plano de Contas:</strong> {conta.plano_conta}")
            
            if conta.conta_pagar_historico:
                info_parts.append(f"<strong>Histórico:</strong> {conta.conta_pagar_historico}")
            
            if conta.compra:
                info_parts.append(f"<strong>Compra:</strong> #{conta.compra.compra_id} - Nota {conta.compra.compra_numero}")
            
            return format_html("<br>".join(info_parts))
        return "N/A"
    get_info_conta_completa.short_description = 'Informações da Conta'
    
    # ===== AÇÕES EM MASSA =====
    
    def marcar_como_pago_hoje(self, request, queryset):
        """Marca os pagamentos selecionados com a data de hoje."""
        from django.utils import timezone
        hoje = timezone.now().date()
        
        count = queryset.update(pagamento_data_pagamento=hoje)
        
        self.message_user(
            request,
            f'{count} pagamento(s) marcado(s) como pago(s) em {hoje.strftime("%d/%m/%Y")}.'
        )
    marcar_como_pago_hoje.short_description = "✓ Marcar como pago hoje"