from django.contrib import admin
from django import forms
from django.db.models import Count, Max
from rangefilter.filters import DateRangeFilter
from .models import Funcionario


class FuncionarioAdminForm(forms.ModelForm):
    class Meta:
        model = Funcionario
        fields = '__all__'
        widgets = {
            'funcionario_nome': forms.TextInput(attrs={
                'placeholder': 'Nome completo do funcionario',
                'class': 'vTextField',
                'style': 'width: 60%;',
            }),
        }
        labels = {
            'funcionario_nome': 'Nome do funcionario',
        }
        help_texts = {
            'funcionario_nome': 'Informe como o funcionario aparece em relatorios e romaneios.',
        }


class FuncionarioInicialFilter(admin.SimpleListFilter):
    title = 'Inicial do nome'
    parameter_name = 'funcionario_nome_inicial'

    def lookups(self, request, model_admin):
        letras = [chr(c) for c in range(ord('A'), ord('Z') + 1)]
        return [(letra, letra) for letra in letras] + [('0-9', 'Inicia com numero')]

    def queryset(self, request, queryset):
        valor = self.value()
        if valor == '0-9':
            return queryset.filter(funcionario_nome__regex=r'^[0-9]')
        if valor:
            return queryset.filter(funcionario_nome__istartswith=valor)
        return queryset


class FuncionarioRomaneioCountFilter(admin.SimpleListFilter):
    title = 'Romaneios vinculados'
    parameter_name = 'romaneio_total'

    def lookups(self, request, model_admin):
        return (
            ('0', 'Sem romaneios'),
            ('1-5', '1 a 5 romaneios'),
            ('6-15', '6 a 15 romaneios'),
            ('15+', 'Mais de 15 romaneios'),
        )

    def queryset(self, request, queryset):
        valor = self.value()
        if valor == '0':
            return queryset.filter(romaneio_total=0)
        if valor == '1-5':
            return queryset.filter(romaneio_total__gte=1, romaneio_total__lte=5)
        if valor == '6-15':
            return queryset.filter(romaneio_total__gt=5, romaneio_total__lte=15)
        if valor == '15+':
            return queryset.filter(romaneio_total__gt=15)
        return queryset


@admin.register(Funcionario)
class FuncionarioAdmin(admin.ModelAdmin):
    form = FuncionarioAdminForm
    list_display = ('funcionario_id', 'funcionario_nome', 'total_romaneios', 'ultima_operacao')
    list_display_links = ('funcionario_id',)
    list_editable = ('funcionario_nome',)
    search_fields = ('funcionario_nome',)
    search_help_text = 'Busque pelo nome do funcionario.'
    list_filter = (
        #FuncionarioInicialFilter,
        FuncionarioRomaneioCountFilter,
        ('romaneio__romaneio_data_emissao', DateRangeFilter),
    )
    ordering = ('funcionario_nome',)
    list_per_page = 25
    readonly_fields = ('funcionario_id', 'total_romaneios_readonly', 'ultima_operacao_readonly')
    fieldsets = (
        ('Identificacao', {'fields': ('funcionario_id', 'funcionario_nome'), 'classes': ('wide',)}),
        ('Indicadores automaticos', {
            'fields': ('total_romaneios_readonly', 'ultima_operacao_readonly'),
            'classes': ('collapse',),
            'description': 'Resumo das operacoes vinculadas ao funcionario.',
        }),
    )
    save_on_top = True
    empty_value_display = '--'
    #inlines = [RomaneioInlineFuncionario]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            romaneio_total=Count('romaneio', distinct=True),
            ultima_data=Max('romaneio__romaneio_data_emissao'),
        )

    @admin.display(description='Romaneios', ordering='romaneio_total')
    def total_romaneios(self, obj):
        total = getattr(obj, 'romaneio_total', None)
        if total is None:
            total = obj.romaneio_set.count()
        return total

    @admin.display(description='Ultimo romaneio', ordering='ultima_data')
    def ultima_operacao(self, obj):
        data = getattr(obj, 'ultima_data', None)
        if not data:
            return '--'
        return data.strftime('%d/%m/%Y')

    def total_romaneios_readonly(self, obj):
        total = getattr(obj, 'romaneio_total', None)
        if total is None:
            total = obj.romaneio_set.count()
        return f'{total} romaneios'
    total_romaneios_readonly.short_description = 'Romaneios vinculados'

    def ultima_operacao_readonly(self, obj):
        data = getattr(obj, 'ultima_data', None)
        if not data:
            return '--'
        return data.strftime('%d/%m/%Y')
    ultima_operacao_readonly.short_description = 'Ultimo romaneio'