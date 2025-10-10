from django.contrib import admin
from django import forms
from django.db.models import Count, Max, Sum, Value, DecimalField
from django.db.models.functions import Coalesce
from django.utils.html import format_html
from decimal import Decimal
from rangefilter.filters import DateRangeFilter
from .models import PlanoConta


class PlanoContaAdminForm(forms.ModelForm):
    class Meta:
        model = PlanoConta
        fields = '__all__'
        widgets = {
            'plano_conta_numero': forms.TextInput(attrs={
                'placeholder': 'Ex: 1.01.001 ou 3.02.005',
                'class': 'vTextField',
                'style': 'width: 30%;',
            }),
            'plano_conta_nome': forms.TextInput(attrs={
                'placeholder': 'Nome do plano de contas',
                'class': 'vTextField',
                'style': 'width: 60%;',
            }),
        }
        labels = {
            'plano_conta_numero': 'Número da Conta',
            'plano_conta_nome': 'Plano de contas',
        }
        help_texts = {
            'plano_conta_numero': '1=Receita (Vendas), 3=Despesa (Compras), 5=Banco',
            'plano_conta_nome': 'Descrição utilizada em lançamentos financeiros.',
        }


class PlanoContaInicialFilter(admin.SimpleListFilter):
    title = 'Inicial do nome'
    parameter_name = 'plano_conta_nome_inicial'

    def lookups(self, request, model_admin):
        letras = [chr(c) for c in range(ord('A'), ord('Z') + 1)]
        return [(letra, letra) for letra in letras] + [('0-9', 'Inicia com número')]

    def queryset(self, request, queryset):
        valor = self.value()
        if valor == '0-9':
            return queryset.filter(plano_conta_nome__regex=r'^[0-9]')
        if valor:
            return queryset.filter(plano_conta_nome__istartswith=valor)
        return queryset


class PlanoContaCaixaCountFilter(admin.SimpleListFilter):
    title = 'lançamentos vinculados'
    parameter_name = 'lancamentos_total'

    def lookups(self, request, model_admin):
        return (
            ('0', 'Sem lançamentos'),
            ('1-20', '1 a 20 lançamentos'),
            ('21-100', '21 a 100 lançamentos'),
            ('100+', 'Mais de 100 lançamentos'),
        )

    def queryset(self, request, queryset):
        valor = self.value()
        if valor == '0':
            return queryset.filter(total_lancamentos=0)
        if valor == '1-20':
            return queryset.filter(total_lancamentos__gte=1, total_lancamentos__lte=20)
        if valor == '21-100':
            return queryset.filter(total_lancamentos__gt=20, total_lancamentos__lte=100)
        if valor == '100+':
            return queryset.filter(total_lancamentos__gt=100)
        return queryset


class PlanoContaTipoFilter(admin.SimpleListFilter):
    title = 'Tipo de Conta'
    parameter_name = 'tipo_conta'

    def lookups(self, request, model_admin):
        return (
            ('1', '💰 Receita (Entrada)'),
            ('3', '💸 Despesa (Saída)'),
            ('5', '🏦 Banco'),
            ('outros', '⚪ Outros'),
        )

    def queryset(self, request, queryset):
        valor = self.value()
        if valor == '1':
            return queryset.filter(plano_conta_numero__startswith='1')
        if valor == '3':
            return queryset.filter(plano_conta_numero__startswith='3')
        if valor == '5':
            return queryset.filter(plano_conta_numero__startswith='5')
        if valor == 'outros':
            return queryset.exclude(plano_conta_numero__startswith='1').exclude(
                plano_conta_numero__startswith='3').exclude(plano_conta_numero__startswith='5')
        return queryset


