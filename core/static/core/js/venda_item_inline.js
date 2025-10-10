django.jQuery(document).ready(function($) {
    console.log('=== JavaScript venda_item_inline.js carregado ===');
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

    function parseDecimal(value) {
        if (value === null || value === undefined) {
            return null;
        }
        var stringValue = value.toString().trim();
        if (!stringValue) {
            return null;
        }
        if (stringValue.indexOf(',') !== -1) {
            stringValue = stringValue.replace(/\./g, '').replace(',', '.');
        }
        var numberValue = parseFloat(stringValue);
        return Number.isFinite(numberValue) ? numberValue : null;
    }

    function updateRowTotal(row) {
        var precoInput = row.find('input[name$="-venda_item_preco"]');
        var quantidadeInput = row.find('input[name$="-venda_item_qtd"]');
        var totalInput = row.find('input[name$="-venda_item_total"]');

        if (!totalInput.length) {
            return;
        }

        var preco = parseDecimal(precoInput.val());
        var quantidade = parseDecimal(quantidadeInput.val());

        if (preco === null || quantidade === null) {
            totalInput.val('R$ 0,00');
            return;
        }

        var total = preco * quantidade;
        var totalFormatado = 'R$ ' + total.toFixed(2).replace('.', ',').replace(/\B(?=(\d{3})+(?!\d))/g, '.');
        totalInput.val(totalFormatado);
    }

    function markAutoPrice(input, isAuto) {
        input.attr('data-auto-price', isAuto ? 'true' : 'false');
    }

    function setPrecoValue(input, value) {
        markAutoPrice(input, true);
        input.val(value);
        input.trigger('change');
        updateRowTotal(input.closest('tr'));
    }

    function initializeRow(row) {
        var precoInput = row.find('input[name$="-venda_item_preco"]');
        if (!precoInput.length) {
            return;
        }

        var instanceId = row.find('input[name$="-id"]').val();
        if (instanceId) {
            markAutoPrice(precoInput, false);
        } else if (precoInput.val()) {
            markAutoPrice(precoInput, false);
        } else {
            markAutoPrice(precoInput, true);
        }

        updateRowTotal(row);
    }

    $(document).on('input', 'input[name$="-venda_item_preco"]', function() {
        markAutoPrice($(this), false);
        updateRowTotal($(this).closest('tr'));
    });

    $(document).on('change', 'input[name$="-venda_item_preco"]', function() {
        updateRowTotal($(this).closest('tr'));
    });

    $(document).on('input change', 'input[name$="-venda_item_qtd"]', function() {
        updateRowTotal($(this).closest('tr'));
    });

    $(document).on('change', '.field-produto select', function() {
        console.log('===== EVENTO PRODUTO SELECIONADO DISPARADO =====');
        var row = $(this).closest('tr');
        var produtoSelect = row.find('.field-produto select');
        var clienteSelect = row.find('.field-cliente select');
        var precoInput = row.find('input[name$="-venda_item_preco"]');

        if (!precoInput.length) {
            console.warn('Nao foi possivel localizar o campo de preco na linha selecionada.');
            return;
        }

        var produtoId = produtoSelect.val();
        console.log('Produto ID:', produtoId);

        if (!produtoId) {
            setPrecoValue(precoInput, '');
            return;
        }

        var instanceId = row.find('input[name$="-id"]').val();
        if (instanceId) {
            markAutoPrice(precoInput, false);
            updateRowTotal(row);
            return;
        }

        var precoValor = precoInput.val();
        var autoFlag = precoInput.attr('data-auto-price');

        if (autoFlag === 'false' && precoValor) {
            updateRowTotal(row);
            return;
        }

        var clienteId = clienteSelect.val();

        // Se tiver cliente, busca preço por convênio
        if (clienteId) {
            $.ajax({
                url: '/core/get-preco-convenio/',
                type: 'POST',
                data: {
                    cliente_id: clienteId,
                    produto_id: produtoId,
                    csrfmiddlewaretoken: getCookie('csrftoken')
                }
            }).done(function(data) {
                if (data && data.preco !== undefined && data.preco !== null) {
                    var preco = Number(data.preco);
                    if (Number.isFinite(preco)) {
                        setPrecoValue(precoInput, preco.toFixed(2));
                    } else {
                        alert('Erro: valor de preco invalido recebido.');
                        setPrecoValue(precoInput, '');
                    }
                } else {
                    var message = data && data.error ? data.error : 'Preco nao encontrado';
                    alert('Erro: ' + message);
                    setPrecoValue(precoInput, '');
                }
            }).fail(function(xhr, status, error) {
                console.error('Erro ao buscar preco', status, error);
                alert('Erro ao buscar preco: ' + error);
                setPrecoValue(precoInput, '');
            });
        } else {
            // Se não tiver cliente, busca o preço do produto
            $.ajax({
                url: '/core/get-preco-produto/',
                type: 'POST',
                data: {
                    produto_id: produtoId,
                    csrfmiddlewaretoken: getCookie('csrftoken')
                }
            }).done(function(data) {
                console.log('Preço de venda obtido:', data);
                if (data && data.preco !== undefined && data.preco !== null) {
                    var preco = Number(data.preco);
                    if (Number.isFinite(preco)) {
                        setPrecoValue(precoInput, preco.toFixed(2));
                    } else {
                        setPrecoValue(precoInput, '');
                    }
                } else {
                    setPrecoValue(precoInput, '');
                }
            }).fail(function(xhr, status, error) {
                console.error('Erro ao buscar preco do produto', status, error);
                setPrecoValue(precoInput, '');
            });
        }
    });

    $(document).on('change', '.field-cliente select', function() {
        var row = $(this).closest('tr');
        var produtoSelect = row.find('.field-produto select');
        var clienteSelect = row.find('.field-cliente select');
        var precoInput = row.find('input[name$="-venda_item_preco"]');

        if (!precoInput.length) {
            return;
        }

        var clienteId = clienteSelect.val();
        var produtoId = produtoSelect.val();

        if (!clienteId || !produtoId) {
            return;
        }

        var instanceId = row.find('input[name$="-id"]').val();
        if (instanceId) {
            markAutoPrice(precoInput, false);
            updateRowTotal(row);
            return;
        }

        var precoValor = precoInput.val();
        var autoFlag = precoInput.attr('data-auto-price');

        if (autoFlag === 'false' && precoValor) {
            updateRowTotal(row);
            return;
        }

        // Busca preço por convênio
        $.ajax({
            url: '/core/get-preco-convenio/',
            type: 'POST',
            data: {
                cliente_id: clienteId,
                produto_id: produtoId,
                csrfmiddlewaretoken: getCookie('csrftoken')
            }
        }).done(function(data) {
            if (data && data.preco !== undefined && data.preco !== null) {
                var preco = Number(data.preco);
                if (Number.isFinite(preco)) {
                    setPrecoValue(precoInput, preco.toFixed(2));
                }
            }
        }).fail(function(xhr, status, error) {
            console.error('Erro ao buscar preco', status, error);
        });
    });

    $(document).on('formset:added', function(event, row) {
        initializeRow($(row));
    });

    $('.inline-group tr.form-row').each(function() {
        initializeRow($(this));
    });
});
