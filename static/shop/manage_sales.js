(function () {
    const createSaleUrl = document.body.dataset.createSaleUrl;
    const checkoutStatusTemplate = document.body.dataset.checkoutStatusTemplate;
    const printOrderTemplate = document.body.dataset.printOrderTemplate;

    const saleForm = document.getElementById('sale-form');
    const saleSummaryCard = document.getElementById('sale-summary-card');
    const cartItemsEl = document.getElementById('sale-cart-items');
    const cartTotalEl = document.getElementById('sale-cart-total');
    const saleCartCount = document.getElementById('sale-cart-count');
    const openSaleCartBtn = document.getElementById('open-sale-cart');
    const closeSaleCartBtn = document.getElementById('close-sale-cart');
    const saleCartOverlay = document.getElementById('sale-cart-overlay');

    const paymentChoiceOverlay = document.getElementById('payment-choice-overlay');
    const paymentChoiceModal = document.getElementById('payment-choice-modal');
    const closePaymentChoiceBtn = document.getElementById('close-payment-choice-modal');
    const paymentChoiceButtons = document.querySelectorAll('[data-payment-choice]');

    const modalOverlay = document.getElementById('sale-modal-overlay');
    const modal = document.getElementById('sale-modal');
    const modalTitle = document.getElementById('sale-modal-title');
    const modalMessage = document.getElementById('sale-modal-message');
    const modalStatus = document.getElementById('sale-modal-status');
    const modalQr = document.getElementById('sale-modal-qr');
    const copyPixBtn = document.getElementById('sale-copy-pix');
    const printTicketBtn = document.getElementById('sale-print-ticket-btn');
    const closeModalBtn = document.getElementById('close-sale-modal');

    let saleCart = [];
    let currentPixCode = '';
    let currentOrderId = null;
    let statusPoller = null;
    let pendingSale = null;
    let creatingSale = false;
    let currentBluetoothTicketText = '';

    function csrfToken() {
        const input = document.querySelector('input[name=csrfmiddlewaretoken]');
        return input ? input.value : '';
    }

    function isAndroidDevice() {
        return /android/i.test(navigator.userAgent || '');
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

    function buildBluetoothTicketText(orderId, customerName, items) {
        const lines = [
            'VIA COZINHA',
            `Pedido #${orderId}`,
            `Cliente: ${customerName || '-'}`,
            '',
            'Itens:',
        ];
        (items || []).forEach((item) => {
            lines.push(`- ${item.quantity}x ${item.name}`);
            lines.push('');
        });
        return lines.join('\n');
    }

    function openRawBtIntent(ticketText) {
        if (!ticketText) {
            return false;
        }
        const payload = encodeURIComponent(ticketText.endsWith('\n') ? ticketText : `${ticketText}\n`);
        const intentUrl = `intent:${payload}#Intent;scheme=rawbt;package=ru.a402d.rawbtprinter;end;`;
        try {
            window.location.href = intentUrl;
            return true;
        } catch (error) {
            // fallback below
        }
        try {
            window.location.href = `rawbt:${payload}`;
            return true;
        } catch (error) {
            return false;
        }
    }

    async function shareBluetoothTicketFallback() {
        if (!currentBluetoothTicketText) {
            return;
        }
        if (navigator.share) {
            try {
                await navigator.share({
                    title: `Pedido #${currentOrderId || ''}`,
                    text: currentBluetoothTicketText,
                });
                return;
            } catch (error) {
                // tenta clipboard abaixo
            }
        }
        if (navigator.clipboard && navigator.clipboard.writeText) {
            try {
                await navigator.clipboard.writeText(currentBluetoothTicketText);
                window.alert('Nao abriu o RawBT automaticamente. Cupom copiado para colar no app.');
            } catch (error) {
                window.alert('Nao foi possivel abrir automaticamente o app da impressora.');
            }
        }
    }

    function openPaymentChoiceModal() {
        closeSaleCart();
        paymentChoiceOverlay.hidden = false;
        paymentChoiceModal.hidden = false;
    }

    function closePaymentChoiceModal() {
        paymentChoiceOverlay.hidden = true;
        paymentChoiceModal.hidden = true;
    }

    function openModal() {
        closeSaleCart();
        modalOverlay.hidden = false;
        modal.hidden = false;
    }

    function closeModal() {
        modalOverlay.hidden = true;
        modal.hidden = true;
        stopPixStatusPolling();
    }

    function buildPrintOrderUrl(orderId) {
        if (!orderId || !printOrderTemplate) {
            return '';
        }
        return printOrderTemplate.replace('/0/', `/${orderId}/`);
    }

    function openPrintTicket() {
        const printUrl = buildPrintOrderUrl(currentOrderId);
        if (!printUrl) {
            showError('Nao foi possivel gerar a URL de impressao.');
            return;
        }
        const popup = window.open(printUrl, '_blank', 'noopener,noreferrer');
        if (!popup) {
            window.location.href = printUrl;
        }
    }

    function renderSaleCart() {
        const totalItems = saleCart.reduce((acc, item) => acc + Number(item.quantity || 0), 0);
        if (saleCartCount) {
            saleCartCount.textContent = String(totalItems);
        }
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

    function showVariationError(card) {
        const errorEl = card.querySelector('.variation-error');
        const select = card.querySelector('.variant-select');
        if (errorEl) {
            errorEl.hidden = false;
        }
        if (select) {
            select.classList.add('has-error');
            select.focus();
        }
    }

    function clearVariationError(card) {
        const errorEl = card.querySelector('.variation-error');
        const select = card.querySelector('.variant-select');
        if (errorEl) {
            errorEl.hidden = true;
        }
        if (select) {
            select.classList.remove('has-error');
        }
    }

    function addItemFromCard(card) {
        const productId = Number(card.dataset.productId);
        const productName = card.dataset.productName;
        const hasVariants = card.dataset.hasVariants === 'true';
        const qtyInput = card.querySelector('.qty-input');
        const select = card.querySelector('.variant-select');
        const quantity = Math.max(1, Number(qtyInput.value || '1'));

        if (hasVariants && (!select || !select.value)) {
            showVariationError(card);
            return;
        }

        let variantId = null;
        let variantName = '';
        let price = parseMoney(card.querySelector('.product-price').dataset.basePrice || '0');

        if (select && select.value) {
            variantId = Number(select.value);
            const option = select.options[select.selectedIndex];
            variantName = option.dataset.name || '';
            price = parseMoney(option.dataset.price || price);
        }
        clearVariationError(card);

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
        openSaleCart();
    }

    function isCompactLayout() {
        return window.matchMedia('(max-width: 900px)').matches;
    }

    function openSaleCart() {
        if (!isCompactLayout()) {
            return;
        }
        saleSummaryCard.classList.add('open');
        saleCartOverlay.classList.add('open');
        document.body.classList.add('sales-cart-open');
    }

    function closeSaleCart() {
        saleSummaryCard.classList.remove('open');
        saleCartOverlay.classList.remove('open');
        document.body.classList.remove('sales-cart-open');
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
                    clearVariationError(card);
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

    function resetProductSelectionInputs() {
        document.querySelectorAll('.sales-product').forEach((card) => {
            const qtyInput = card.querySelector('.qty-input');
            if (qtyInput) {
                qtyInput.value = '1';
            }
            const select = card.querySelector('.variant-select');
            if (select && !select.disabled) {
                select.value = '';
                clearVariationError(card);
                const priceEl = card.querySelector('.product-price');
                if (priceEl) {
                    priceEl.textContent = `R$ ${formatMoney(priceEl.dataset.basePrice || 0)}`;
                }
            }
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
                stopPixStatusPolling();
            }
        } catch (error) {
            stopPixStatusPolling();
        }
    }

    function collectSaleData() {
        const formData = new FormData(saleForm);
        const customerName = String(formData.get('customer_name') || '').trim();
        const whatsapp = String(formData.get('whatsapp') || '').trim();
        return { customerName, whatsapp };
    }

    async function createSaleWithPayment(paymentMethod) {
        if (creatingSale || !pendingSale) {
            return;
        }

        creatingSale = true;
        closePaymentChoiceModal();

        try {
            const saleItemsSnapshot = saleCart.map((item) => ({ ...item }));
            const payload = await post(createSaleUrl, {
                customer_name: pendingSale.customerName,
                whatsapp: pendingSale.whatsapp,
                payment_method: paymentMethod,
                mark_paid_now: 'false',
                items_json: JSON.stringify(
                    saleCart.map((item) => ({
                        product_id: item.product_id,
                        variant_id: item.variant_id,
                        quantity: item.quantity,
                    }))
                ),
            });

            currentOrderId = payload.order_id;
            currentPixCode = payload.pix_code || '';
            currentBluetoothTicketText = buildBluetoothTicketText(
                payload.order_id,
                pendingSale.customerName,
                saleItemsSnapshot
            );
            printTicketBtn.hidden = isAndroidDevice() || !currentOrderId;

            if (paymentMethod === 'pix' && payload.qr_code_base64) {
                modalTitle.textContent = 'Pagamento Pix';
                modalMessage.textContent = payload.message || 'Venda criada. Gere o Pix.';
                modalStatus.textContent = payload.status_label || 'Aguardando pagamento';
                modalQr.src = `data:image/png;base64,${payload.qr_code_base64}`;
                modalQr.hidden = false;
                copyPixBtn.hidden = false;
                stopPixStatusPolling();
                statusPoller = window.setInterval(pollPixStatus, 5000);
                pollPixStatus();
            } else {
                modalTitle.textContent = 'Venda criada';
                modalMessage.textContent = payload.message || `Venda #${payload.order_id} criada.`;
                modalStatus.textContent = payload.status_label || 'Aguardando pagamento';
                modalQr.removeAttribute('src');
                modalQr.hidden = true;
                copyPixBtn.hidden = true;
                stopPixStatusPolling();
            }

            saleCart = [];
            pendingSale = null;
            saleForm.reset();
            resetProductSelectionInputs();
            renderSaleCart();
            openModal();
            if (isAndroidDevice()) {
                const opened = openRawBtIntent(currentBluetoothTicketText);
                if (!opened) {
                    shareBluetoothTicketFallback();
                }
            }
        } catch (error) {
            showError(error.message);
        } finally {
            creatingSale = false;
        }
    }

    function onSubmitSale(event) {
        event.preventDefault();
        closeSaleCart();

        if (!saleCart.length) {
            showError('Adicione itens antes de finalizar a venda.');
            return;
        }

        const data = collectSaleData();
        if (!data.customerName || !data.whatsapp) {
            showError('Informe nome completo e WhatsApp antes de continuar.');
            return;
        }

        pendingSale = data;
        openPaymentChoiceModal();
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

    saleForm.addEventListener('submit', onSubmitSale);
    paymentChoiceButtons.forEach((button) => {
        button.addEventListener('click', () => createSaleWithPayment(button.dataset.paymentChoice));
    });
    closePaymentChoiceBtn.addEventListener('click', closePaymentChoiceModal);
    paymentChoiceOverlay.addEventListener('click', closePaymentChoiceModal);

    copyPixBtn.addEventListener('click', onCopyPix);
    printTicketBtn.addEventListener('click', openPrintTicket);
    if (isAndroidDevice()) {
        printTicketBtn.hidden = true;
    }
    closeModalBtn.addEventListener('click', closeModal);
    modalOverlay.addEventListener('click', closeModal);
    openSaleCartBtn.addEventListener('click', openSaleCart);
    closeSaleCartBtn.addEventListener('click', closeSaleCart);
    saleCartOverlay.addEventListener('click', closeSaleCart);
    window.addEventListener('resize', () => {
        if (!isCompactLayout()) {
            closeSaleCart();
        }
    });

    bindProductCards();
    bindCartActions();
    renderSaleCart();
})();
