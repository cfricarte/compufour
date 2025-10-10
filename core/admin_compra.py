from django.contrib import admin
from django import forms
from django.db.models import Sum, F, DecimalField, ExpressionWrapper, Count, Case, When, Max
from django.db.models.functions import Coalesce
from django.template.response import TemplateResponse
from django.urls import reverse
from django.db import transaction
from django.utils.translation import ngettext
from django.db.models import Window
from django.utils import timezone
from django.utils.html import format_html
from datetime import date
from django.db.models import DecimalField
from django.db.models import Subquery, OuterRef
from decimal import Decimal
from rangefilter.filters import DateRangeFilter
from .models import Compra, CompraItem, Romaneio, VendaItem, PlanoConta
from .forms import CompraItemForm


class CompraAdminForm(forms.ModelForm):
    """
    Formulário customizado para Compra que filtra o Plano de Contas
    para exibir apenas contas de despesa (que iniciam com 3).
    """
    class Meta:
        model = Compra
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filtra apenas contas de despesa (iniciam com 3)
        if 'plano_conta' in self.fields:
            self.fields['plano_conta'].queryset = PlanoConta.objects.filter(
                plano_conta_numero__startswith='3'
            ).order_by('plano_conta_numero')
            
            self.fields['plano_conta'].help_text = (
                '💸 Apenas contas de DESPESA (iniciam com 3) são exibidas aqui'
            )


