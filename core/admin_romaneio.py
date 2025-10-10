from django.contrib import admin
from django.db.models import Sum, Subquery, OuterRef, FloatField, F, ExpressionWrapper
from django.db.models.functions import Coalesce
from decimal import Decimal
from .models import Romaneio, VendaItem


class StatusRomaneioFilter(admin.SimpleListFilter):
    title = 'Status'
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return (
            ('aberto', 'Aberto'),
            ('fechado', 'Fechado'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == 'aberto':
            return queryset.filter(saldo__gt=0)
        if value == 'fechado':
            # Considera fechado quando saldo <= 0
            return queryset.filter(saldo__lte=0)
        return queryset


@admin.register(Romaneio)
class RomaneioAdmin(admin.ModelAdmin):
    list_display = (
        'romaneio_id', 'compra', 'funcionario', 'veiculo', 'romaneio_data_emissao',
        'total_carregado_display', 'total_entregue_display', 'saldo_display', 'status'
    )
    list_filter = (
        'romaneio_data_emissao',
        'funcionario',
        'veiculo',
        'compra',
        'compra__empresa',
        'compra__fornecedor',
        'status',
    )
    date_hierarchy = 'romaneio_data_emissao'
    change_list_template = 'admin/core/romaneio/change_list.html'

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        total_entregue_sq = Subquery(
            VendaItem.objects.filter(venda__romaneio=OuterRef('pk'))
            .values('venda__romaneio')
            .annotate(total=Sum('venda_item_qtd'))
            .values('total')[:1],
            output_field=FloatField()
        )

        qs = qs.annotate(total_entregue=total_entregue_sq)
        qs = qs.annotate(
            saldo=ExpressionWrapper(
                Coalesce(F('produto_item_qtd'), 0.0) - Coalesce(F('total_entregue'), 0.0),
                output_field=FloatField()
            )
        )
        return qs

    # Colunas agregadas por registro
    def total_carregado_display(self, obj):
        value = obj.produto_item_qtd or 0
        return f"{value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    total_carregado_display.short_description = 'Total Carregado'
    total_carregado_display.admin_order_field = 'produto_item_qtd'

    def total_entregue_display(self, obj):
        value = getattr(obj, 'total_entregue', 0) or 0
        return f"{value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    total_entregue_display.short_description = 'Total Entregue'
    total_entregue_display.admin_order_field = 'total_entregue'

    def saldo_display(self, obj):
        value = getattr(obj, 'saldo', None)
        if value is None:
            carregado = float(obj.produto_item_qtd or 0)
            entregue = float(getattr(obj, 'total_entregue', 0) or 0)
            value = carregado - entregue
        cor = 'green' if value >= 0 else 'red'
        formatted = f"{value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        return formatted
    saldo_display.short_description = 'Saldo'
    saldo_display.admin_order_field = 'saldo'

    def status_display(self, obj):
        total_carregado = float(obj.produto_item_qtd or 0)
        total_entregue = float(getattr(obj, 'total_entregue', 0) or 0)
        # Fechado quando entregue >= carregado (e há quantidade definida)
        fechado = total_carregado > 0 and total_entregue >= total_carregado
        return 'Fechado' if fechado else 'Aberto'
    status_display.short_description = 'Status'
    status_display.admin_order_field = 'saldo'

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context=extra_context)
        return response


class StatusRomaneioFilter(admin.SimpleListFilter):
    title = 'Status'
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return (
            ('aberto', 'Aberto'),
            ('fechado', 'Fechado'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == 'aberto':
            return queryset.filter(saldo__gt=0)
        if value == 'fechado':
            # Considera fechado quando saldo <= 0
            return queryset.filter(saldo__lte=0)
        return queryset