@admin.register(PlanoConta)
class PlanoContaAdmin(admin.ModelAdmin):
    form = PlanoContaAdminForm
    list_display = ('plano_conta_id', 'plano_conta_numero', 'plano_conta_nome', 'tipo_conta_display', 'total_lancamentos', 'ultima_movimentacao', 'valor_entradas', 'valor_saidas', 'saldo_total')
    list_display_links = ('plano_conta_id', 'plano_conta_numero')
    list_editable = ('plano_conta_nome',)
    search_fields = ('plano_conta_numero', 'plano_conta_nome',)
    search_help_text = 'Busque pelo número ou nome do plano de contas.'
    list_filter = (
        PlanoContaTipoFilter,
        #PlanoContaInicialFilter,
        PlanoContaCaixaCountFilter,
        ('caixa__caixa_data_emissao', DateRangeFilter),
    )
    ordering = ('plano_conta_numero', 'plano_conta_nome',)
    list_per_page = 25
    readonly_fields = ('plano_conta_id', 'tipo_conta_display', 'total_lancamentos_readonly', 'ultima_movimentacao_readonly', 'valor_entradas_readonly', 'valor_saidas_readonly', 'saldo_total_readonly')
    fieldsets = (
        ('Identificação', {'fields': ('plano_conta_id', 'plano_conta_numero', 'plano_conta_nome', 'tipo_conta_display'), 'classes': ('wide',)}),
        ('Indicadores automáticos', {
            'fields': ('total_lancamentos_readonly', 'ultima_movimentacao_readonly', 'valor_entradas_readonly', 'valor_saidas_readonly', 'saldo_total_readonly'),
            'classes': ('collapse',),
            'description': 'Resumo financeiro calculado a partir dos lançamentos de caixa.',
        }),
    )
    save_on_top = True
    empty_value_display = '--'
    #inlines = [CaixaInlinePlanoConta]
    
    @admin.display(description='Tipo de Conta', ordering='plano_conta_numero')
    def tipo_conta_display(self, obj):
        """Exibe o tipo da conta com cor baseada no primeiro dígito."""
        primeiro_digito = obj.get_primeiro_digito()
        
        if primeiro_digito == '1':
            return format_html('<strong style="color: #009933;">💰 Receita (Entrada)</strong>')
        elif primeiro_digito == '3':
            return format_html('<strong style="color: #cc0000;">💸 Despesa (Saída)</strong>')
        elif primeiro_digito == '5':
            return format_html('<strong style="color: #0066cc;">🏦 Banco</strong>')
        else:
            return format_html('<span style="color: #666;">⚪ Outros</span>')

    def get_queryset(self, request):
        zero = Decimal('0')
        qs = super().get_queryset(request)
        qs = qs.annotate(
            total_lancamentos=Count('caixa', distinct=True),
            ultima_data=Max('caixa__caixa_data_emissao'),
            total_entradas=Coalesce(Sum('caixa__caixa_valor_entrada'), Value(zero)),
            total_saidas=Coalesce(Sum('caixa__caixa_valor_saida'), Value(zero)),
        )
        return qs

    @admin.display(description='lançamentos', ordering='total_lancamentos')
    def total_lancamentos(self, obj):
        total = getattr(obj, 'total_lancamentos', None)
        if total is None:
            total = obj.caixa_set.count()
        return total

    @admin.display(description='última movimentação', ordering='ultima_data')
    def ultima_movimentacao(self, obj):
        data = getattr(obj, 'ultima_data', None)
        if not data:
            return '--'
        return data.strftime('%d/%m/%Y')

    @admin.display(description='Entradas (R$)', ordering='total_entradas')
    def valor_entradas(self, obj):
        valor = getattr(obj, 'total_entradas', Decimal('0')) or Decimal('0')
        return f"R$ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

    @admin.display(description='saídas (R$)', ordering='total_saidas')
    def valor_saidas(self, obj):
        valor = getattr(obj, 'total_saidas', Decimal('0')) or Decimal('0')
        return f"R$ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

    @admin.display(description='Saldo (R$)')
    def saldo_total(self, obj):
        entradas = getattr(obj, 'total_entradas', Decimal('0')) or Decimal('0')
        saidas = getattr(obj, 'total_saidas', Decimal('0')) or Decimal('0')
        saldo = entradas - saidas
        cor = 'green' if saldo >= 0 else 'red'
        saldo_formatado = f"R$ {saldo:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        return format_html('<span style="color:{};">{}</span>', cor, saldo_formatado)

    def total_lancamentos_readonly(self, obj):
        total = self.total_lancamentos(obj)
        return f'{total} lançamentos'
    total_lancamentos_readonly.short_description = 'lançamentos vinculados'

    def ultima_movimentacao_readonly(self, obj):
        return self.ultima_movimentacao(obj)
    ultima_movimentacao_readonly.short_description = 'última movimentação'

    def valor_entradas_readonly(self, obj):
        return self.valor_entradas(obj)
    valor_entradas_readonly.short_description = 'Entradas (R$)'

    def valor_saidas_readonly(self, obj):
        return self.valor_saidas(obj)
    valor_saidas_readonly.short_description = 'saídas (R$)'

    def saldo_total_readonly(self, obj):
        entradas = getattr(obj, 'total_entradas', Decimal('0')) or Decimal('0')
        saidas = getattr(obj, 'total_saidas', Decimal('0')) or Decimal('0')
        saldo = entradas - saidas
        return f"R$ {saldo:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    saldo_total_readonly.short_description = 'Saldo (R$)'