from django.contrib import admin
from django.contrib import messages
from django import forms
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.conf import settings
from django.template.response import TemplateResponse
from django.urls import reverse
from django.db import transaction
from django.utils.translation import ngettext
from django.db.models import Window, F, Sum, Q, Value, ExpressionWrapper, Count, Case, When, Max
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.html import format_html
from datetime import date
from django.db.models import DecimalField
from decimal import Decimal
from rangefilter.filters import DateRangeFilter
from .models import ContaPagar, Pagamento, Empresa, Fornecedor, Compra, PlanoConta, Caixa


class PagamentoInline(admin.TabularInline):
    model = Pagamento
    extra = 1


class StatusFilter(admin.SimpleListFilter):
    title = 'Status de Pagamento'
    parameter_name = 'status_pagamento'

    def lookups(self, request, model_admin):
        return (
            ('paga', 'Paga'),
            ('parcial', 'Paga Parcialmente'),
            ('pendente_atrasada', 'Pendente (Atrasada)'),
            ('pendente_hoje', 'Pendente (Vencendo Hoje)'),
            ('pendente_a_vencer', 'Pendente (A Vencer)'),
        )

    def queryset(self, request, queryset):
        qs = queryset.annotate(
            total_pago=Coalesce(
                Sum('pagamento__pagamento_valor_pago'),
                Value(Decimal('0')),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        )
        today = date.today()

        if self.value() == 'paga':
            return qs.filter(total_pago__gte=F('conta_pagar_valor'))

        if self.value() == 'parcial':
            return qs.filter(
                total_pago__gt=0,
                total_pago__lt=F('conta_pagar_valor')
            )

        if self.value() == 'pendente_atrasada':
            return qs.filter(
                Q(total_pago__lt=F('conta_pagar_valor')) | Q(total_pago__isnull=True),
                conta_pagar_data_vencimento__lt=today
            )

        if self.value() == 'pendente_hoje':
            return qs.filter(
                Q(total_pago__lt=F('conta_pagar_valor')) | Q(total_pago__isnull=True),
                conta_pagar_data_vencimento=today
            )

        if self.value() == 'pendente_a_vencer':
            return qs.filter(
                Q(total_pago__lt=F('conta_pagar_valor')) | Q(total_pago__isnull=True),
                conta_pagar_data_vencimento__gt=today
            )

        return queryset


@admin.register(ContaPagar)
class ContaPagarAdmin(admin.ModelAdmin):
    list_display = (
        'empresa',
        'plano_conta',
        'conta_pagar_numero_documento',
        #'conta_pagar_id',
        'fornecedor',
        'conta_pagar_valor',
        'conta_pagar_data_vencimento',
        'total_pago_display',
        'saldo_devedor_display',
        'exibir_status'
    )
    search_fields = ('fornecedor__fornecedor_nome', 'conta_pagar_historico')
    list_filter = (
        StatusFilter,
        ('conta_pagar_data_vencimento', DateRangeFilter),
        ('conta_pagar_data_emissao', DateRangeFilter),
        'empresa',
        'plano_conta',
        'fornecedor'
    )
    inlines = [PagamentoInline]
    actions = ['pagar_contas_selecionadas']

    _plano_conta_padrao_cache = None

    def _obter_plano_para_pagamento(self, conta):
        if getattr(conta, 'plano_conta_id', None):
            return conta.plano_conta
        if getattr(conta, 'compra', None) and getattr(conta.compra, 'plano_conta_id', None):
            return conta.compra.plano_conta
        if self._plano_conta_padrao_cache is None:
            self._plano_conta_padrao_cache = PlanoConta.objects.filter(pk=1).first()
        return self._plano_conta_padrao_cache

    def _historico_pagamento(self, pagamento):
        conta = pagamento.conta_pagar
        numero = conta.conta_pagar_numero_documento or conta.conta_pagar_id
        return f'Pagamento #{pagamento.pk} da conta {numero}'

    def _registrar_pagamento_no_caixa(self, request, pagamento):
        valor = pagamento.pagamento_valor_pago or Decimal('0')
        if valor <= Decimal('0'):
            self._remover_pagamento_caixa(pagamento)
            return
        conta = pagamento.conta_pagar
        plano = self._obter_plano_para_pagamento(conta)
        if plano is None:
            if request is not None:
                self.message_user(
                    request,
                    'Não foi possível registrar o pagamento no caixa porque o plano de contas Não foi definido.',
                    level=messages.WARNING,
                )
            return
        data_pagamento = pagamento.pagamento_data_pagamento or timezone.localdate()
        historico = self._historico_pagamento(pagamento)
        Caixa.objects.update_or_create(
            empresa=conta.empresa,
            caixa_historico=historico,
            defaults={
                'plano_conta': plano,
                'caixa_data_emissao': data_pagamento,
                'caixa_valor_entrada': Decimal('0'),
                'caixa_valor_saida': valor,
            },
        )

    def _remover_pagamento_caixa(self, pagamento):
        conta = pagamento.conta_pagar
        if not getattr(conta, 'pk', None):
            return
        historico = self._historico_pagamento(pagamento)
        Caixa.objects.filter(empresa=conta.empresa, caixa_historico=historico).delete()

    def save_formset(self, request, form, formset, change):
        if formset.model is Pagamento:
            instances = formset.save(commit=False)
            for obj in formset.deleted_objects:
                self._remover_pagamento_caixa(obj)
                obj.delete()
            for obj in instances:
                if not obj.pagamento_data_pagamento:
                    obj.pagamento_data_pagamento = timezone.localdate()
                obj.conta_pagar = form.instance
                obj.save()
                self._registrar_pagamento_no_caixa(request, obj)
            formset.save_m2m()
        else:
            super().save_formset(request, form, formset, change)

    @admin.action(description='Pagar contas selecionadas automaticamente')
    def pagar_contas_selecionadas(self, request, queryset):
        queryset = (
            queryset
            .select_related('empresa', 'plano_conta', 'compra', 'compra__plano_conta')
            .annotate(
                total_pago=Coalesce(
                    Sum('pagamento__pagamento_valor_pago'),
                    Value(Decimal('0')),
                    output_field=DecimalField(max_digits=10, decimal_places=2)
                )
            )
        )

        if request.POST.get('post'):
            hoje = date.today()
            contas_pagas = 0
            contas_ja_quitadas = 0
            contas_sem_valor = 0
            contas_sem_plano = 0
            plano_conta_padrao = None

            with transaction.atomic():
                for conta in queryset.select_for_update():
                    valor_total = conta.conta_pagar_valor or Decimal('0')
                    if valor_total <= Decimal('0'):
                        contas_sem_valor += 1
                        continue

                    total_pago = conta.total_pago or Decimal('0')
                    saldo = valor_total - total_pago
                    if saldo <= Decimal('0'):
                        contas_ja_quitadas += 1
                        continue

                    if plano_conta_padrao is None:
                        plano_conta_padrao = PlanoConta.objects.filter(pk=1).first()
                    plano_caixa = (
                        conta.plano_conta
                        or (getattr(conta, 'compra', None) and getattr(conta.compra, 'plano_conta', None))
                        or plano_conta_padrao
                    )
                    if plano_caixa is None:
                        contas_sem_plano += 1
                        continue

                    pagamento = Pagamento.objects.create(
                        conta_pagar=conta,
                        pagamento_data_pagamento=hoje,
                        pagamento_valor_pago=saldo,
                        pagamento_forma_pagamento='Automatico (admin)',
                        pagamento_observacao='Pagamento gerado pela acao em massa do admin.',
                    )

                    historico_pagamento = self._historico_pagamento(pagamento)
                    Caixa.objects.update_or_create(
                        empresa=conta.empresa,
                        caixa_historico=historico_pagamento,
                        defaults={
                            'plano_conta': plano_caixa,
                            'caixa_data_emissao': hoje,
                            'caixa_valor_entrada': Decimal('0'),
                            'caixa_valor_saida': saldo,
                        },
                    )
                    contas_pagas += 1

            if contas_pagas:
                self.message_user(
                    request,
                    ngettext(
                        '%d conta a pagar foi quitada automaticamente.',
                        '%d contas a pagar foram quitadas automaticamente.',
                        contas_pagas,
                    ) % contas_pagas,
                    messages.SUCCESS,
                )
            if contas_ja_quitadas:
                self.message_user(
                    request,
                    ngettext(
                        '%d conta ja estava quitada e foi ignorada.',
                        '%d contas ja estavam quitadas e foram ignoradas.',
                        contas_ja_quitadas,
                    ) % contas_ja_quitadas,
                    messages.WARNING,
                )
            if contas_sem_valor:
                self.message_user(
                    request,
                    ngettext(
                        '%d conta sem valor definido nao pode ser paga.',
                        '%d contas sem valor definido nao puderam ser pagas.',
                        contas_sem_valor,
                    ) % contas_sem_valor,
                    messages.WARNING,
                )
            if contas_sem_plano:
                self.message_user(
                    request,
                    ngettext(
                        '%d conta sem plano de contas definido nao pode ser registrada no caixa.',
                        '%d contas sem plano de contas definido nao puderam ser registradas no caixa.',
                        contas_sem_plano,
                    ) % contas_sem_plano,
                    messages.WARNING,
                )
            if (
                contas_pagas == 0
                and contas_ja_quitadas == 0
                and contas_sem_valor == 0
                and contas_sem_plano == 0
            ):
                self.message_user(
                    request,
                    'Nenhuma acao foi realizada.',
                    messages.INFO,
                )
            return None

        contas = list(queryset)
        if not contas:
            self.message_user(
                request,
                'Nenhuma conta foi selecionada para pagamento.',
                messages.WARNING,
            )
            return None

        resumo_contas = []
        total_valor = Decimal('0')
        total_pago = Decimal('0')
        total_saldo = Decimal('0')

        for conta in contas:
            valor_total = conta.conta_pagar_valor or Decimal('0')
            valor_pago = conta.total_pago or Decimal('0')
            saldo = max(Decimal('0'), valor_total - valor_pago)
            total_valor += valor_total
            total_pago += valor_pago
            total_saldo += saldo
            resumo_contas.append(
                {
                    'obj': conta,
                    'valor_total': valor_total,
                    'valor_pago': valor_pago,
                    'saldo': saldo,
                }
            )

        opts = self.model._meta
        cancel_url = reverse(f"admin:{opts.app_label}_{opts.model_name}_changelist")

        context = {
            **self.admin_site.each_context(request),
            'opts': opts,
            'contas': resumo_contas,
            'total_valor': total_valor,
            'total_pago': total_pago,
            'total_saldo': total_saldo,
            'action_checkbox_name': ACTION_CHECKBOX_NAME,
            'selected_ids': request.POST.getlist(ACTION_CHECKBOX_NAME),
            'select_across': request.POST.get('select_across'),
            'index': request.POST.get('index'),
            'action_name': 'pagar_contas_selecionadas',
            'title': 'Confirmar pagamento das contas selecionadas',
            'cancel_url': cancel_url,
        }
        request.current_app = self.admin_site.name
        return TemplateResponse(
            request,
            'admin/core/contapagar/confirmar_pagamento.html',
            context,
        )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(
            total_pago=Coalesce(
                Sum('pagamento__pagamento_valor_pago'),
                Value(Decimal('0')),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        )
        return qs

    def total_pago_display(self, obj):
        return f"R$ {obj.total_pago:.2f}"

    total_pago_display.short_description = 'Total Pago'
    total_pago_display.admin_order_field = 'total_pago'

    def saldo_devedor_display(self, obj):
        saldo = (obj.conta_pagar_valor or 0) - obj.total_pago
        return f"R$ {saldo:.2f}"

    saldo_devedor_display.short_description = 'Saldo Devedor'

    def exibir_status(self, obj):
        valor_total = obj.conta_pagar_valor or 0
        total_pago = obj.total_pago

        if total_pago >= valor_total and valor_total > 0:
            return format_html('<span style="color: green; font-weight: bold;">&#x2714; Paga</span>')

        status_pendente = ''
        if obj.conta_pagar_data_vencimento:
            today = date.today()
            if obj.conta_pagar_data_vencimento < today:
                status_pendente = format_html('<span style="color: red; font-weight: bold;">&#x26A0; Atrasada</span>')
            elif obj.conta_pagar_data_vencimento == today:
                status_pendente = format_html('<span style="color: orange; font-weight: bold;">&#x23F3; Vencendo Hoje</span>')
            else:
                status_pendente = format_html('<span style="color: blue;">&#x1F4C5; A Vencer</span>')

        if total_pago > 0:
            return format_html(
                '<span style="color: purple; font-weight: bold;">&#x25CF; Parcial</span><br>{}', status_pendente
            )

        return status_pendente if status_pendente else 'Pendente'

    exibir_status.short_description = 'Status'