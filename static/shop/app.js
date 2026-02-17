(function () {
    const sidebar = document.getElementById('cart-sidebar');
    const overlay = document.getElementById('cart-overlay');
    const openCartButton = document.getElementById('open-cart');
    const closeCartButton = document.getElementById('close-cart');
    const cartCount = document.getElementById('cart-count');
    const cartTotal = document.getElementById('cart-total');
    const cartItems = document.getElementById('cart-items');
    const initialCart = JSON.parse(document.getElementById('initial-cart').textContent);
    const cartUpdateTemplate = document.body.dataset.cartUpdateTemplate;

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
        if (!response.ok) {
            throw new Error('Falha ao atualizar carrinho.');
        }
        return response.json();
    }

    function bindAddToCartForms() {
        document.querySelectorAll('.add-form').forEach((form) => {
            form.addEventListener('submit', async (event) => {
                event.preventDefault();
                const quantity = form.querySelector('.qty-input').value;
                const cart = await post(form.dataset.url, { quantity });
                renderCart(cart);
                openCart();
            });
        });
    }

    function bindCartActions() {
        cartItems.querySelectorAll('.cart-item').forEach((row) => {
            const id = row.dataset.id;
            const updateUrl = cartUpdateTemplate.replace('/0/', `/${id}/`);
            row.querySelectorAll('button').forEach((button) => {
                button.addEventListener('click', async () => {
                    const action = button.dataset.action;
                    const cart = await post(updateUrl, {
                        action: action === 'remove' ? 'set' : action,
                        quantity: action === 'remove' ? '0' : '1',
                    });
                    renderCart(cart);
                });
            });
        });
    }

    openCartButton.addEventListener('click', openCart);
    closeCartButton.addEventListener('click', closeCart);
    overlay.addEventListener('click', closeCart);

    bindCardQuantityControls();
    bindAddToCartForms();
    renderCart(initialCart);
})();
