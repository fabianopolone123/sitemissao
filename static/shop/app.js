(function () {
    const sidebar = document.getElementById('cart-sidebar');
    const cartOverlay = document.getElementById('cart-overlay');
    const openCartButtons = document.querySelectorAll('[data-open-cart]');
    const closeCartButton = document.getElementById('close-cart');
    const cartCountBadges = document.querySelectorAll('.cart-count-badge');
    const cartTotal = document.getElementById('cart-total');
    const cartItems = document.getElementById('cart-items');
    const checkoutForm = document.getElementById('checkout-form');

    const loginOverlay = document.getElementById('login-modal-overlay');
    const loginModal = document.getElementById('login-modal');
    const loginForm = document.getElementById('login-form');
    const openLoginButtons = document.querySelectorAll('#open-login-mobile, #open-login-desktop');
    const closeLoginModalButton = document.getElementById('close-login-modal');

    const paymentOverlay = document.getElementById('payment-modal-overlay');
    const paymentModal = document.getElementById('payment-modal');
    const closePaymentModalButton = document.getElementById('close-payment-modal');
    const copyPixCodeButton = document.getElementById('copy-pix-code');
    let printOrderTicketButton = document.getElementById('print-order-ticket');
    const paymentMessage = document.getElementById('payment-message');
    const paymentStatusLabel = document.getElementById('payment-status-label');
    const paymentQr = document.getElementById('payment-qr');

    const successOverlay = document.getElementById('success-modal-overlay');
    const successModal = document.getElementById('success-modal');
    const closeSuccessModalButton = document.getElementById('close-success-modal');
    const successOkButton = document.getElementById('success-ok-btn');
    const successOrderDetails = document.getElementById('success-order-details');

    const initialCart = JSON.parse(document.getElementById('initial-cart').textContent);
    const cartUpdateTemplate = document.body.dataset.cartUpdateTemplate;
    const checkoutFinalizeUrl = document.body.dataset.checkoutFinalizeUrl;
    const checkoutStatusTemplate = document.body.dataset.checkoutStatusTemplate;
    const authLoginUrl = document.body.dataset.authLoginUrl;

    let currentPixCode = '';
    let currentOrderId = null;
    let paymentPollInterval = null;
    let currentOrderSummary = null;
    let currentPrintUrl = '';
    let paymentApprovedShown = false;

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
            throw new Error(payload.error || 'Falha ao processar a solicitação.');
        }
        return payload;
    }

    async function post(url, body) {
        const data = new URLSearchParams(body);
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken(),
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: data,
        });
        return parseResponse(response);
    }

    function openCart() {
        sidebar.classList.add('open');
        cartOverlay.classList.add('open');
        sidebar.setAttribute('aria-hidden', 'false');
    }

    function closeCart() {
        sidebar.classList.remove('open');
        cartOverlay.classList.remove('open');
        sidebar.setAttribute('aria-hidden', 'true');
    }

    function openLoginModal() {
        closeCart();
        loginOverlay.hidden = false;
        loginModal.hidden = false;
    }

    function closeLoginModal() {
        loginOverlay.hidden = true;
        loginModal.hidden = true;
    }

    function openPaymentModal() {
        closeCart();
        if (!printOrderTicketButton) {
            const dynamicButton = document.createElement('button');
            dynamicButton.id = 'print-order-ticket';
            dynamicButton.type = 'button';
            dynamicButton.className = 'add-btn';
            dynamicButton.hidden = true;
            dynamicButton.textContent = 'Imprimir pedido';
            paymentModal.appendChild(dynamicButton);
            dynamicButton.addEventListener('click', printOrderTicket);
            printOrderTicketButton = dynamicButton;
        }
        paymentOverlay.hidden = false;
        paymentModal.hidden = false;
    }

    function closePaymentModal() {
        paymentOverlay.hidden = true;
        paymentModal.hidden = true;
        stopPaymentStatusPolling();
    }

    function openSuccessModal() {
        successOverlay.hidden = false;
        successModal.hidden = false;
    }

    function closeSuccessModal() {
        successOverlay.hidden = true;
        successModal.hidden = true;
    }

    function stopPaymentStatusPolling() {
        if (paymentPollInterval) {
            window.clearInterval(paymentPollInterval);
            paymentPollInterval = null;
        }
    }

    async function fetchPaymentStatus(orderId) {
        const statusUrl = checkoutStatusTemplate.replace('/0/', `/${orderId}/`);
        const response = await fetch(statusUrl, { method: 'GET' });
        return parseResponse(response);
    }

    async function refreshPaymentStatus() {
        if (!currentOrderId) {
            return;
        }

        try {
            const payload = await fetchPaymentStatus(currentOrderId);
            paymentStatusLabel.textContent = payload.status_label || 'Aguardando pagamento';
            if (payload.is_paid) {
                paymentMessage.textContent = `Pagamento aprovado. Pedido #${payload.order_id}.`;
                stopPaymentStatusPolling();
                if (!paymentApprovedShown) {
                    paymentApprovedShown = true;
                    const summary = currentOrderSummary || {};
                    const customerName = summary.customer_name || 'Cliente';
                    const whatsapp = summary.whatsapp || '-';
                    const total = summary.total || '0.00';
                    successOrderDetails.textContent = `Pedido #${payload.order_id} | ${customerName} | WhatsApp: ${whatsapp} | Total: R$ ${total}`;
                    openSuccessModal();
                }
            }
        } catch (error) {
            stopPaymentStatusPolling();
            showError(error.message);
        }
    }

    function startPaymentStatusPolling(orderId) {
        currentOrderId = orderId;
        paymentApprovedShown = false;
        stopPaymentStatusPolling();
        refreshPaymentStatus();
        paymentPollInterval = window.setInterval(refreshPaymentStatus, 5000);
    }

    function renderCart(cart) {
        cartCountBadges.forEach((badge) => {
            badge.textContent = cart.count;
        });
        cartTotal.textContent = `R$ ${cart.total}`;

        if (!cart.items.length) {
            cartItems.innerHTML = '<p>Seu carrinho está vazio.</p>';
            return;
        }

        cartItems.innerHTML = cart.items
            .map(
                (item) => `
                    <article class="cart-item" data-id="${item.id}" data-variant-id="${item.variant_id || ''}">
                        <img src="${item.image_url}" alt="${item.name}">
                        <div>
                            <h4>${item.name}</h4>
                            <div class="cart-meta">${item.quantity} x R$ ${item.price}</div>
                            <div class="cart-meta">Subtotal: R$ ${item.subtotal}</div>
                            <div class="cart-actions">
                                <button data-action="dec">-</button>
                                <button data-action="inc">+</button>
                                <button class="remove" data-action="remove">remover</button>
                            </div>
                        </div>
                    </article>
                `
            )
            .join('');

        bindCartActions();
    }

    function bindCardQuantityControls() {
        document.querySelectorAll('.add-form').forEach((form) => {
            const input = form.querySelector('.qty-input');
            form.querySelectorAll('.qty-btn').forEach((button) => {
                button.addEventListener('click', () => {
                    const current = parseInt(input.value || '1', 10);
                    const next = button.dataset.action === 'plus' ? current + 1 : current - 1;
                    input.value = String(Math.max(1, next));
                });
            });
        });
    }

    function bindVariantSelectors() {
        document.querySelectorAll('.product-card').forEach((card) => {
            const select = card.querySelector('.variant-select');
            const priceElement = card.querySelector('.product-price');
            if (!select || !priceElement) {
                return;
            }

            const updatePrice = () => {
                const selectedOption = select.options[select.selectedIndex];
                const selectedPrice = select.value && selectedOption ? selectedOption.dataset.price : null;
                const basePrice = priceElement.dataset.basePrice || '0.00';
                priceElement.textContent = `R$ ${selectedPrice || basePrice}`;
            };

            select.addEventListener('change', updatePrice);
            updatePrice();
        });
    }

    function bindAddToCartForms() {
        document.querySelectorAll('.add-form').forEach((form) => {
            form.addEventListener('submit', async (event) => {
                event.preventDefault();
                try {
                    const quantity = form.querySelector('.qty-input').value;
                    const variantSelect = form.querySelector('.variant-select');
                    const variantId = variantSelect ? variantSelect.value : '';
                    const cart = await post(form.dataset.url, { quantity, variant_id: variantId });
                    renderCart(cart);
                    openCart();
                } catch (error) {
                    showError(error.message);
                }
            });
        });
    }

    function bindCartActions() {
        cartItems.querySelectorAll('.cart-item').forEach((row) => {
            const id = row.dataset.id;
            const variantId = row.dataset.variantId || '';
            const updateUrl = cartUpdateTemplate.replace('/0/', `/${id}/`);
            row.querySelectorAll('button').forEach((button) => {
                button.addEventListener('click', async () => {
                    try {
                        const action = button.dataset.action;
                        const cart = await post(updateUrl, {
                            action: action === 'remove' ? 'set' : action,
                            quantity: action === 'remove' ? '0' : '1',
                            variant_id: variantId,
                        });
                        renderCart(cart);
                    } catch (error) {
                        showError(error.message);
                    }
                });
            });
        });
    }

    function bindCheckoutForm() {
        checkoutForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            const formData = new FormData(checkoutForm);

            try {
                const payload = await post(checkoutFinalizeUrl, {
                    first_name: formData.get('first_name') || '',
                    last_name: formData.get('last_name') || '',
                    whatsapp: formData.get('whatsapp') || '',
                    payment_method: formData.get('payment_method') || '',
                });

                renderCart(payload.cart);
                paymentMessage.textContent = `${payload.message} Pedido #${payload.order_id}.`;
                paymentStatusLabel.textContent = payload.status_label || 'Aguardando pagamento';
                paymentQr.src = `data:image/png;base64,${payload.qr_code_base64}`;
                currentPixCode = payload.pix_code;
                currentOrderSummary = payload.order_summary || null;
                currentPrintUrl = payload.print_url || '';
                if (printOrderTicketButton) {
                    printOrderTicketButton.hidden = !currentPrintUrl;
                }
                const firstNameInput = checkoutForm.querySelector('input[name="first_name"]');
                const lastNameInput = checkoutForm.querySelector('input[name="last_name"]');
                if (firstNameInput) {
                    firstNameInput.value = '';
                }
                if (lastNameInput) {
                    lastNameInput.value = '';
                }
                startPaymentStatusPolling(payload.order_id);
                openPaymentModal();
            } catch (error) {
                showError(error.message);
            }
        });
    }

    function bindLoginForm() {
        loginForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            const formData = new FormData(loginForm);

            try {
                await post(authLoginUrl, {
                    username: formData.get('username') || '',
                    password: formData.get('password') || '',
                });
                window.location.reload();
            } catch (error) {
                showError(error.message);
            }
        });
    }

    async function copyPixCode() {
        if (!currentPixCode) {
            showError('Código Pix indisponível.');
            return;
        }

        try {
            await navigator.clipboard.writeText(currentPixCode);
            window.alert('Código Pix copiado com sucesso.');
        } catch (error) {
            showError('Não foi possível copiar o código Pix.');
        }
    }

    function printOrderTicket() {
        if (!currentPrintUrl) {
            showError('URL de impressao indisponivel.');
            return;
        }
        window.open(currentPrintUrl, '_blank', 'noopener,noreferrer');
    }

    openCartButtons.forEach((button) => button.addEventListener('click', openCart));
    closeCartButton.addEventListener('click', closeCart);
    cartOverlay.addEventListener('click', closeCart);

    openLoginButtons.forEach((button) => {
        button.addEventListener('click', openLoginModal);
    });
    closeLoginModalButton.addEventListener('click', closeLoginModal);
    loginOverlay.addEventListener('click', closeLoginModal);

    closePaymentModalButton.addEventListener('click', closePaymentModal);
    paymentOverlay.addEventListener('click', closePaymentModal);
    copyPixCodeButton.addEventListener('click', copyPixCode);
    if (printOrderTicketButton) {
        printOrderTicketButton.addEventListener('click', printOrderTicket);
    }
    closeSuccessModalButton.addEventListener('click', closeSuccessModal);
    successOkButton.addEventListener('click', closeSuccessModal);
    successOverlay.addEventListener('click', closeSuccessModal);

    bindCardQuantityControls();
    bindVariantSelectors();
    bindAddToCartForms();
    bindCheckoutForm();
    bindLoginForm();
    renderCart(initialCart);
})();
