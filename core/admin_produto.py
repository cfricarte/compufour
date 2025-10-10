from django.contrib import admin
from django import forms
from django.db.models import Case, When, Sum, Value, DecimalField, Count, F
from django.utils.html import format_html
from .models import Produto, Cfop


class ProdutoAdminForm(forms.ModelForm):
    class Meta:
        model = Produto
        fields = '__all__'
        widgets = {
            'produto_nome': forms.TextInput(attrs={
                'placeholder': 'Nome comercial do produto',
                'class': 'vTextField',
                'style': 'width: 60%;',
            }),
            'produto_unidade_medida': forms.TextInput(attrs={
                'placeholder': 'Ex.: UN, KG, CX',
                'class': 'vTextField',
                'style': 'width: 150px;',
            }),
            'produto_preco': forms.NumberInput(attrs={
                'step': '0.01',
                'min': '0',
                'class': 'vTextField',
                'style': 'width: 150px;',
            }),
            'produto_preco_custo': forms.NumberInput(attrs={
                'step': '0.01',
                'min': '0',
                'class': 'vTextField',
                'style': 'width: 150px;',
            }),
        }
        labels = {
            'produto_nome': 'Produto',
            'produto_unidade_medida': 'Unidade de medida',
            'produto_preco': 'Preço de venda (R$)',
            'produto_preco_custo': 'Preço de custo (R$)',
        }
        help_texts = {
            'produto_nome': 'Nome como apresentado em catálogos e notas.',
            'produto_unidade_medida': 'Informe a unidade utilizada nos controles de estoque.',
            'produto_preco': 'Defina o Preço sugerido de venda para o produto.',
            'produto_preco_custo': 'Preço de custo usado quando a venda não tem romaneio para rastreamento.',
        }


class ProdutoFaixaPrecoFilter(admin.SimpleListFilter):
    title = 'Faixa de Preço'
    parameter_name = 'produto_preco_intervalo'

    def lookups(self, request, model_admin):
        return (
            ('0-50', 'Até R$ 50,00'),
            ('50-200', 'R$ 50,01 a R$ 200,00'),
            ('200-500', 'R$ 200,01 a R$ 500,00'),
            ('500+', 'Acima de R$ 500,00'),
        )

    def queryset(self, request, queryset):
        valor = self.value()
        if valor == '0-50':
            return queryset.filter(produto_preco__lte=50)
        if valor == '50-200':
            return queryset.filter(produto_preco__gt=50, produto_preco__lte=200)
        if valor == '200-500':
            return queryset.filter(produto_preco__gt=200, produto_preco__lte=500)
        if valor == '500+':
            return queryset.filter(produto_preco__gt=500)
        return queryset


