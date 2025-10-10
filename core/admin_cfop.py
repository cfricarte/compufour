from django.contrib import admin
from django import forms
from django.db.models import Count
from django.utils.html import format_html
from .models import Cfop


class CfopAdminForm(forms.ModelForm):
    class Meta:
        model = Cfop
        fields = '__all__'
        widgets = {
            'cfop_codigo': forms.TextInput(attrs={
                'placeholder': 'Ex.: 5101',
                'class': 'vTextField',
                'style': 'width: 200px;',
            }),
            'cfop_operacao': forms.TextInput(attrs={
                'placeholder': 'Descrição da operações fiscal',
                'class': 'vTextField',
                'style': 'width: 70%;',
            }),
            'cfop_integracao': forms.TextInput(attrs={
                'placeholder': 'Etiqueta utilizada na integração',
                'class': 'vTextField',
                'style': 'width: 50%;',
            }),
            'cfop_tipo': forms.Select(attrs={'class': 'vSelect'}),
        }
        labels = {
            'cfop_codigo': 'Código CFOP',
            'cfop_operacao': 'operações',
            'cfop_integracao': 'integração',
            'cfop_tipo': 'Tipo',
        }
        help_texts = {
            'cfop_codigo': 'Informe o Código conforme tabela oficial do CFOP.',
            'cfop_operacao': 'Descrição amigável da operações para conferência rápida.',
            'cfop_integracao': 'Código interno utilizado em integrações ou automações.',
            'cfop_tipo': 'Classifique se a operações é de entrada ou saída.',
        }


class CfopTipoFilter(admin.SimpleListFilter):
    title = 'Tipo de operações'
    parameter_name = 'cfop_tipo_custom'

    def lookups(self, request, model_admin):
        return Cfop.TipoCfop.choices

    def queryset(self, request, queryset):
        valor = self.value()
        if valor:
            return queryset.filter(cfop_tipo=valor)
        return queryset


@admin.register(Cfop)
class CfopAdmin(admin.ModelAdmin):
    form = CfopAdminForm
    list_display = ('cfop_id', 'cfop_codigo_colored', 'cfop_operacao', 'tipo_display', 'cfop_integracao', 'disponibilidade_display', 'usos_compra', 'usos_venda')
    list_display_links = ('cfop_id', 'cfop_codigo_colored')
    list_editable = ('cfop_integracao',)
    search_fields = ('cfop_codigo', 'cfop_operacao', 'cfop_integracao')
    search_help_text = 'Busque pelo Código, Descrição ou integração.'
    list_filter = (CfopTipoFilter, 'cfop_integracao')
    ordering = ('cfop_codigo',)
    list_per_page = 25
    readonly_fields = ('cfop_id', 'usos_compra_readonly', 'usos_venda_readonly', 'disponibilidade_display')
    fieldsets = (
        ('Identificação', {'fields': ('cfop_id', 'cfop_codigo', 'cfop_operacao'), 'classes': ('wide',)}),
        ('Classificação', {'fields': ('cfop_tipo', 'cfop_integracao', 'disponibilidade_display'), 'classes': ('wide',)}),
        ('Indicadores automáticos', {
            'fields': ('usos_compra_readonly', 'usos_venda_readonly'),
            'classes': ('collapse',),
            'description': 'Valores calculados automaticamente a partir dos lançamentos.',
        }),
    )
    save_on_top = True
    empty_value_display = '--'
    #inlines = [CompraItemInlineCfop, VendaItemInlineCfop]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            usos_compra_total=Count('compraitem', distinct=True),
            usos_venda_total=Count('vendaitem', distinct=True),
        )

    @admin.display(description='Tipo', ordering='cfop_tipo')
    def tipo_display(self, obj):
        return obj.get_cfop_tipo_display() or '--'

    @admin.display(description='Usos em compras', ordering='usos_compra_total')
    def usos_compra(self, obj):
        total = getattr(obj, 'usos_compra_total', None)
        if total is None:
            total = obj.compraitem_set.count()
        return total

    @admin.display(description='Usos em vendas', ordering='usos_venda_total')
    def usos_venda(self, obj):
        total = getattr(obj, 'usos_venda_total', None)
        if total is None:
            total = obj.vendaitem_set.count()
        return total

    def usos_compra_readonly(self, obj):
        total = getattr(obj, 'usos_compra_total', None)
        if total is None:
            total = obj.compraitem_set.count()
        return f'{total} registros de compra'
    usos_compra_readonly.short_description = 'Usos em compras'

    def usos_venda_readonly(self, obj):
        total = getattr(obj, 'usos_venda_total', None)
        if total is None:
            total = obj.vendaitem_set.count()
        return f'{total} registros de venda'
    usos_venda_readonly.short_description = 'Usos em vendas'

    @admin.display(description='Código CFOP', ordering='cfop_codigo')
    def cfop_codigo_colored(self, obj):
        """Exibe o código CFOP com cor de acordo com o tipo de operação."""
        if not obj.cfop_codigo:
            return '--'
        
        color = obj.get_color_code()
        color_map = {
            'blue': '#0066cc',    # Azul para vendas (5, 6)
            'red': '#cc0000',     # Vermelho para compras (1, 2)
            'green': '#009933',   # Verde para importação/exportação (3, 7)
            'black': '#000000'    # Preto padrão
        }
        
        hex_color = color_map.get(color, '#000000')
        return format_html(
            '<strong style="color: {};">{}</strong>',
            hex_color,
            obj.cfop_codigo
        )
    
    @admin.display(description='Disponível para')
    def disponibilidade_display(self, obj):
        """Mostra em quais módulos o CFOP está disponível."""
        disponibilidade = []
        
        if obj.is_available_for_compra():
            disponibilidade.append('<span style="color: #cc0000;">📥 Compras</span>')
        
        if obj.is_available_for_venda():
            disponibilidade.append('<span style="color: #0066cc;">📤 Vendas</span>')
        
        if obj.is_import_operation():
            disponibilidade.append('<span style="color: #009933;">🌍 Importação</span>')
        
        if obj.is_export_operation():
            disponibilidade.append('<span style="color: #009933;">🌍 Exportação</span>')
        
        if disponibilidade:
            return format_html(' | '.join(disponibilidade))
        return '--'