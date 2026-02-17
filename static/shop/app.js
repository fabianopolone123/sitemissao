(function () {
    const sidebar = document.getElementById('cart-sidebar');
    const overlay = document.getElementById('cart-overlay');
    const openCartButton = document.getElementById('open-cart');
    const closeCartButton = document.getElementById('close-cart');
    const cartCount = document.getElementById('cart-count');
    const cartTotal = document.getElementById('cart-total');
    const cartItems = document.getElementById('cart-items');
    const checkoutForm = document.getElementById('checkout-form');
    const paymentResult = document.getElementById('payment-result');
    const paymentMessage = document.getElementById('payment-message');
    const paymentQr = document.getElementById('payment-qr');
    const pixCode = document.getElementById('pix-code');
    const initialCart = JSON.parse(document.getElementById('initial-cart').textContent);
    const cartUpdateTemplate = document.body.dataset.cartUpdateTemplate;
    const checkoutFinalizeUrl = document.body.dataset.checkoutFinalizeUrl;

    function openCart() {
        sidebar.classList.add('open');
        overlay.classList.add('open');
        sidebar.setAttribute('aria-hidden', 'false');
    }

    function closeCart() {
        sidebar.classList.remove('open');
        overlay.classList.remove('open');
        sidebar.setAttribute('aria-hidden', 'true');
    }

    function csrfToken() {
        const input = document.querySelector('input[name=csrfmiddlewaretoken]');
        return input ? input.value : '';
    }

    function showError(message) {
        window.alert(message);
    }

    function resetPaymentResult() {
        paymentResult.hidden = true;
        paymentMessage.textContent = '';
        paymentQr.removeAttribute('src');
        pixCode.value = '';
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

    function renderCart(cart) {
        cartCount.textContent = cart.count;
        cartTotal.textContent = `R$ ${cart.total}`;

        if (!cart.items.length) {
            cartItems.innerHTML = '<p>Seu carrinho está vazio.</p>';
            return;
        }

        cartItems.innerHTML = cart.items
            .map(
                (item) => `
                    <article class="cart-item" data-id="${item.id}">
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

    function bindAddToCartForms() {
        document.querySelectorAll('.add-form').forEach((form) => {
            form.addEventListener('submit', async (event) => {
                event.preventDefault();
                try {
                    const quantity = form.querySelector('.qty-input').value;
                    const cart = await post(form.dataset.url, { quantity });
                    renderCart(cart);
                    resetPaymentResult();
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
            const updateUrl = cartUpdateTemplate.replace('/0/', `/${id}/`);
            row.querySelectorAll('button').forEach((button) => {
                button.addEventListener('click', async () => {
                    try {
                        const action = button.dataset.action;
                        const cart = await post(updateUrl, {
                            action: action === 'remove' ? 'set' : action,
                            quantity: action === 'remove' ? '0' : '1',
                        });
                        renderCart(cart);
                        resetPaymentResult();
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
            const body = {
                first_name: formData.get('first_name') || '',
                last_name: formData.get('last_name') || '',
                whatsapp: formData.get('whatsapp') || '',
                payment_method: formData.get('payment_method') || '',
            };

            try {
                const payload = await post(checkoutFinalizeUrl, body);
                renderCart(payload.cart);
                paymentResult.hidden = false;
                paymentMessage.textContent = `${payload.message} Pedido #${payload.order_id}.`;
                paymentQr.src = `data:image/png;base64,${payload.qr_code_base64}`;
                pixCode.value = payload.pix_code;
            } catch (error) {
                showError(error.message);
            }
        });
    }

    openCartButton.addEventListener('click', openCart);
    closeCartButton.addEventListener('click', closeCart);
    overlay.addEventListener('click', closeCart);

    bindCardQuantityControls();
    bindAddToCartForms();
    bindCheckoutForm();
    renderCart(initialCart);
})();
