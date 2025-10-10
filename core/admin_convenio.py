from django.contrib import admin
from django import forms
from .models import Convenio


class ConvenioAdminForm(forms.ModelForm):
    class Meta:
        model = Convenio
        fields = '__all__'
        widgets = {
            'convenio_nome': forms.TextInput(attrs={
                'placeholder': 'Nome do convènio',
                'class': 'vTextField',
                'style': 'width: 60%;',
            }),
            'convenio_preco': forms.NumberInput(attrs={
                'step': '0.01',
                'min': '0',
                'class': 'vTextField',
                'style': 'width: 150px;',
            }),
        }
        labels = {
            'convenio_nome': 'Nome do convènio',
            'convenio_preco': 'Preço base',
        }
        help_texts = {
            'convenio_nome': 'Como o convènio será exibido no painel.',
            'convenio_preco': 'Informe o Preço base em reais (use ponto como separador decimal).',
        }


class ConvenioPrecoRangeFilter(admin.SimpleListFilter):
    title = 'Faixa de Preço'
    parameter_name = 'convenio_preco'

    def lookups(self, request, model_admin):
        return (
            ('0-100', 'Até R$ 100,00'),
            ('100-500', 'De R$ 100,01 a R$ 500,00'),
            ('500-1000', 'De R$ 500,01 a R$ 1.000,00'),
            ('1000+', 'Acima de R$ 1.000,00'),
        )

    def queryset(self, request, queryset):
        valor = self.value()
        if valor == '0-100':
            return queryset.filter(convenio_preco__lte=100)
        if valor == '100-500':
            return queryset.filter(convenio_preco__gt=100, convenio_preco__lte=500)
        if valor == '500-1000':
            return queryset.filter(convenio_preco__gt=500, convenio_preco__lte=1000)
        if valor == '1000+':
            return queryset.filter(convenio_preco__gt=1000)
        return queryset


@admin.register(Convenio)
class ConvenioAdmin(admin.ModelAdmin):
    form = ConvenioAdminForm
    list_display = ('convenio_id', 'convenio_nome', 'convenio_preco', 'preco_formatado')
    list_display_links = ('convenio_id', 'convenio_nome')
    list_editable = ('convenio_preco',)
    search_fields = ('convenio_nome',)
    search_help_text = 'Busque pelo nome do convènio.'
    list_filter = (ConvenioPrecoRangeFilter,)
    ordering = ('convenio_nome',)
    list_per_page = 25
    readonly_fields = ('convenio_id',)
    fieldsets = (
        ('Identificação', {'fields': ('convenio_id', 'convenio_nome'), 'classes': ('wide',)}),
        ('Precificação', {'fields': ('convenio_preco',), 'description': 'Defina o Preço base apresentado nos cadastros relacionados.'}),
    )

    @admin.display(description='Preço (R$)', ordering='convenio_preco')
    def preco_formatado(self, obj):
        valor = obj.convenio_preco
        if valor is None:
            return 'N/A'
        return f"R$ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')