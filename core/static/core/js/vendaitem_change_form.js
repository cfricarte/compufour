// Script para preenchimento automático de preço no formulário standalone de VendaItem
(function($) {
    'use strict';
    
    // Aguarda o carregamento completo do DOM
    $(document).ready(function() {
    
    function getCookie(name) {
        var cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            var cookies = document.cookie.split(';');
            for (var i = 0; i < cookies.length; i++) {
                var cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    var precoInput = $('#id_venda_item_preco');
    var clienteSelect = $('#id_cliente');
    var produtoSelect = $('#id_produto');
    
    // Flag para controlar se o preço foi alterado manualmente
    var precoManualmenteAlterado = false;
    
    // Se estamos editando um item existente, marca como manualmente alterado
    if (precoInput.val() && precoInput.val() !== '0' && precoInput.val() !== '0.00') {
        // Verifica se há um ID (edição) através do campo hidden ou URL
        var isEditing = $('input[name="venda_item_id"]').length > 0 || 
                       window.location.pathname.match(/\/\d+\/change\//);
        
        if (isEditing) {
            precoManualmenteAlterado = true;
        }
    }
    
    // Detecta mudanças manuais no campo de preço
    precoInput.on('input change', function() {
        precoManualmenteAlterado = true;
    });
    
    // Função para buscar e preencher o preço
    function buscarEPreencherPreco() {
        var clienteId = clienteSelect.val();
        var produtoId = produtoSelect.val();
        
        // Só busca se ambos estiverem selecionados
        if (!clienteId || !produtoId) {
            return;
        }
        
        // Se o preço foi alterado manualmente, não sobrescreve
        if (precoManualmenteAlterado) {
            console.log('Preço foi alterado manualmente. Não será atualizado automaticamente.');
            return;
        }
        
        // Faz a requisição AJAX para buscar o preço
        $.ajax({
            url: '/core/get-preco-convenio/',
            type: 'POST',
            data: {
                cliente_id: clienteId,
                produto_id: produtoId,
                csrfmiddlewaretoken: getCookie('csrftoken')
            },
            beforeSend: function() {
                // Indica que está carregando
                precoInput.css('background-color', '#ffffcc');
            }
        }).done(function(data) {
            if (data && data.preco !== undefined && data.preco !== null) {
                var preco = Number(data.preco);
                if (Number.isFinite(preco)) {
                    // Preenche o preço
                    precoInput.val(preco.toFixed(2));
                    precoInput.css('background-color', '#ccffcc'); // Verde claro (sucesso)
                    
                    // Reseta a flag de alteração manual
                    precoManualmenteAlterado = false;
                    
                    // Volta à cor normal após 1 segundo
                    setTimeout(function() {
                        precoInput.css('background-color', '');
                    }, 1000);
                } else {
                    console.error('Valor de preço inválido recebido:', data.preco);
                    precoInput.css('background-color', '#ffcccc'); // Vermelho claro (erro)
                    alert('Erro: valor de preço inválido recebido.');
                }
            } else {
                var message = data && data.error ? data.error : 'Preço não encontrado';
                console.warn('Preço não encontrado:', message);
                precoInput.css('background-color', '#ffcccc'); // Vermelho claro (erro)
                alert('Aviso: ' + message);
            }
        }).fail(function(xhr, status, error) {
            console.error('Erro ao buscar preço:', status, error);
            precoInput.css('background-color', '#ffcccc'); // Vermelho claro (erro)
            alert('Erro ao buscar preço: ' + error);
        }).always(function() {
            // Volta à cor normal após 2 segundos em caso de erro
            setTimeout(function() {
                if (precoInput.css('background-color') === 'rgb(255, 204, 204)') { // #ffcccc
                    precoInput.css('background-color', '');
                }
            }, 2000);
        });
    }
    
    // Escuta mudanças no select de cliente
    clienteSelect.on('change', function() {
        buscarEPreencherPreco();
    });
    
    // Escuta mudanças no select de produto
    produtoSelect.on('change', function() {
        buscarEPreencherPreco();
    });
    
    // Se ambos já estiverem selecionados ao carregar a página (ex: edição),
    // mas o preço estiver vazio ou zerado, busca automaticamente
    if (clienteSelect.val() && produtoSelect.val() && 
        (!precoInput.val() || precoInput.val() === '0' || precoInput.val() === '0.00')) {
        buscarEPreencherPreco();
    }
    
    }); // Fecha $(document).ready
    
})(django.jQuery || jQuery); // Fecha IIFE - usa django.jQuery ou jQuery global
