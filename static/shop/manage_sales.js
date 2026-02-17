(function () {
    const createSaleUrl = document.body.dataset.createSaleUrl;
    const markPaidTemplate = document.body.dataset.markPaidTemplate;
    const checkoutStatusTemplate = document.body.dataset.checkoutStatusTemplate;

    const saleForm = document.getElementById('sale-form');
    const paymentMethodSelect = document.getElementById('sale-payment-method');
    const markPaidWrapper = document.getElementById('mark-paid-wrapper');
    const cartItemsEl = document.getElementById('sale-cart-items');
    const cartTotalEl = document.getElementById('sale-cart-total');

    const modalOverlay = document.getElementById('sale-modal-overlay');
    const modal = document.getElementById('sale-modal');
    const modalTitle = document.getElementById('sale-modal-title');
    const modalMessage = document.getElementById('sale-modal-message');
    const modalStatus = document.getElementById('sale-modal-status');
    const modalQr = document.getElementById('sale-modal-qr');
    const copyPixBtn = document.getElementById('sale-copy-pix');
    const markPaidBtn = document.getElementById('sale-mark-paid-btn');
    const closeModalBtn = document.getElementById('close-sale-modal');

    let saleCart = [];
    let currentPixCode = '';
    let currentOrderId = null;
    let statusPoller = null;

    function csrfToken() {
        const input = document.querySelector('input[name=csrfmiddlewaretoken]');
        return input ? input.value : '';
    }

    function showError(message) {
        window.alert(message);
    }

    async function parseResponse(response) {
        let payload = {};
        try {
            payload = await response.json();
        } catch (error) {
            payload = {};
        }
        if (!response.ok) {
            throw new Error(payload.error || 'Falha na solicitacao.');
        }
        return payload;
    }

    async function post(url, body) {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken(),
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams(body),
        });
        return parseResponse(response);
    }

    function parseMoney(value) {
        if (typeof value === 'number') {
            return Number.isFinite(value) ? value : 0;
        }
        let normalized = String(value || '').trim().replace(/\s+/g, '');
        if (normalized.includes(',')) {
            normalized = normalized.replace(/\./g, '').replace(',', '.');
        }
        const parsed = Number(normalized);
        return Number.isFinite(parsed) ? parsed : 0;
    }

    function formatMoney(value) {
        return parseMoney(value).toFixed(2);
    }

    function openModal() {
        modalOverlay.hidden = false;
        modal.hidden = false;
    }

    function closeModal() {
        modalOverlay.hidden = true;
        modal.hidden = true;
        stopPixStatusPolling();
    }

    function renderSaleCart() {
        if (!saleCart.length) {
            cartItemsEl.innerHTML = '<p>Nenhum item no carrinho.</p>';
            cartTotalEl.textContent = 'R$ 0.00';
            return;
        }

        let total = 0;
        cartItemsEl.innerHTML = saleCart
            .map((item, index) => {
                const subtotal = parseMoney(item.price) * Number(item.quantity);
                total += subtotal;
                return `
                    <article class="cart-item">
                        <div>
                            <h4>${item.name}</h4>
                            <div class="cart-meta">${item.quantity} x R$ ${formatMoney(item.price)}</div>
                            <div class="cart-meta">Subtotal: R$ ${formatMoney(subtotal)}</div>
                            <div class="cart-actions">
                                <button data-cart-action="dec" data-index="${index}">-</button>
                                <button data-cart-action="inc" data-index="${index}">+</button>
                                <button class="remove" data-cart-action="remove" data-index="${index}">remover</button>
                            </div>
                        </div>
                    </article>
                `;
            })
            .join('');
        cartTotalEl.textContent = `R$ ${formatMoney(total)}`;
    }

    function refreshPaymentMethodUI() {
        const method = paymentMethodSelect.value;
        markPaidWrapper.style.display = method === 'pix' ? 'none' : 'flex';
    }

    function addItemFromCard(card) {
        const productId = Number(card.dataset.productId);
        const productName = card.dataset.productName;
        const qtyInput = card.querySelector('.qty-input');
        const select = card.querySelector('.variant-select');
        const quantity = Math.max(1, Number(qtyInput.value || '1'));

        let variantId = null;
        let variantName = '';
        let price = parseMoney(card.querySelector('.product-price').dataset.basePrice || '0');

        if (select && select.value) {
            variantId = Number(select.value);
            const option = select.options[select.selectedIndex];
            variantName = option.dataset.name || '';
            price = parseMoney(option.dataset.price || price);
        }

        const itemName = variantName ? `${productName} - ${variantName}` : productName;

        const existing = saleCart.find((item) => item.product_id === productId && item.variant_id === variantId);
        if (existing) {
            existing.quantity += quantity;
        } else {
            saleCart.push({
                product_id: productId,
                variant_id: variantId,
                name: itemName,
                price,
                quantity,
            });
        }
        renderSaleCart();
    }

    function bindProductCards() {
        document.querySelectorAll('.sales-product').forEach((card) => {
            const qtyInput = card.querySelector('.qty-input');
            card.querySelectorAll('.qty-btn').forEach((button) => {
                button.addEventListener('click', () => {
                    const current = Number(qtyInput.value || '1');
                    const next = button.dataset.action === 'plus' ? current + 1 : current - 1;
                    qtyInput.value = String(Math.max(1, next));
                });
            });

            const select = card.querySelector('.variant-select');
            const priceEl = card.querySelector('.product-price');
            if (select) {
                const updatePrice = () => {
                    if (!select.value) {
                        priceEl.textContent = `R$ ${formatMoney(priceEl.dataset.basePrice || 0)}`;
                        return;
                    }
                    const selected = select.options[select.selectedIndex];
                    priceEl.textContent = `R$ ${formatMoney(selected.dataset.price || priceEl.dataset.basePrice || 0)}`;
                };
                select.addEventListener('change', updatePrice);
                updatePrice();
            }

            card.querySelector('.add-sale-item-btn').addEventListener('click', () => addItemFromCard(card));
        });
    }

    function bindCartActions() {
        cartItemsEl.addEventListener('click', (event) => {
            const button = event.target.closest('[data-cart-action]');
            if (!button) {
                return;
            }
            const index = Number(button.dataset.index);
            const item = saleCart[index];
            if (!item) {
                return;
            }
            const action = button.dataset.cartAction;
            if (action === 'inc') {
                item.quantity += 1;
            } else if (action === 'dec') {
                item.quantity -= 1;
                if (item.quantity <= 0) {
                    saleCart.splice(index, 1);
                }
            } else if (action === 'remove') {
                saleCart.splice(index, 1);
            }
            renderSaleCart();
        });
    }

    function stopPixStatusPolling() {
        if (statusPoller) {
            window.clearInterval(statusPoller);
            statusPoller = null;
        }
    }

    async function pollPixStatus() {
        if (!currentOrderId) {
            return;
        }
        try {
            const response = await fetch(checkoutStatusTemplate.replace('/0/', `/${currentOrderId}/`), {
                method: 'GET',
            });
            const payload = await parseResponse(response);
            modalStatus.textContent = payload.status_label || 'Aguardando pagamento';
            if (payload.is_paid) {
                modalMessage.textContent = `Pagamento aprovado para a venda #${payload.order_id}.`;
                markPaidBtn.hidden = true;
                stopPixStatusPolling();
            }
        } catch (error) {
            stopPixStatusPolling();
        }
    }

    async function onSubmitSale(event) {
        event.preventDefault();
        if (!saleCart.length) {
            showError('Adicione itens antes de finalizar a venda.');
            return;
        }

        const formData = new FormData(saleForm);
        try {
            const payload = await post(createSaleUrl, {
                customer_name: formData.get('customer_name') || '',
                whatsapp: formData.get('whatsapp') || '',
                payment_method: formData.get('payment_method') || '',
                mark_paid_now: formData.get('mark_paid_now') ? 'true' : 'false',
                items_json: JSON.stringify(
                    saleCart.map((item) => ({
                        product_id: item.product_id,
                        variant_id: item.variant_id,
                        quantity: item.quantity,
                    }))
                ),
            });

            currentOrderId = payload.order_id;
            modalTitle.textContent = 'Venda criada';
            modalMessage.textContent = payload.message || 'Venda finalizada.';
            modalStatus.textContent = payload.status_label || '';

            currentPixCode = payload.pix_code || '';
            if (payload.qr_code_base64) {
                modalQr.src = `data:image/png;base64,${payload.qr_code_base64}`;
                modalQr.hidden = false;
                copyPixBtn.hidden = false;
                markPaidBtn.hidden = true;
                stopPixStatusPolling();
                statusPoller = window.setInterval(pollPixStatus, 5000);
                pollPixStatus();
            } else {
                modalQr.removeAttribute('src');
                modalQr.hidden = true;
                copyPixBtn.hidden = true;
                markPaidBtn.hidden = payload.is_paid;
            }

            saleCart = [];
            saleForm.reset();
            refreshPaymentMethodUI();
            renderSaleCart();
            openModal();
        } catch (error) {
            showError(error.message);
        }
    }

    async function onMarkPaid() {
        if (!currentOrderId) {
            return;
        }
        try {
            const payload = await post(markPaidTemplate.replace('/0/', `/${currentOrderId}/`), {});
            modalStatus.textContent = 'Pagamento aprovado';
            modalMessage.textContent = payload.message || `Venda #${currentOrderId} marcada como paga.`;
            markPaidBtn.hidden = true;
        } catch (error) {
            showError(error.message);
        }
    }

    async function onCopyPix() {
        if (!currentPixCode) {
            showError('Codigo Pix indisponivel.');
            return;
        }
        try {
            await navigator.clipboard.writeText(currentPixCode);
            window.alert('Codigo Pix copiado.');
        } catch (error) {
            showError('Nao foi possivel copiar o codigo Pix.');
        }
    }

    paymentMethodSelect.addEventListener('change', refreshPaymentMethodUI);
    saleForm.addEventListener('submit', onSubmitSale);
    copyPixBtn.addEventListener('click', onCopyPix);
    markPaidBtn.addEventListener('click', onMarkPaid);
    closeModalBtn.addEventListener('click', closeModal);
    modalOverlay.addEventListener('click', closeModal);

    bindProductCards();
    bindCartActions();
    refreshPaymentMethodUI();
    renderSaleCart();
})();
