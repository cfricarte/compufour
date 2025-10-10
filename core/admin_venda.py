from decimal import Decimal

from django.contrib import admin
from django import forms
from django.db.models import Sum, F, DecimalField, ExpressionWrapper
from django.utils.html import format_html
from rangefilter.filters import DateRangeFilter
from .models import Venda, VendaItem, PlanoConta, Romaneio


class VendaAdminForm(forms.ModelForm):
    """
    Formulário customizado para Venda que filtra o Plano de Contas
    para exibir apenas contas de receita (que iniciam com 1).
    """
    class Meta:
        model = Venda
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filtra apenas contas de receita (iniciam com 1)
        if 'plano_conta' in self.fields:
            self.fields['plano_conta'].queryset = PlanoConta.objects.filter(
                plano_conta_numero__startswith='1'
            ).order_by('plano_conta_numero')
            
            self.fields['plano_conta'].help_text = (
                '💰 Apenas contas de RECEITA (iniciam com 1) são exibidas aqui'
            )
        
        # Filtra apenas romaneios com status ABERTO
        if 'romaneio' in self.fields:
            self.fields['romaneio'].queryset = Romaneio.objects.filter(
                status='ABERTO'
            ).order_by('-romaneio_data_emissao')
            
            self.fields['romaneio'].help_text = (
                '📦 Apenas romaneios com status ABERTO são exibidos aqui'
            )


