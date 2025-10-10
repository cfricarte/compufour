from django.contrib import admin
from django import forms
from django.db.models import Count
from .models import GrupoMercadoria


class GrupoMercadoriaAdminForm(forms.ModelForm):
    class Meta:
        model = GrupoMercadoria
        fields = '__all__'
        widgets = {
            'grupo_mercadoria_nome': forms.TextInput(attrs={
                'placeholder': 'Nome do grupo de mercadorias',
                'class': 'vTextField',
                'style': 'width: 60%;',
            }),
        }
        labels = {
            'grupo_mercadoria_nome': 'Nome do grupo',
        }
        help_texts = {
            'grupo_mercadoria_nome': 'Informe como o grupo aparece nas listagens e nos produtos.',
        }


class GrupoMercadoriaInicialFilter(admin.SimpleListFilter):
    title = 'Inicial do nome'
    parameter_name = 'grupo_mercadoria_inicial'

    def lookups(self, request, model_admin):
        letras = [chr(c) for c in range(ord('A'), ord('Z') + 1)]
        return [(letra, letra) for letra in letras] + [('0-9', 'Inicia com numero')]

    def queryset(self, request, queryset):
        valor = self.value()
        if valor == '0-9':
            return queryset.filter(grupo_mercadoria_nome__regex=r'^[0-9]')
        if valor:
            return queryset.filter(grupo_mercadoria_nome__istartswith=valor)
        return queryset


class GrupoMercadoriaProdutoCountFilter(admin.SimpleListFilter):
    title = 'Produtos cadastrados'
    parameter_name = 'produto_total'

    def lookups(self, request, model_admin):
        return (
            ('0', 'Sem produtos'),
            ('1-10', '1 a 10 produtos'),
            ('11-50', '11 a 50 produtos'),
            ('50+', 'Mais de 50 produtos'),
        )

    def queryset(self, request, queryset):
        valor = self.value()
        if valor == '0':
            return queryset.filter(produto_total=0)
        if valor == '1-10':
            return queryset.filter(produto_total__gte=1, produto_total__lte=10)
        if valor == '11-50':
            return queryset.filter(produto_total__gt=10, produto_total__lte=50)
        if valor == '50+':
            return queryset.filter(produto_total__gt=50)
        return queryset


@admin.register(GrupoMercadoria)
class GrupoMercadoriaAdmin(admin.ModelAdmin):
    form = GrupoMercadoriaAdminForm
    list_display = ('grupo_mercadoria_id', 'grupo_mercadoria_nome', 'produtos_cadastrados')
    list_display_links = ('grupo_mercadoria_id',)
    list_editable = ('grupo_mercadoria_nome',)
    search_fields = ('grupo_mercadoria_nome',)
    search_help_text = 'Busque pelo nome do grupo.'
    list_filter = (GrupoMercadoriaInicialFilter, GrupoMercadoriaProdutoCountFilter)
    ordering = ('grupo_mercadoria_nome',)
    list_per_page = 25
    readonly_fields = ('grupo_mercadoria_id', 'total_produtos_readonly')
    fieldsets = (
        ('Identificacao', {'fields': ('grupo_mercadoria_id', 'grupo_mercadoria_nome'), 'classes': ('wide',)}),
        ('Resumo', {
            'fields': ('total_produtos_readonly',),
            'classes': ('collapse',),
            'description': 'Dados calculados automaticamente.',
        }),
    )
    save_on_top = True
    empty_value_display = '--'
    #inlines = [ProdutoInlineGrupoMercadoria]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(produto_total=Count('produto', distinct=True))

    @admin.display(description='Produtos cadastrados', ordering='produto_total')
    def produtos_cadastrados(self, obj):
        total = getattr(obj, 'produto_total', None)
        if total is None:
            total = obj.produto_set.count()
        return total

    def total_produtos_readonly(self, obj):
        total = getattr(obj, 'produto_total', None)
        if total is None:
            total = obj.produto_set.count()
        return f'{total} produtos'
    total_produtos_readonly.short_description = 'Produtos cadastrados'