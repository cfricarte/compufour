from django.contrib import admin
from django.db.models import Window, F, Sum
from django.utils.html import format_html
from django import forms
from rangefilter.filters import DateRangeFilter
from .models import Caixa


class CaixaForm(forms.ModelForm):
    caixa_data_emissao = forms.DateField(
        widget=admin.widgets.AdminDateWidget(),
        required=False
    )

    class Meta:
        model = Caixa
        fields = '__all__'


@admin.register(Caixa)
class CaixaAdmin(admin.ModelAdmin):
    form = CaixaForm
    list_display = (
        'empresa',
        'plano_conta',
        'caixa_data_emissao',
        'caixa_historico',
        'caixa_valor_entrada',
        'caixa_valor_saida',
        'saldo_do_movimento',
        'mostrar_saldo_acumulado',
    )
    list_filter = (
        ('caixa_data_emissao', DateRangeFilter),
        'empresa',
        'plano_conta'
    )
    search_fields = ('caixa_historico',)
    ordering = ('caixa_data_emissao', 'caixa_id')

    class Media:
        js = ('admin/js/jquery.init.js', 'admin/js/core.js', 'admin/js/admin/DateTimeShortcuts.js')
        css = {'all': ('admin/css/widgets.css',)}

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(
            saldo_acumulado=Window(
                expression=Sum(F('caixa_valor_entrada') - F('caixa_valor_saida')),
                order_by=[F('caixa_data_emissao').asc(), F('caixa_id').asc()]
            )
        )
        return qs

    @admin.display(description='Saldo do Movimento (R$)')
    def saldo_do_movimento(self, obj):
        saldo = obj.saldo
        cor = 'green' if saldo > 0 else 'red' if saldo < 0 else 'gray'
        saldo_formatado = f"R$ {saldo:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return format_html(f'<b style="color: {cor};">{saldo_formatado}</b>')

    @admin.display(description='Saldo Acumulado (R$)')
    def mostrar_saldo_acumulado(self, obj):
        if hasattr(obj, 'saldo_acumulado') and obj.saldo_acumulado is not None:
            saldo = obj.saldo_acumulado
            cor = 'green' if saldo >= 0 else 'red'
            saldo_formatado = f"R$ {saldo:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            return format_html(f'<strong style="color: {cor};">{saldo_formatado}</strong>')
        return "N/A"