class CompraItemInline(admin.TabularInline):
    model = CompraItem
    form = CompraItemForm
    extra = 1
    template = 'admin/core/compra/compraitem_inline.html'

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
                    total_quantidade=Sum('compra_item_qtd'),
                    total_volume=Sum('compra_item_volume'),
                    total_valor=Sum(
                        ExpressionWrapper(
                            F('compra_item_qtd') * F('compra_item_preco'),
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


class RomaneioInline(admin.TabularInline):
    model = Romaneio
    extra = 0


@admin.register(Compra)
class CompraAdmin(admin.ModelAdmin):
    form = CompraAdminForm  # Aplica o formulário customizado com filtro de despesas
    
    list_display = (
        'empresa',
        'compra_numero',
        'fornecedor',
        'compra_data_entrada',
        'total_compra',
        'total_venda_display',   # NOVO
        'lucro_display',         # NOVO
        'total_itens_comprados_display',
        'total_itens_vendidos_display',
        'saldo_itens_display',
    )
    list_filter = (
        'empresa',
        ('compra_data_entrada', DateRangeFilter),
        'fornecedor',
        'plano_conta'
    )
    search_fields = (
        'compra_numero',
        'fornecedor__fornecedor_nome',
        'empresa__empresa_nome',
        'plano_conta__plano_conta_nome',
        'plano_conta__plano_conta_numero',
        'compra_prazo_pagamento',
        'compraitem__produto__produto_nome',
        'compraitem__produto__grupo_mercadoria__grupo_mercadoria_nome',
        'romaneio__veiculo__veiculo_placa',
        'romaneio__funcionario__funcionario_nome',
    )
    inlines = [CompraItemInline, RomaneioInline]
    actions = ['gerar_pdf_detalhado']

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        # Subquery: total comprado (quantidade)
        total_comprado = Subquery(
            CompraItem.objects.filter(compra=OuterRef('pk'))
            .values('compra')
            .annotate(total=Sum('compra_item_qtd'))
            .values('total')[:1],
            output_field=DecimalField(max_digits=15, decimal_places=2)
        )

        # Subquery: total vendido (quantidade)
        total_vendido = Subquery(
            VendaItem.objects.filter(venda__romaneio__compra=OuterRef('pk'))
            .values('venda__romaneio__compra')
            .annotate(total=Sum('venda_item_qtd'))
            .values('total')[:1],
            output_field=DecimalField(max_digits=15, decimal_places=2)
        )

        # Subquery: valor total da venda (R$)
        total_venda = Subquery(
            VendaItem.objects.filter(venda__romaneio__compra=OuterRef('pk'))
            .values('venda__romaneio__compra')
            .annotate(total=Sum(
                ExpressionWrapper(
                    F('venda_item_qtd') * F('venda_item_preco'),
                    output_field=DecimalField(max_digits=15, decimal_places=2)
                )
            ))
            .values('total')[:1],
            output_field=DecimalField(max_digits=15, decimal_places=2)
        )

        return qs.annotate(
            total_comprado=total_comprado,
            total_vendido=total_vendido,
            total_venda=total_venda,
            saldo_final=ExpressionWrapper(
                F('total_comprado') - Coalesce(total_vendido, 0),
                output_field=DecimalField(max_digits=15, decimal_places=2)
            )
        )

    # Quantidade comprada
    def total_itens_comprados_display(self, obj):
        total_qtd = obj.total_comprado or 0
        return f"{total_qtd:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    total_itens_comprados_display.short_description = 'Qtd. Comprada'
    total_itens_comprados_display.admin_order_field = 'total_comprado'

    # Quantidade vendida
    def total_itens_vendidos_display(self, obj):
        total_qtd = obj.total_vendido or 0
        return f"{total_qtd:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    total_itens_vendidos_display.short_description = 'Qtd. Vendida'
    total_itens_vendidos_display.admin_order_field = 'total_vendido'

    # Saldo de itens
    def saldo_itens_display(self, obj):
        saldo = obj.saldo_final or 0
        cor = 'green' if saldo >= 0 else 'red'
        saldo_formatado = f"{saldo:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return format_html(f'<b style="color: {cor};">{saldo_formatado}</b>')
    saldo_itens_display.short_description = 'Saldo de Itens'
    saldo_itens_display.admin_order_field = 'saldo_final'

    # Total financeiro da compra
    def total_compra(self, obj):
        total = CompraItem.objects.filter(
            compra=obj,
            cfop__cfop_integracao__icontains="pagar"
        ).aggregate(
            total=Sum(
                ExpressionWrapper(
                    F('compra_item_qtd') * F('compra_item_preco'),
                    output_field=DecimalField(max_digits=15, decimal_places=2)
                )
            )
        )['total'] or 0
        return f"R$ {total:,.2f}"
    total_compra.short_description = "Total Compra (R$)"

    # Total financeiro da venda
    def total_venda_display(self, obj):
        total = obj.total_venda or 0
        return f"R$ {total:,.2f}"
    total_venda_display.short_description = "Total Venda (R$)"
    total_venda_display.admin_order_field = 'total_venda'

    # Lucro
    def lucro_display(self, obj):
        total_compra = CompraItem.objects.filter(
            compra=obj,
            cfop__cfop_integracao__icontains="pagar"
        ).aggregate(
            total=Sum(
                ExpressionWrapper(
                    F('compra_item_qtd') * F('compra_item_preco'),
                    output_field=DecimalField(max_digits=15, decimal_places=2)
                )
            )
        )['total'] or 0

        total_venda = obj.total_venda or 0
        lucro = total_venda - total_compra

        cor = 'green' if lucro >= 0 else 'red'
        lucro_formatado = f"R$ {lucro:,.2f}"
        return format_html(f'<b style="color: {cor};">{lucro_formatado}</b>')
    lucro_display.short_description = "Lucro (R$)"

    def gerar_pdf_detalhado(self, request, queryset):
        """Gera PDF detalhado das compras selecionadas"""
        from django.http import HttpResponse
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
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

        # Iterar sobre cada compra selecionada
        for idx, compra in enumerate(queryset):
            # Título
            titulo = Paragraph(f"DETALHAMENTO DA COMPRA #{compra.compra_numero}", titulo_style)
            elements.append(titulo)
            elements.append(Spacer(1, 5*mm))

            # Informações da Compra
            info_data = [
                ['Empresa:', compra.empresa.empresa_nome if compra.empresa else 'N/A'],
                ['Fornecedor:', compra.fornecedor.fornecedor_nome if compra.fornecedor else 'N/A'],
                ['Data de Entrada:', compra.compra_data_entrada.strftime('%d/%m/%Y') if compra.compra_data_entrada else 'N/A'],
            ]

            if compra.compra_data_saida_fornecedor:
                info_data.append(['Data de Saída do Fornecedor:', compra.compra_data_saida_fornecedor.strftime('%d/%m/%Y')])

            if compra.compra_data_base:
                info_data.append(['Data Base:', compra.compra_data_base.strftime('%d/%m/%Y')])

            if compra.compra_prazo_pagamento:
                info_data.append(['Prazo de Pagamento:', compra.compra_prazo_pagamento])

            for row in info_data:
                row[1] = build_paragraph(row[1], info_value_style)

            info_table = Table(info_data, colWidths=[60*mm, 120*mm])
            info_table.setStyle(TableStyle([
                ('FONT', (0, 0), (0, -1), 'Helvetica-Bold', 9),
                ('FONT', (1, 0), (1, -1), 'Helvetica', 9),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ]))
            elements.append(info_table)
            elements.append(Spacer(1, 5*mm))

            # Itens da Compra
            subtitulo = Paragraph("ITENS DA COMPRA", subtitulo_style)
            elements.append(subtitulo)
            elements.append(Spacer(1, 3*mm))

            # Cabeçalho da tabela de itens
            itens_data = [['Produto', 'CFOP - Operação', 'Qtd', 'Preço Unit.', 'Volume', 'Total']]

            # Buscar itens da compra
            itens = CompraItem.objects.filter(compra=compra).select_related('produto', 'cfop')

            total_geral = Decimal('0')
            total_qtd = Decimal('0')
            total_volume = 0

            for item in itens:
                produto_nome = item.produto.produto_nome if item.produto else 'N/A'

                cfop_parts = []
                if item.cfop:
                    if item.cfop.cfop_codigo:
                        cfop_parts.append(item.cfop.cfop_codigo)
                    if item.cfop.cfop_operacao:
                        cfop_parts.append(item.cfop.cfop_operacao)
                cfop_text = '\n'.join(cfop_parts) if cfop_parts else 'N/A'

                qtd = item.compra_item_qtd or Decimal('0')
                preco = item.compra_item_preco or Decimal('0')
                volume = item.compra_item_volume or 0
                total_item = qtd * preco

                total_geral += total_item
                total_qtd += qtd
                total_volume += volume

                itens_data.append([
                    build_paragraph(produto_nome, table_text_style),
                    build_paragraph(cfop_text, table_text_style),
                    f"{qtd:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    f"R$ {preco:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    str(volume),
                    f"R$ {total_item:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                ])

            # Linha de totais
            itens_data.append([
                '', 'TOTAIS:',
                f"{total_qtd:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                '',
                str(total_volume),
                f"R$ {total_geral:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
            ])

            # Criar tabela de itens
            itens_table = Table(itens_data, colWidths=[55*mm, 38*mm, 20*mm, 25*mm, 15*mm, 26*mm])
            itens_table.setStyle(TableStyle([
                # Cabeçalho
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 7),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                # Dados
                ('FONT', (0, 1), (-1, -2), 'Helvetica', 6),
                ('ALIGN', (2, 1), (2, -1), 'RIGHT'),  # Qtd
                ('ALIGN', (3, 1), (3, -1), 'RIGHT'),  # Preço
                ('ALIGN', (4, 1), (4, -1), 'CENTER'), # Volume
                ('ALIGN', (5, 1), (5, -1), 'RIGHT'),  # Total
                ('VALIGN', (0, 1), (1, -2), 'TOP'),   # Alinha textos multilinha
                # Linha de totais
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f0f0f0')),
                ('FONT', (0, -1), (-1, -1), 'Helvetica-Bold', 7),
                ('ALIGN', (1, -1), (1, -1), 'RIGHT'),
                ('ALIGN', (2, -1), (2, -1), 'RIGHT'),
                ('ALIGN', (4, -1), (4, -1), 'CENTER'),
                ('ALIGN', (5, -1), (5, -1), 'RIGHT'),
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

            # Contas a Pagar
            from .models import ContaPagar
            contas_pagar = ContaPagar.objects.filter(compra=compra).select_related('plano_conta')

            if contas_pagar.exists():
                subtitulo_contas = Paragraph("CONTAS A PAGAR", subtitulo_style)
                elements.append(subtitulo_contas)
                elements.append(Spacer(1, 3*mm))

                # Cabeçalho da tabela de contas a pagar
                contas_data = [['N° Doc.', 'Histórico', 'Dt. Emissão', 'Dt. Vencimento', 'Valor', 'Portador']]

                total_contas = Decimal('0')

                for conta in contas_pagar:
                    num_doc = conta.conta_pagar_numero_documento or 'N/A'
                    historico = conta.conta_pagar_historico or 'N/A'
                    dt_emissao = conta.conta_pagar_data_emissao.strftime('%d/%m/%Y') if conta.conta_pagar_data_emissao else 'N/A'
                    dt_vencimento = conta.conta_pagar_data_vencimento.strftime('%d/%m/%Y') if conta.conta_pagar_data_vencimento else 'N/A'
                    valor = conta.conta_pagar_valor or Decimal('0')
                    portador = conta.conta_pagar_portador or 'N/A'

                    total_contas += valor

                    contas_data.append([
                        build_paragraph(num_doc, table_text_style),
                        build_paragraph(historico, table_text_style),
                        dt_emissao,
                        dt_vencimento,
                        f"R$ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        build_paragraph(portador, table_text_style),
                    ])

                # Linha de totais
                contas_data.append([
                    '', '', '', 'TOTAL:',
                    f"R$ {total_contas:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    '',
                ])

                # Criar tabela de contas a pagar
                contas_table = Table(contas_data, colWidths=[28*mm, 55*mm, 24*mm, 28*mm, 30*mm, 25*mm])
                contas_table.setStyle(TableStyle([
                    # Cabeçalho
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 8),
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                    # Dados
                    ('FONT', (0, 1), (-1, -2), 'Helvetica', 7),
                    ('ALIGN', (2, 1), (2, -1), 'CENTER'),  # Data Emissão
                    ('ALIGN', (3, 1), (3, -1), 'CENTER'),  # Data Vencimento
                    ('ALIGN', (4, 1), (4, -1), 'RIGHT'),   # Valor
                    ('VALIGN', (0, 1), (1, -2), 'TOP'),    # Ajusta textos longos
                    ('VALIGN', (5, 1), (5, -2), 'TOP'),
                    # Linha de totais
                    ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f0f0f0')),
                    ('FONT', (0, -1), (-1, -1), 'Helvetica-Bold', 8),
                    ('ALIGN', (3, -1), (3, -1), 'RIGHT'),
                    ('ALIGN', (4, -1), (4, -1), 'RIGHT'),
                    # Bordas
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 3),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                ]))
                elements.append(contas_table)
                elements.append(Spacer(1, 3*mm))

            # Adicionar quebra de página se não for a última compra
            if idx < len(queryset) - 1:
                elements.append(PageBreak())

        # Gerar PDF
        doc.build(elements)

        # Preparar resposta
        buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')

        if len(queryset) == 1:
            filename = f'compra_{queryset[0].compra_numero}_detalhada.pdf'
        else:
            filename = f'compras_detalhadas_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'

        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        self.message_user(
            request,
            ngettext(
                '%d compra exportada para PDF com sucesso.',
                '%d compras exportadas para PDF com sucesso.',
                len(queryset),
            ) % len(queryset),
        )

        return response
    gerar_pdf_detalhado.short_description = "Gerar PDF detalhado das compras selecionadas"


