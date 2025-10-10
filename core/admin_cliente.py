from django.contrib import admin
from django import forms
from django.db.models import Count
from .models import Cliente, ClienteConvenioGrupoMercadoria


class ClienteConvenioGrupoMercadoriaInline(admin.TabularInline):
    model = ClienteConvenioGrupoMercadoria
    extra = 1


class ClienteAdminForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = '__all__'
        widgets = {
            'cliente_nome': forms.TextInput(attrs={
                'placeholder': 'Nome completo ou social',
                'class': 'vTextField',
                'style': 'width: 60%;',
            }),
        }
        labels = {
            'cliente_nome': 'Nome do cliente',
        }
        help_texts = {
            'cliente_nome': 'Como o nome aparecer para a equipe e nos relatórios.',
        }


class ClienteInicialFilter(admin.SimpleListFilter):
    title = 'Inicial do nome'
    parameter_name = 'cliente_nome_inicial'

    def lookups(self, request, model_admin):
        letras = [chr(c) for c in range(ord('A'), ord('Z') + 1)]
        return [(letra, letra) for letra in letras] + [('0-9', 'Inicia com número')]

    def queryset(self, request, queryset):
        valor = self.value()
        if valor == '0-9':
            return queryset.filter(cliente_nome__regex=r'^[0-9]')
        if valor:
            return queryset.filter(cliente_nome__istartswith=valor)
        return queryset


class ClienteConvenioCountFilter(admin.SimpleListFilter):
    title = 'Convênios vinculados'
    parameter_name = 'convenio_total'

    def lookups(self, request, model_admin):
        return (
            ('0', 'Sem convênios'),
            ('1-3', '1 a 3 convênios'),
            ('4-10', '4 a 10 convênios'),
            ('10+', 'Mais de 10 convênios'),
        )

    def queryset(self, request, queryset):
        valor = self.value()
        if valor == '0':
            return queryset.filter(convenio_total=0)
        if valor == '1-3':
            return queryset.filter(convenio_total__gte=1, convenio_total__lte=3)
        if valor == '4-10':
            return queryset.filter(convenio_total__gt=3, convenio_total__lte=10)
        if valor == '10+':
            return queryset.filter(convenio_total__gt=10)
        return queryset


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    form = ClienteAdminForm
    list_display = ('cliente_id', 'cliente_nome', 'convenios_cadastrados')
    list_display_links = ('cliente_id',)
    list_editable = ('cliente_nome',)
    search_fields = ('cliente_nome',)
    search_help_text = 'Busque pelo nome do cliente.'
    list_filter = (ClienteInicialFilter, ClienteConvenioCountFilter)
    ordering = ('cliente_nome',)
    list_per_page = 25
    readonly_fields = ('cliente_id', 'total_convenios_readonly')
    fieldsets = (
        ('Identificação', {'fields': ('cliente_id', 'cliente_nome'), 'classes': ('wide',)}),
        ('Resumo', {
            'fields': ('total_convenios_readonly',),
            'classes': ('collapse',),
            'description': 'Informações calculadas automaticamente.',
        }),
    )
    save_on_top = True
    empty_value_display = '--'
    inlines = [ClienteConvenioGrupoMercadoriaInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(convenio_total=Count('clienteconveniogrupomercadoria', distinct=True))

    @admin.display(description='convênios vinculados', ordering='convenio_total')
    def convenios_cadastrados(self, obj):
        total = getattr(obj, 'convenio_total', None)
        if total is None:
            total = obj.clienteconveniogrupomercadoria_set.count()
        return total

    def total_convenios_readonly(self, obj):
        total = getattr(obj, 'convenio_total', None)
        if total is None:
            total = obj.clienteconveniogrupomercadoria_set.count()
        return f'{total} convênios'
    total_convenios_readonly.short_description = 'convênios vinculados'