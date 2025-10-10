from django.contrib import admin
from django import forms
from django.db.models import Count, Max
from .models import Veiculo


class VeiculoAdminForm(forms.ModelForm):
    class Meta:
        model = Veiculo
        fields = '__all__'
        widgets = {
            'veiculo_modelo': forms.TextInput(attrs={
                'placeholder': 'Modelo do veiculo',
                'class': 'vTextField',
                'style': 'width: 60%;',
            }),
            'veiculo_placa': forms.TextInput(attrs={
                'placeholder': 'Placa (ex.: ABC-1234)',
                'class': 'vTextField',
                'style': 'width: 180px;',
            }),
        }
        labels = {
            'veiculo_modelo': 'Modelo',
            'veiculo_placa': 'Placa',
        }
        help_texts = {
            'veiculo_modelo': 'Informe o modelo como aparece nos romaneios.',
            'veiculo_placa': 'Placa formatada conformepadrão do Detran.',
        }


class VeiculoModeloInicialFilter(admin.SimpleListFilter):
    title = 'Inicial do modelo'
    parameter_name = 'veiculo_modelo_inicial'

    def lookups(self, request, model_admin):
        letras = [chr(c) for c in range(ord('A'), ord('Z') + 1)]
        return [(letra, letra) for letra in letras] + [('0-9', 'Inicia com numero')]

    def queryset(self, request, queryset):
        valor = self.value()
        if valor == '0-9':
            return queryset.filter(veiculo_modelo__regex=r'^[0-9]')
        if valor:
            return queryset.filter(veiculo_modelo__istartswith=valor)
        return queryset


class VeiculoRomaneioCountFilter(admin.SimpleListFilter):
    title = 'Romaneios vinculados'
    parameter_name = 'romaneio_total'

    def lookups(self, request, model_admin):
        return (
            ('0', 'Sem romaneios'),
            ('1-3', '1 a 3 romaneios'),
            ('4-10', '4 a 10 romaneios'),
            ('10+', 'Mais de 10 romaneios'),
        )

    def queryset(self, request, queryset):
        valor = self.value()
        if valor == '0':
            return queryset.filter(romaneio_total=0)
        if valor == '1-3':
            return queryset.filter(romaneio_total__gte=1, romaneio_total__lte=3)
        if valor == '4-10':
            return queryset.filter(romaneio_total__gt=3, romaneio_total__lte=10)
        if valor == '10+':
            return queryset.filter(romaneio_total__gt=10)
        return queryset


@admin.register(Veiculo)
class VeiculoAdmin(admin.ModelAdmin):
    form = VeiculoAdminForm
    list_display = ('veiculo_id', 'veiculo_modelo', 'veiculo_placa', 'total_romaneios', 'ultima_saida')
    list_display_links = ('veiculo_id', 'veiculo_modelo')
    list_editable = ('veiculo_placa',)
    search_fields = ('veiculo_modelo', 'veiculo_placa')
    search_help_text = 'Busque pelo modelo ou placa do veiculo.'
    list_filter = (VeiculoModeloInicialFilter, VeiculoRomaneioCountFilter)
    ordering = ('veiculo_modelo', 'veiculo_placa')
    list_per_page = 25
    readonly_fields = ('veiculo_id', 'total_romaneios_readonly', 'ultima_saida_readonly')
    fieldsets = (
        ('Identificacao', {'fields': ('veiculo_id', 'veiculo_modelo', 'veiculo_placa'), 'classes': ('wide',)}),
        ('Indicadores automaticos', {
            'fields': ('total_romaneios_readonly', 'ultima_saida_readonly'),
            'classes': ('collapse',),
            'description': 'Resumo das saídas registradas nos romaneios.',
        }),
    )
    save_on_top = True
    empty_value_display = '--'
    #inlines = [RomaneioInlineVeiculo]

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

    @admin.display(description='Ultima saida', ordering='ultima_data')
    def ultima_saida(self, obj):
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

    def ultima_saida_readonly(self, obj):
        data = getattr(obj, 'ultima_data', None)
        if not data:
            return '--'
        return data.strftime('%d/%m/%Y')
    ultima_saida_readonly.short_description = 'Ultima saida'