# core/forms.py

from django import forms
from .models import PlanoConta, VendaItem, CompraItem, Cfop
from datetime import date


class GeracaoContasForm(forms.Form):
    plano_conta = forms.ModelChoiceField(
        queryset=PlanoConta.objects.all(),
        label="Plano de Contas",
        required=True
    )
    numero_parcelas = forms.IntegerField(
        label="Número de Parcelas",
        required=True,
        min_value=1,
        initial=1
    )
    primeiro_vencimento = forms.DateField(
        label="Data do Primeiro Vencimento",
        required=True,
        widget=forms.DateInput(attrs={'type': 'date'}),  # Adiciona um seletor de data no navegador
        initial=date.today
    )

    def __init__(self, *args, **kwargs):
        # Pega o vencimento padrão que passaremos do admin
        vencimento_default = kwargs.pop('primeiro_vencimento_default', None)
        super().__init__(*args, **kwargs)

        # Se um vencimento padrão foi fornecido, usa ele no campo
        if vencimento_default:
            self.fields['primeiro_vencimento'].initial = vencimento_default


class VendaItemForm(forms.ModelForm):
    """
    Formulário para VendaItem que filtra:
    1. CFOPs disponíveis apenas para operações de venda (5, 6, 7)
    2. Plano de Contas apenas para receitas (iniciam com 1)
    """
    
    class Meta:
        model = VendaItem
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filtra os CFOPs disponíveis para venda: 
        # 1. Códigos que iniciam com 5, 6 ou 7
        # 2. OU CFOPs marcados como tipo SAÍDA (tipo=2)
        if 'cfop' in self.fields:
            from django.db.models import Q
            self.fields['cfop'].queryset = Cfop.objects.filter(
                Q(cfop_codigo__regex=r'^[567]') | Q(cfop_tipo=2)
            ).order_by('cfop_codigo')
            
            # Adiciona um help text explicativo
            self.fields['cfop'].help_text = (
                '🔵 Azul (5, 6): Vendas | '
                '🟢 Verde (7): Exportação | '
                '📤 Tipo SAÍDA'
            )
        
        # Filtra apenas contas de receita (iniciam com 1) para Plano de Contas
        if 'plano_conta' in self.fields:
            self.fields['plano_conta'].queryset = PlanoConta.objects.filter(
                plano_conta_numero__startswith='1'
            ).order_by('plano_conta_numero')
            
            # Adiciona um help text explicativo
            self.fields['plano_conta'].help_text = (
                '💰 Apenas contas de RECEITA (iniciam com 1) são exibidas aqui'
            )


class CompraItemForm(forms.ModelForm):
    """
    Formulário para CompraItem que filtra os CFOPs disponíveis apenas para operações de compra.
    Exibe apenas CFOPs marcados como tipo Entrada.
    Nota: CompraItem não possui campo plano_conta (é herdado da Compra).
    """
    
    class Meta:
        model = CompraItem
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filtra os CFOPs disponíveis para compra: apenas CFOPs do tipo ENTRADA
        if 'cfop' in self.fields:
            self.fields['cfop'].queryset = Cfop.objects.filter(
                cfop_tipo=Cfop.TipoCfop.ENTRADA
            ).order_by('cfop_codigo')

            # Explica que apenas CFOPs de entrada aparecem
            self.fields['cfop'].help_text = (
                'Apenas CFOPs do tipo ENTRADA estao disponiveis.'
            )