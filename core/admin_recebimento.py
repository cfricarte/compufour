from django.contrib import admin
from django.utils.html import format_html
from rangefilter.filters import DateRangeFilter
from .models import Recebimento


@admin.register(Recebimento)
class RecebimentoAdmin(admin.ModelAdmin):
    """
    Configuração do admin para Recebimento com list_display, filtros e busca.
    """
    
    # Campos exibidos na lista
    list_display = (
        'recebimento_id',
        'get_conta_info',
        'get_cliente',
        'recebimento_data_recebimento',
        'get_valor_formatado',
        'recebimento_forma_recebimento',
        'get_status_badge',
    )
    
    # Filtros na barra lateral
    list_filter = (
        ('recebimento_data_recebimento', DateRangeFilter),
        'recebimento_forma_recebimento',
        'contas_receber__cliente',
        'contas_receber__empresa',
    )
    
    # Campos de busca
    search_fields = (
        'recebimento_id',
        'contas_receber__contas_receber_numero_documento',
        'contas_receber__cliente__cliente_nome',
        'contas_receber__contas_receber_historico',
        'recebimento_observacao',
    )
    
    # Campos somente leitura (calculados)
    readonly_fields = ('get_info_conta_completa',)
    
    # Campos exibidos no formulário
    fields = (
        'contas_receber',
        'get_info_conta_completa',
        'recebimento_data_recebimento',
        'recebimento_valor_recebido',
        'recebimento_forma_recebimento',
        'recebimento_observacao',
    )
    
    # Ordenação padrão
    ordering = ('-recebimento_data_recebimento', '-recebimento_id')
    
    # Melhorar performance com select_related
    list_select_related = ('contas_receber', 'contas_receber__cliente', 'contas_receber__empresa')
    
    # Paginação
    list_per_page = 50
    
    # Ações em massa
    actions = ['marcar_como_recebido_hoje']
    
    # ===== MÉTODOS CUSTOMIZADOS =====
    
    def get_conta_info(self, obj):
        """Exibe informações da conta a receber."""
        if obj.contas_receber:
            doc = obj.contas_receber.contas_receber_numero_documento or 'S/N'
            return f"Doc: {doc}"
        return "N/A"
    get_conta_info.short_description = 'Documento'
    get_conta_info.admin_order_field = 'contas_receber__contas_receber_numero_documento'
    
    def get_cliente(self, obj):
        """Exibe o nome do cliente."""
        if obj.contas_receber and obj.contas_receber.cliente:
            return obj.contas_receber.cliente.cliente_nome
        return "N/A"
    get_cliente.short_description = 'Cliente'
    get_cliente.admin_order_field = 'contas_receber__cliente__cliente_nome'
    
    def get_valor_formatado(self, obj):
        """Exibe o valor recebido formatado em reais."""
        if obj.recebimento_valor_recebido:
            valor = obj.recebimento_valor_recebido
            return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return "R$ 0,00"
    get_valor_formatado.short_description = 'Valor Recebido'
    get_valor_formatado.admin_order_field = 'recebimento_valor_recebido'
    
    def get_status_badge(self, obj):
        """Exibe um badge colorido de status."""
        if obj.recebimento_data_recebimento and obj.recebimento_valor_recebido:
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
        """Exibe informações completas da conta a receber no formulário."""
        if obj.contas_receber:
            conta = obj.contas_receber
            info_parts = []
            
            if conta.cliente:
                info_parts.append(f"<strong>Cliente:</strong> {conta.cliente.cliente_nome}")
            
            if conta.contas_receber_numero_documento:
                info_parts.append(f"<strong>Documento:</strong> {conta.contas_receber_numero_documento}")
            
            if conta.contas_receber_valor:
                valor = f"R$ {conta.contas_receber_valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                info_parts.append(f"<strong>Valor da Conta:</strong> {valor}")
            
            if conta.contas_receber_data_vencimento:
                data_venc = conta.contas_receber_data_vencimento.strftime('%d/%m/%Y')
                info_parts.append(f"<strong>Vencimento:</strong> {data_venc}")
            
            if conta.contas_receber_historico:
                info_parts.append(f"<strong>Histórico:</strong> {conta.contas_receber_historico}")
            
            return format_html("<br>".join(info_parts))
        return "N/A"
    get_info_conta_completa.short_description = 'Informações da Conta'
    
    # ===== AÇÕES EM MASSA =====
    
    def marcar_como_recebido_hoje(self, request, queryset):
        """Marca os recebimentos selecionados com a data de hoje."""
        from django.utils import timezone
        hoje = timezone.now().date()
        
        count = queryset.update(recebimento_data_recebimento=hoje)
        
        self.message_user(
            request,
            f'{count} recebimento(s) marcado(s) como recebido(s) em {hoje.strftime("%d/%m/%Y")}.'
        )
    marcar_como_recebido_hoje.short_description = "✓ Marcar como recebido hoje"