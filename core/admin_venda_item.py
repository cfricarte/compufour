from django.contrib import admin
from django.db.models import Sum, F, DecimalField, ExpressionWrapper
from .models import VendaItem, PlanoConta
from .forms import VendaItemForm


@admin.register(VendaItem)
class VendaItemAdmin(admin.ModelAdmin):
    form = VendaItemForm
    
    # Campos que serão exibidos na lista
    list_display = (
        'get_venda_info',
        'cliente',
        'produto',
        'venda_item_qtd',
        'venda_item_preco',
        'valor_total',
        'venda_item_volume',
    )

    # Adiciona campos de busca
    search_fields = (
        'venda__venda_id',
        'venda__romaneio__romaneio_data',
        'cliente__cliente_nome',
        'produto__produto_nome',
    )

    # Adiciona filtros na lateral direita
    list_filter = ('cliente', 'produto', 'cfop', 'venda__venda_data_emissao')

    # Melhora a performance, buscando os objetos relacionados em uma única query
    list_select_related = ('venda', 'venda__romaneio', 'cliente', 'produto', 'cfop')

    # Deixa o campo calculado como "apenas leitura" na tela de edição do item
    readonly_fields = ('valor_total',)

    # Campos exibidos no formulário de edição
    fields = (
        'venda',
        'plano_conta',
        'cliente',
        'produto',
        'cfop',
        'venda_item_qtd',
        'venda_item_preco',
        'valor_total',
        'venda_item_volume',
    )

    # Método para exibir informações da venda
    def get_venda_info(self, obj):
        if obj.venda:
            venda_id = obj.venda.venda_id
            if obj.venda.romaneio:
                data_emissao = obj.venda.romaneio.romaneio_data_emissao
                if data_emissao:
                    return f"Venda #{venda_id} - Romaneio {data_emissao.strftime('%d/%m/%Y')}"
                return f"Venda #{venda_id} - Romaneio #{obj.venda.romaneio.romaneio_id}"
            return f"Venda #{venda_id}"
        return "N/A"
    
    get_venda_info.short_description = 'Venda'
    get_venda_info.admin_order_field = 'venda__venda_id'

    # Método para calcular e exibir o valor total do item (Qtd * Preço)
    def valor_total(self, obj):
        if obj.venda_item_qtd and obj.venda_item_preco:
            total = obj.venda_item_qtd * obj.venda_item_preco
            return f'R$ {total:,.2f}'.replace(",", "X").replace(".", ",").replace("X", ".")
        return "R$ 0,00"
    
    valor_total.short_description = 'Valor Total (R$)'
    
    # Configuração para usar template customizado
    change_form_template = 'admin/core/vendaitem/change_form.html'
    add_form_template = 'admin/core/vendaitem/change_form.html'
    
    class Media:
        js = ('core/js/vendaitem_change_form.js',)