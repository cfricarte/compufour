from django.contrib import admin
from django import forms
from .models import Empresa


class EmpresaAdminForm(forms.ModelForm):
    class Meta:
        model = Empresa
        fields = '__all__'
        widgets = {
            'empresa_nome': forms.TextInput(attrs={
                'placeholder': 'Razão social ou nome fantasia',
                'class': 'vTextField',
                'style': 'width: 60%;',
            }),
        }
        labels = {
            'empresa_nome': 'Empresa',
        }
        help_texts = {
            'empresa_nome': 'Informe o nome como deve aparecer em relatórios e cadastros.',
        }


class EmpresaInicialFilter(admin.SimpleListFilter):
    title = 'Inicial do nome'
    parameter_name = 'empresa_nome_inicial'

    def lookups(self, request, model_admin):
        letras = [chr(c) for c in range(ord('A'), ord('Z') + 1)]
        return [(letra, letra) for letra in letras] + [('0-9', 'Inicia com número')]

    def queryset(self, request, queryset):
        valor = self.value()
        if valor == '0-9':
            return queryset.filter(empresa_nome__regex=r'^[0-9]')
        if valor:
            return queryset.filter(empresa_nome__istartswith=valor)
        return queryset


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    form = EmpresaAdminForm
    list_display = ('empresa_id', 'empresa_nome', 'tamanho_nome')
    list_display_links = ('empresa_id',)
    list_editable = ('empresa_nome',)
    search_fields = ('empresa_nome',)
    search_help_text = 'Busque pelo nome comercial da empresa.'
    list_filter = (EmpresaInicialFilter,)
    ordering = ('empresa_nome',)
    list_per_page = 25
    readonly_fields = ('empresa_id', 'tamanho_nome')
    fieldsets = (
        ('Identificação', {'fields': ('empresa_id', 'empresa_nome'), 'classes': ('wide',)}),
        ('Informações adicionais', {
            'fields': ('tamanho_nome',),
            'classes': ('collapse',),
            'description': 'Dados auxiliares calculados automaticamente.',
        }),
    )
    save_on_top = True
    empty_value_display = '--'

    @admin.display(description='Tamanho do Nome', ordering='empresa_nome')
    def tamanho_nome(self, obj):
        nome = obj.empresa_nome or ''
        return f'{len(nome)} caracteres'