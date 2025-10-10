from django.contrib import admin
from django.contrib import messages
from django import forms
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.conf import settings
from .models import (
    Empresa, Fornecedor, Compra, ContaPagar, ContasReceber, Romaneio, Venda, Cliente,
    Produto, Convenio, GrupoMercadoria, Funcionario, Veiculo, PlanoConta, Cfop,
    CompraItem, Pagamento, Recebimento, Caixa, VendaItem, ConvenioGrupoMercadoria,
    ClienteConvenioGrupoMercadoria
)
from decimal import Decimal
from django.template.response import TemplateResponse
from django.urls import reverse
from django.db import transaction
from django.utils.translation import ngettext
from django.db.models import Window, F, Sum, Q, Value, ExpressionWrapper, Count, Case, When, Max
from django.utils import timezone
from django.db.models.functions import Coalesce
from django.utils.html import format_html
from datetime import date
from django.db.models import DecimalField
from django.db.models import Subquery, OuterRef
from functools import lru_cache


# Personalização dos títulos do site de administração
admin.site.site_header = 'Administração Compufour'
admin.site.site_title = 'Painel Administrativo'
admin.site.index_title = 'Bem-vindo ao Painel de Administração'


_model_admin_order_pathed = getattr(admin.AdminSite.get_app_list, '_uses_custom_ordering', False)
if not _model_admin_order_pathed:
    _original_get_app_list = admin.AdminSite.get_app_list

    @lru_cache(maxsize=1)
    def _admin_menu_orders():
        jazzmin_order = getattr(settings, 'JAZZMIN_SETTINGS', {}).get('order_with_respect_to', [])
        app_order = list(getattr(settings, 'ADMIN_MENU_APP_ORDER', []))
        model_order = list(getattr(settings, 'ADMIN_MENU_MODEL_ORDER', []))
        if not app_order and jazzmin_order:
            app_order = [item for item in jazzmin_order if '.' not in item]
        if not model_order and jazzmin_order:
            model_order = [item for item in jazzmin_order if '.' in item]
        return app_order, model_order

    def _ordered_get_app_list(self, request, app_label=None):
        app_order, model_order = _admin_menu_orders()
        original_list = list(_original_get_app_list(self, request, app_label))
        app_list = [
            {
                **app,
                'models': list(app['models'])
            }
            for app in original_list
        ]
        model_order_map = {name: pos for pos, name in enumerate(model_order)}
        app_order_map = {name: pos for pos, name in enumerate(app_order)}
        fallback_model_offset = len(model_order_map)
        fallback_app_offset = len(app_order_map) + fallback_model_offset
        original_app_positions = {app['app_label']: idx for idx, app in enumerate(original_list)}

        for app, original in zip(app_list, original_list):
            app_label = app['app_label']
            original_model_positions = {model['object_name']: idx for idx, model in enumerate(original['models'])}
            app['models'].sort(key=lambda m: (
                model_order_map.get(f"{app_label}.{m['object_name']}", fallback_model_offset + original_model_positions[m['object_name']]),
                m['name']
            ))

        def _app_sort_key(app):
            label = app['app_label']
            base = app_order_map.get(label)
            if base is None:
                positions = [model_order_map.get(f"{label}.{m['object_name']}") for m in app['models']]
                positions = [p for p in positions if p is not None]
                if positions:
                    base = min(positions)
                else:
                    base = fallback_app_offset + original_app_positions.get(label, 0)
            return (base, app['name'])

        app_list.sort(key=_app_sort_key)
        return app_list

    _ordered_get_app_list._uses_custom_ordering = True
    admin.AdminSite.get_app_list = _ordered_get_app_list

# =============================================================================
# Inlines restantes (não movidos para arquivos específicos)
# =============================================================================

class VendaInline(admin.TabularInline):
    model = Venda
    extra = 0

class VendaItemInline(admin.TabularInline):
    model = VendaItem
    extra = 1

class ProdutoInlineFornecedor(admin.TabularInline):
    model = Produto
    fk_name = "fornecedor"
    extra = 0

class CompraInline(admin.TabularInline):
    model = Compra
    extra = 0

class ContaPagarInline(admin.TabularInline):
    model = ContaPagar
    extra = 0

class ContasReceberInlineCliente(admin.TabularInline):
    model = ContasReceber
    fk_name = "cliente"
    extra = 0

class ProdutoInlineEmpresa(admin.TabularInline):
    model = Produto
    fk_name = "empresa"
    extra = 0

class ProdutoInlineGrupoMercadoria(admin.TabularInline):
    model = Produto
    fk_name = "grupo_mercadoria"
    extra = 0

class ContaPagarInlineEmpresa(admin.TabularInline):
    model = ContaPagar
    fk_name = "empresa"
    extra = 0

class ContasReceberInlineEmpresa(admin.TabularInline):
    model = ContasReceber
    fk_name = "empresa"
    extra = 0

class CaixaInline(admin.TabularInline):
    model = Caixa
    fk_name = "empresa"
    extra = 0

class CaixaInlinePlanoConta(admin.TabularInline):
    model = Caixa
    fk_name = 'plano_conta'
    extra = 0
    fields = ('caixa_id', 'empresa', 'caixa_data_emissao', 'caixa_historico', 'caixa_valor_entrada', 'caixa_valor_saida')
    readonly_fields = ('caixa_id',)
    show_change_link = True

class CompraItemInlineCfop(admin.TabularInline):
    model = CompraItem
    fk_name = 'cfop'
    extra = 0

class VendaItemInlineCfop(admin.TabularInline):
    model = VendaItem
    fk_name = 'cfop'
    extra = 0

class RomaneioInlineFuncionario(admin.TabularInline):
    model = Romaneio
    fk_name = 'funcionario'
    extra = 0
    fields = ('romaneio_id', 'compra', 'veiculo', 'romaneio_data_emissao')
    readonly_fields = ('romaneio_id',)
    show_change_link = True

class RomaneioInlineVeiculo(admin.TabularInline):
    model = Romaneio
    fk_name = 'veiculo'
    extra = 0
    fields = ('romaneio_id', 'compra', 'funcionario', 'romaneio_data_emissao')
    readonly_fields = ('romaneio_id',)
    show_change_link = True

# =============================================================================
# Importar todos os módulos de admin separados
# =============================================================================

from .admin_empresa import *
from .admin_fornecedor import *
from .admin_cliente import *
from .admin_convenio import *
from .admin_grupo_mercadoria import *
from .admin_funcionario import *
from .admin_veiculo import *
from .admin_plano_conta import *
from .admin_cfop import *
from .admin_produto import *
from .admin_compra import *
from .admin_compra_item import *
from .admin_conta_pagar import *
from .admin_contas_receber import *
from .admin_pagamento import *
from .admin_recebimento import *
from .admin_caixa import *
from .admin_romaneio import *
from .admin_venda import *
from .admin_venda_item import *
from .admin_convenio_grupo_mercadoria import *
from .admin_cliente_convenio_grupo_mercadoria import *