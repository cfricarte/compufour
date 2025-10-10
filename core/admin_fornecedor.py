from django.contrib import admin
from django import forms
from django.db.models import Count
from .models import Fornecedor


class FornecedorAdminForm(forms.ModelForm):
    class Meta:
        model = Fornecedor
        fields = '__all__'
        widgets = {
            'fornecedor_nome': forms.TextInput(attrs={
                'placeholder': 'Nome do fornecedor',
                'class': 'vTextField',
                'style': 'width: 60%;',
            }),
        }
        labels = {
            'fornecedor_nome': 'Nome do fornecedor',
        }
        help_texts = {
            'fornecedor_nome': 'Informe o nome comercial apresentado em notas e cadastros.',
        }


class FornecedorInicialFilter(admin.SimpleListFilter):
    title = 'Inicial do nome'
    parameter_name = 'fornecedor_nome_inicial'

    def lookups(self, request, model_admin):
        letras = [chr(c) for c in range(ord('A'), ord('Z') + 1)]
        return [(letra, letra) for letra in letras] + [('0-9', 'Inicia com número')]

    def queryset(self, request, queryset):
        valor = self.value()
        if valor == '0-9':
            return queryset.filter(fornecedor_nome__regex=r'^[0-9]')
        if valor:
            return queryset.filter(fornecedor_nome__istartswith=valor)
        return queryset


class FornecedorProdutoCountFilter(admin.SimpleListFilter):
    title = 'Produtos cadastrados'
    parameter_name = 'produto_total'

    def lookups(self, request, model_admin):
        return (
            ('0', 'Nenhum produto'),
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


@admin.register(Fornecedor)
class FornecedorAdmin(admin.ModelAdmin):
    form = FornecedorAdminForm
    list_display = ('fornecedor_id', 'fornecedor_nome', 'produtos_cadastrados')
    list_display_links = ('fornecedor_id',)
    list_editable = ('fornecedor_nome',)
    search_fields = ('fornecedor_nome', 'produto__produto_nome')
    search_help_text = 'Busque por nome de fornecedor ou de produtos relacionados.'
    list_filter = (FornecedorInicialFilter, FornecedorProdutoCountFilter)
    ordering = ('fornecedor_nome',)
    list_per_page = 25
    readonly_fields = ('fornecedor_id', 'total_produtos_readonly')
    fieldsets = (
        ('Identificação', {'fields': ('fornecedor_id', 'fornecedor_nome'), 'classes': ('wide',)}),
        ('Resumo', {
            'fields': ('total_produtos_readonly',),
            'classes': ('collapse',),
            'description': 'Indicadores calculados automaticamente.',
        }),
    )
    save_on_top = True
    empty_value_display = '--'
    #inlines = [ProdutoInlineFornecedor, CompraInline, ContaPagarInline]

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