class ProdutoFornecedorFilter(admin.SimpleListFilter):
    title = 'Fornecedor'
    parameter_name = 'fornecedor_id'

    def lookups(self, request, model_admin):
        from .models import Fornecedor
        fornecedores = Fornecedor.objects.order_by('fornecedor_nome').values_list('pk', 'fornecedor_nome')
        return fornecedores

    def queryset(self, request, queryset):
        valor = self.value()
        if valor:
            return queryset.filter(fornecedor_id=valor)
        return queryset


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    form = ProdutoAdminForm
    list_display = ('produto_id', 'produto_nome', 'produto_preco_custo', 'produto_preco', 'fornecedor', 'grupo_mercadoria', 'unidade_medida', 'estoque_atual', 'valor_estoque_atual')
    list_display_links = ('produto_id', 'produto_nome')
    list_editable = ('produto_preco_custo', 'produto_preco',)
    search_fields = ('produto_nome', 'fornecedor__fornecedor_nome', 'grupo_mercadoria__grupo_mercadoria_nome')
    search_help_text = 'Busque pelo nome do produto, fornecedor ou grupo.'
    list_filter = (ProdutoFaixaPrecoFilter, ProdutoFornecedorFilter, 'grupo_mercadoria')
    ordering = ('produto_nome',)
    list_per_page = 25
    readonly_fields = ('produto_id', 'estoque_atual_readonly', 'valor_estoque_readonly')
    fieldsets = (
        ('Identificação', {'fields': ('produto_id', 'produto_nome', 'grupo_mercadoria', 'fornecedor'), 'classes': ('wide',)}),
        ('Detalhes Comerciais', {
            'fields': ('produto_unidade_medida', 'produto_preco_custo', 'produto_preco'), 
            'classes': ('wide',),
            'description': 'Unidade de medida, preço de custo (usado quando não há romaneio) e preço de venda.',
        }),
        ('Indicadores Automáticos', {
            'fields': ('estoque_atual_readonly', 'valor_estoque_readonly'),
            'classes': ('collapse',),
            'description': 'Valores calculados com base em compras e vendas registradas.',
        }),
    )
    save_on_top = True
    empty_value_display = '--'
    #inlines = [CompraItemInline, VendaItemInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(
            estoque_total=(Sum(
                Case(
                    When(compraitem__cfop__cfop_tipo=Cfop.TipoCfop.ENTRADA, then='compraitem__compra_item_qtd'),
                    When(vendaitem__cfop__cfop_tipo=Cfop.TipoCfop.ENTRADA, then='vendaitem__venda_item_qtd'),
                    default=Value(0),
                    output_field=DecimalField(),
                )
            ) - Sum(
                Case(
                    When(compraitem__cfop__cfop_tipo=Cfop.TipoCfop.SAIDA, then='compraitem__compra_item_qtd'),
                    When(vendaitem__cfop__cfop_tipo=Cfop.TipoCfop.SAIDA, then='vendaitem__venda_item_qtd'),
                    default=Value(0),
                    output_field=DecimalField(),
                )
            )),
            valor_estoque=F('estoque_total') * F('produto_preco'),
        )
        return qs

    @admin.display(description='Unidade')
    def unidade_medida(self, obj):
        return obj.produto_unidade_medida or '--'

    @admin.display(description='Estoque atual')
    def estoque_atual(self, obj):
        total = getattr(obj, 'estoque_total', None)
        if total is None:
            total = self._calcular_estoque(obj)
        if total < 0:
            return format_html('<span style="color:red;">{}</span>', total)
        return total

    @admin.display(description='Valor estoque (R$)', ordering='valor_estoque')
    def valor_estoque_atual(self, obj):
        valor = getattr(obj, 'valor_estoque', None)
        if valor is None:
            total = self._calcular_estoque(obj)
            preco = getattr(obj, 'produto_preco', None)
            if total is None or preco is None:
                return '--'
            valor = total * preco
        if valor is None:
            return '--'
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def estoque_atual_readonly(self, obj):
        total = getattr(obj, 'estoque_total', None)
        if total is None:
            total = self._calcular_estoque(obj)
        if total is None:
            return '--'
        return total
    estoque_atual_readonly.short_description = 'Estoque atual'

    def valor_estoque_readonly(self, obj):
        valor = getattr(obj, 'valor_estoque', None)
        if valor is None:
            total = self._calcular_estoque(obj)
            if total is None:
                return '--'
            # Verificar se produto_preco existe
            preco = getattr(obj, 'produto_preco', None)
            if preco is None:
                return '--'
            valor = total * preco
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    valor_estoque_readonly.short_description = 'Valor de estoque (R$)'

    def _calcular_estoque(self, obj):
        from .models import CompraItem, VendaItem
        entradas_compra = CompraItem.objects.filter(
            produto=obj,
            cfop__cfop_tipo=Cfop.TipoCfop.ENTRADA,
        ).aggregate(total=Sum('compra_item_qtd'))['total'] or 0
        entradas_venda = VendaItem.objects.filter(
            produto=obj,
            cfop__cfop_tipo=Cfop.TipoCfop.ENTRADA,
        ).aggregate(total=Sum('venda_item_qtd'))['total'] or 0
        saidas_compra = CompraItem.objects.filter(
            produto=obj,
            cfop__cfop_tipo=Cfop.TipoCfop.SAIDA,
        ).aggregate(total=Sum('compra_item_qtd'))['total'] or 0
        saidas_venda = VendaItem.objects.filter(
            produto=obj,
            cfop__cfop_tipo=Cfop.TipoCfop.SAIDA,
        ).aggregate(total=Sum('venda_item_qtd'))['total'] or 0
        return (entradas_compra + entradas_venda) - (saidas_compra + saidas_venda)