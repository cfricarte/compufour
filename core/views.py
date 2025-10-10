from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .models import ClienteConvenioGrupoMercadoria, Convenio, Produto

@csrf_exempt
@require_POST
def get_preco_convenio(request):
    cliente_id = request.POST.get('cliente_id')
    produto_id = request.POST.get('produto_id')
    
    if not cliente_id or not produto_id:
        return JsonResponse({'error': 'Cliente e produto são obrigatórios'}, status=400)
    
    try:
        # Get the produto's grupo_mercadoria
        produto = Produto.objects.get(produto_id=produto_id)
        grupo_mercadoria = produto.grupo_mercadoria
        
        # Find the ClienteConvenioGrupoMercadoria for this cliente and grupo_mercadoria
        cliente_convenio = ClienteConvenioGrupoMercadoria.objects.filter(
            cliente_id=cliente_id,
            convenio_grupo_mercadoria__grupo_mercadoria=grupo_mercadoria
        ).select_related('convenio_grupo_mercadoria__convenio').first()
        
        if cliente_convenio:
            preco = cliente_convenio.convenio_grupo_mercadoria.convenio.convenio_preco
            return JsonResponse({'preco': float(preco)})
        else:
            return JsonResponse({'error': 'Convenio não encontrado para este cliente e grupo'}, status=404)
            
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_POST
def get_preco_produto(request):
    """
    Retorna o preço de venda do produto.
    """
    produto_id = request.POST.get('produto_id')
    
    if not produto_id:
        return JsonResponse({'error': 'Produto é obrigatório'}, status=400)
    
    try:
        produto = Produto.objects.get(produto_id=produto_id)
        preco = float(produto.produto_preco) if produto.produto_preco else 0.0
        
        return JsonResponse({'preco': preco})
            
    except Produto.DoesNotExist:
        return JsonResponse({'error': 'Produto não encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# Create your views here.
