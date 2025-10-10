from django.contrib import admin
from django.db.models import Sum, F, DecimalField, ExpressionWrapper
from .models import CompraItem
from .forms import CompraItemForm


@admin.register(CompraItem)
class CompraItemAdmin(admin.ModelAdmin):
    form = CompraItemForm
    
    # Campos que seráo exibidos na lista
    list_display = (
        'get_empresa_nome',
        'get_compra_info',
        'produto',
        'compra_item_qtd',
        'compra_item_preco',
        'valor_total'
    )

    # Adiciona campos de busca
    search_fields = ('compra__empresa__empresa_nome', 'produto__produto_nome', 'compra__compra_numero')

    # Adiciona filtros na lateral direita
    list_filter = ('compra__empresa', 'produto', 'cfop')

    # Melhora a performance, buscando os objetos relacionados em uma única query
    list_select_related = ('compra__empresa', 'compra', 'produto', 'cfop')

    # Deixa o campo calculado como "apenas leitura" na tela de edição do item
    readonly_fields = ('valor_total',)

    def get_empresa_nome(self, obj):
        if obj.compra and obj.compra.empresa:
            return obj.compra.empresa.empresa_nome
        return "N/A"

    get_empresa_nome.short_description = 'Empresa'  # Nome da coluna
    get_empresa_nome.admin_order_field = 'compra__empresa__empresa_nome'  # Permite ordenar pela coluna

    # método para exibir o número da compra e o fornecedor
    def get_compra_info(self, obj):
        if obj.compra:
            return f"Compra Número {obj.compra.compra_numero} ({obj.compra.fornecedor.fornecedor_nome})"
        return "N/A"
    get_compra_info.short_description = 'Compra (Fornecedor)' # Nome da coluna
    get_compra_info.admin_order_field = 'compra__compra_numero' # Permite ordenar por esta coluna

    # método para calcular e exibir o valor total do item (Qtd * Preço)
    def valor_total(self, obj):
        if obj.compra_item_qtd is None or obj.compra_item_preco is None:
            return "R$ 0,00"
        total = obj.compra_item_qtd * obj.compra_item_preco
        return f'R$ {total:,.2f}'.replace(",", "X").replace(".", ",").replace("X", ".")
    valor_total.short_description = 'Valor Total (R$)' # Nome da coluna