class VendaItemInlineForm(forms.ModelForm):
    venda_item_total = forms.CharField(label='Total', required=False, widget=forms.TextInput(attrs={
        'readonly': 'readonly',
        'class': 'venda-item-total-field',
        'style': 'width: 100px; text-align: right; background-color: #f5f5f5; border: 1px solid #ccc;',
    }))
    
    # ====== CONFIGURAÇÃO DE LARGURAS DOS CAMPOS ======
    # Ajuste as larguras aqui de acordo com sua necessidade:
    # Valores sugeridos: '50%', '100%', '80px', '120px', etc.
    
    FIELD_WIDTHS = {
        'produto': '200px',                # Produto (dropdown)
        'cliente': '200px',                # Cliente (dropdown)
        'cfop': '120px',                   # CFOP (dropdown)
        'plano_conta': '150px',            # Plano de Conta (dropdown)
        'venda_item_qtd': '80px',          # Quantidade
        'venda_item_preco': '80px',        # Preço
        'venda_item_volume': '80px',       # Volume
        'venda_item_total': '80px',
    }
    # ==================================================

    class Meta:
        model = VendaItem
        fields = '__all__'
        widgets = {
            'venda_item_qtd': forms.TextInput(attrs={
                'placeholder': '',
                'class': 'vTextField',
            }),
            'venda_item_preco': forms.TextInput(attrs={
                'placeholder': '',
                'class': 'vTextField',
            }),
            'venda_item_volume': forms.TextInput(attrs={
                'placeholder': '',
                'class': 'vTextField',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filtra os CFOPs disponíveis para venda: 
        # 1. Códigos que iniciam com 5, 6 ou 7
        # 2. OU CFOPs marcados como tipo SAÍDA (tipo=2)
        if 'cfop' in self.fields:
            from django.db.models import Q
            from .models import Cfop
            self.fields['cfop'].queryset = Cfop.objects.filter(
                Q(cfop_codigo__regex=r'^[567]') | Q(cfop_tipo=2)
            ).order_by('cfop_codigo')
            
            # Adiciona um help text explicativo
            self.fields['cfop'].help_text = (
                '🔵 Azul (5, 6): Vendas | '
                '🟢 Verde (7): Exportação | '
                '📤 Tipo SAÍDA'
            )
        
        # Aplicar larguras configuradas a todos os campos
        for field_name, width in self.FIELD_WIDTHS.items():
            field = self.fields.get(field_name)
            if field and hasattr(field, 'widget'):
                current_style = field.widget.attrs.get('style', '')
                # Remove width anterior se existir
                if 'width' in current_style:
                    parts = [p.strip() for p in current_style.split(';') if p.strip() and 'width' not in p.lower()]
                    current_style = '; '.join(parts)
                # Adiciona nova width
                new_style = f"width: {width};"
                if current_style:
                    new_style = f"{current_style}; {new_style}"
                field.widget.attrs['style'] = new_style
        
        # Calcular e exibir total inicial
        if self.instance and self.instance.pk:
            preco = self.instance.venda_item_preco or Decimal('0')
            quantidade = self.instance.venda_item_qtd or Decimal('0')
            total = preco * quantidade
            total_formatado = f"R$ {total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            self.initial['venda_item_total'] = total_formatado
        else:
            self.initial['venda_item_total'] = 'R$ 0,00'


class VendaItemInline(admin.TabularInline):
    model = VendaItem
    form = VendaItemInlineForm
    extra = 1
    # Removido 'plano_conta' do inline - será preenchido automaticamente pela Venda
    fields = ('produto', 'cliente', 'cfop', 'venda_item_qtd', 'venda_item_preco', 'venda_item_total', 'venda_item_volume')
    template = 'admin/core/venda/vendaitem_inline.html'

    def get_formset(self, request, obj=None, **kwargs):
        base_formset = super().get_formset(request, obj, **kwargs)

        class TotalsFormSet(base_formset):
            inline_totals = {
                'quantidade': Decimal('0'),
                'quantidade_display': '0,00',
                'volume': 0,
                'volume_display': '0',
                'valor': Decimal('0'),
                'valor_display': 'R$ 0,00',
            }

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.inline_totals = self._compute_totals()

            @staticmethod
            def _format_decimal(value):
                formatted = f"{value:,.2f}"
                return formatted.replace(',', 'X').replace('.', ',').replace('X', '.')

            @staticmethod
            def _format_integer(value):
                return f"{int(value):,}".replace(',', '.') if value else '0'

            def _compute_totals(self):
                queryset = self.get_queryset()
                aggregates = queryset.aggregate(
                    total_quantidade=Sum('venda_item_qtd'),
                    total_volume=Sum('venda_item_volume'),
                    total_valor=Sum(
                        ExpressionWrapper(
                            F('venda_item_qtd') * F('venda_item_preco'),
                            output_field=DecimalField(max_digits=15, decimal_places=2)
                        )
                    ),
                )
                quantidade = aggregates.get('total_quantidade') or Decimal('0')
                volume = aggregates.get('total_volume') or 0
                valor = aggregates.get('total_valor') or Decimal('0')

                return {
                    'quantidade': quantidade,
                    'quantidade_display': self._format_decimal(quantidade),
                    'volume': volume,
                    'volume_display': self._format_integer(volume),
                    'valor': valor,
                    'valor_display': f"R$ {self._format_decimal(valor)}",
                }

        return TotalsFormSet

    class Media:
        js = ('admin/js/jquery.init.js', 'core/js/venda_item_inline.js')


@admin.register(Venda)
class VendaAdmin(admin.ModelAdmin):
    form = VendaAdminForm  # Aplica o formulário customizado com filtro de receitas
    
    list_display = (
        'venda_id',
        'romaneio',
        'plano_conta',
        'venda_data_emissao',
        'venda_data_vencimento',
        'total_venda',
        'total_itens_display',
        'total_volume_display',
    )
    list_filter = (
        ('venda_data_emissao', DateRangeFilter),
        ('venda_data_vencimento', DateRangeFilter),
        'plano_conta'
    )
    search_fields = ('venda_id', 'romaneio__romaneio_data')
    inlines = [VendaItemInline]
    actions = ['gerar_pdf_detalhado']
    
    # Define os campos do formulário
    fieldsets = (
        ('Informações da Venda', {
            'fields': ('romaneio', 'plano_conta', 'venda_data_emissao', 'venda_data_vencimento')
        }),
    )
    
    def save_formset(self, request, form, formset, change):
        """
        Sobrescreve o método para preencher automaticamente o plano_conta
        dos VendaItems com o plano_conta da Venda.
        """
        instances = formset.save(commit=False)
        venda = form.instance
        
        for instance in instances:
            # Preenche o plano_conta do item com o da venda
            if venda.plano_conta:
                instance.plano_conta = venda.plano_conta
            instance.save()
        
        # Salvar os objetos marcados para exclusão
        formset.save_m2m()
        for obj in formset.deleted_objects:
            obj.delete()

    def get_queryset(self, request):
        from django.db.models import Subquery, OuterRef
        from django.db.models.functions import Coalesce
        
        qs = super().get_queryset(request)

        # Subquery: total de itens vendidos (quantidade)
        total_itens = Subquery(
            VendaItem.objects.filter(venda=OuterRef('pk'))
            .values('venda')
            .annotate(total=Sum('venda_item_qtd'))
            .values('total')[:1],
            output_field=DecimalField(max_digits=15, decimal_places=2)
        )

        # Subquery: total de volume
        total_volume = Subquery(
            VendaItem.objects.filter(venda=OuterRef('pk'))
            .values('venda')
            .annotate(total=Sum('venda_item_volume'))
            .values('total')[:1],
            output_field=DecimalField(max_digits=15, decimal_places=2)
        )

        return qs.annotate(
            total_itens=Coalesce(total_itens, Decimal('0')),
            total_volume_vendido=Coalesce(total_volume, Decimal('0')),
        )

    def total_venda(self, obj):
        """Total financeiro da venda"""
        total = VendaItem.objects.filter(
            venda=obj,
            cfop__cfop_integracao__icontains="receber"
        ).aggregate(
            total=Sum(
                ExpressionWrapper(
                    F('venda_item_qtd') * F('venda_item_preco'),
                    output_field=DecimalField(max_digits=15, decimal_places=2)
                )
            )
        )['total'] or 0
        return f"R$ {total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    total_venda.short_description = "Total Venda (R$)"

    def total_itens_display(self, obj):
        """Quantidade total de itens vendidos"""
        total_qtd = obj.total_itens or 0
        return f"{total_qtd:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    total_itens_display.short_description = 'Qtd. Total'
    total_itens_display.admin_order_field = 'total_itens'

    def total_volume_display(self, obj):
        """Volume total de itens vendidos"""
        volume = obj.total_volume_vendido or 0
        return f"{int(volume):,}".replace(',', '.') if volume else '0'
    total_volume_display.short_description = 'Volume Total'
    total_volume_display.admin_order_field = 'total_volume_vendido'

    def gerar_pdf_detalhado(self, request, queryset):
        """Gera PDF detalhado das vendas selecionadas"""
        from django.http import HttpResponse
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from io import BytesIO
        from datetime import datetime
        from xml.sax.saxutils import escape

        # Criar buffer para o PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=10*mm, bottomMargin=10*mm)
        elements = []
        styles = getSampleStyleSheet()

        # Estilos customizados
        titulo_style = ParagraphStyle(
            'TituloCustom',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#1f4788'),
            alignment=TA_CENTER,
            spaceAfter=12
        )

        subtitulo_style = ParagraphStyle(
            'SubtituloCustom',
            parent=styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#333333'),
            alignment=TA_LEFT,
            spaceAfter=8
        )

        info_value_style = ParagraphStyle(
            'InfoValue',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=11,
            alignment=TA_LEFT,
            spaceAfter=0,
            spaceBefore=0,
            wordWrap='CJK',
        )

        table_text_style = ParagraphStyle(
            'TableText',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=6,
            leading=7.2,
            alignment=TA_LEFT,
            spaceAfter=0,
            spaceBefore=0,
            wordWrap='CJK',
        )

        def build_paragraph(value, style):
            safe_value = 'N/A' if value in (None, '') else str(value)
            safe_value = escape(safe_value).replace('\n', '<br/>')
            return Paragraph(safe_value, style)

        # Iterar sobre cada venda selecionada
        for idx, venda in enumerate(queryset):
            # Título
            titulo = Paragraph(f"DETALHAMENTO DA VENDA #{venda.venda_id}", titulo_style)
            elements.append(titulo)
            elements.append(Spacer(1, 5*mm))

            # Informações da Venda
            info_data = [
                ['Data de Emissão:', venda.venda_data_emissao.strftime('%d/%m/%Y') if venda.venda_data_emissao else 'N/A'],
                ['Data de Vencimento:', venda.venda_data_vencimento.strftime('%d/%m/%Y') if venda.venda_data_vencimento else 'N/A'],
            ]

            if venda.romaneio:
                romaneio_parts = [f"Romaneio #{venda.romaneio.romaneio_id}"]
                if venda.romaneio.romaneio_data_emissao:
                    romaneio_parts.append(venda.romaneio.romaneio_data_emissao.strftime('%d/%m/%Y'))
                info_data.append(['Romaneio:', ' - '.join(romaneio_parts)])

            for row in info_data:
                row[1] = build_paragraph(row[1], info_value_style)

            info_table = Table(info_data, colWidths=[55*mm, 125*mm])
            info_table.setStyle(TableStyle([
                ('FONT', (0, 0), (0, -1), 'Helvetica-Bold', 9),
                ('FONT', (1, 0), (1, -1), 'Helvetica', 9),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ]))
            elements.append(info_table)
            elements.append(Spacer(1, 5*mm))

            # Itens da Venda
            subtitulo = Paragraph("ITENS DA VENDA", subtitulo_style)
            elements.append(subtitulo)
            elements.append(Spacer(1, 3*mm))

            # Cabeçalho da tabela de itens
            itens_data = [['Cliente', 'Produto', 'CFOP - Operação', 'Qtd', 'Preço Unit.', 'Volume', 'Total']]

            # Buscar itens da venda
            itens = VendaItem.objects.filter(venda=venda).select_related('cliente', 'produto', 'cfop')

            total_geral = Decimal('0')
            total_qtd = Decimal('0')
            total_volume = 0

            for item in itens:
                cliente_nome = item.cliente.cliente_nome if item.cliente else 'N/A'
                produto_nome = item.produto.produto_nome if item.produto else 'N/A'

                cfop_parts = []
                if item.cfop:
                    if item.cfop.cfop_codigo:
                        cfop_parts.append(item.cfop.cfop_codigo)
                    if item.cfop.cfop_operacao:
                        cfop_parts.append(item.cfop.cfop_operacao)
                cfop_text = '\n'.join(cfop_parts) if cfop_parts else 'N/A'

                qtd = item.venda_item_qtd or Decimal('0')
                preco = item.venda_item_preco or Decimal('0')
                volume = item.venda_item_volume or 0
                total_item = qtd * preco

                total_geral += total_item
                total_qtd += qtd
                total_volume += volume

                itens_data.append([
                    build_paragraph(cliente_nome, table_text_style),
                    build_paragraph(produto_nome, table_text_style),
                    build_paragraph(cfop_text, table_text_style),
                    f"{qtd:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    f"R$ {preco:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    str(volume),
                    f"R$ {total_item:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                ])

            # Linha de totais
            itens_data.append([
                '', '', 'TOTAIS:',
                f"{total_qtd:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                '',
                str(total_volume),
                f"R$ {total_geral:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
            ])

            # Criar tabela de itens
            itens_table = Table(itens_data, colWidths=[34*mm, 38*mm, 38*mm, 18*mm, 24*mm, 12*mm, 26*mm])
            itens_table.setStyle(TableStyle([
                # Cabeçalho
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 7),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                # Dados
                ('FONT', (0, 1), (-1, -2), 'Helvetica', 6),
                ('ALIGN', (3, 1), (3, -1), 'RIGHT'),  # Qtd
                ('ALIGN', (4, 1), (4, -1), 'RIGHT'),  # Preço
                ('ALIGN', (5, 1), (5, -1), 'CENTER'), # Volume
                ('ALIGN', (6, 1), (6, -1), 'RIGHT'),  # Total
                ('VALIGN', (0, 1), (2, -2), 'TOP'),   # Ajusta textos múltiplas linhas
                # Linha de totais
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f0f0f0')),
                ('FONT', (0, -1), (-1, -1), 'Helvetica-Bold', 7),
                ('ALIGN', (2, -1), (2, -1), 'RIGHT'),
                ('ALIGN', (3, -1), (3, -1), 'RIGHT'),
                ('ALIGN', (5, -1), (5, -1), 'CENTER'),
                ('ALIGN', (6, -1), (6, -1), 'RIGHT'),
                # Bordas
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]))
            elements.append(itens_table)
            elements.append(Spacer(1, 5*mm))

            # Adicionar quebra de página se não for a última venda
            if idx < len(queryset) - 1:
                elements.append(PageBreak())

        # Gerar PDF
        doc.build(elements)

        # Preparar resposta
        buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')

        if len(queryset) == 1:
            filename = f'venda_{queryset[0].venda_id}_detalhada.pdf'
        else:
            filename = f'vendas_detalhadas_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'

        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response
    gerar_pdf_detalhado.short_description = "Gerar PDF detalhado das vendas selecionadas"






