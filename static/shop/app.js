(function () {
    const sidebar = document.getElementById('cart-sidebar');
    const cartOverlay = document.getElementById('cart-overlay');
    const openCartButtons = document.querySelectorAll('[data-open-cart]');
    const closeCartButton = document.getElementById('close-cart');
    const cartCountBadges = document.querySelectorAll('.cart-count-badge');
    const cartTotal = document.getElementById('cart-total');
    const cartItems = document.getElementById('cart-items');
    const checkoutForm = document.getElementById('checkout-form');

    const authOverlay = document.getElementById('auth-modal-overlay');
    const loginModal = document.getElementById('login-modal');
    const productPanelModal = document.getElementById('product-panel-modal');
    const paymentModal = document.getElementById('payment-modal');

    const loginForm = document.getElementById('login-form');
    const productForm = document.getElementById('product-form');
    const panelProductList = document.getElementById('panel-product-list');
    const newProductBtn = document.getElementById('new-product-btn');

    const closeLoginModalButton = document.getElementById('close-login-modal');
    const closeProductPanelButton = document.getElementById('close-product-panel');
    const closePaymentModalButton = document.getElementById('close-payment-modal');

    const openLoginButtons = document.querySelectorAll('#open-login-mobile, #open-login-desktop');
    const openPanelButtons = document.querySelectorAll('#open-panel-mobile, #open-panel-desktop');

    const copyPixCodeButton = document.getElementById('copy-pix-code');
    const paymentMessage = document.getElementById('payment-message');
    const paymentQr = document.getElementById('payment-qr');

    const initialCart = JSON.parse(document.getElementById('initial-cart').textContent);
    const cartUpdateTemplate = document.body.dataset.cartUpdateTemplate;
    const checkoutFinalizeUrl = document.body.dataset.checkoutFinalizeUrl;
    const authLoginUrl = document.body.dataset.authLoginUrl;
    const manageProductsUrl = document.body.dataset.manageProductsUrl;
    const manageProductsSaveUrl = document.body.dataset.manageProductsSaveUrl;
    const manageProductsDeleteTemplate = document.body.dataset.manageProductsDeleteTemplate;

    let isStaffUser = document.body.dataset.userStaff === 'true';
    let currentPixCode = '';

    function csrfToken() {
        const input = document.querySelector('input[name=csrfmiddlewaretoken]');
        return input ? input.value : '';
    }

    function showError(message) {
        window.alert(message);
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

    function closeAuthModals() {
        loginModal.hidden = true;
        productPanelModal.hidden = true;
        paymentModal.hidden = true;
        authOverlay.hidden = true;
    }

    function openModal(modal) {
        closeCart();
        authOverlay.hidden = false;
        loginModal.hidden = true;
        productPanelModal.hidden = true;
        paymentModal.hidden = true;
        modal.hidden = false;
    }

    function syncStaffUI() {
        openPanelButtons.forEach((button) => {
            button.hidden = !isStaffUser;
        });
        openLoginButtons.forEach((button) => {
            button.textContent = isStaffUser ? 'Administrador' : 'Login';
        });
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

    async function postMultipart(url, formData) {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken(),
            },
            body: formData,
        });
        return parseResponse(response);
    }

    async function getJson(url) {
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
            },
        });
        return parseResponse(response);
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

    function bindAddToCartForms() {
        document.querySelectorAll('.add-form').forEach((form) => {
            form.addEventListener('submit', async (event) => {
                event.preventDefault();
                try {
                    const quantity = form.querySelector('.qty-input').value;
                    const cart = await post(form.dataset.url, { quantity });
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
                paymentQr.src = `data:image/png;base64,${payload.qr_code_base64}`;
                currentPixCode = payload.pix_code;
                openModal(paymentModal);
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

    function fillProductForm(product) {
        productForm.querySelector('input[name=product_id]').value = product.id;
        productForm.querySelector('input[name=name]').value = product.name;
        productForm.querySelector('input[name=cause]').value = product.cause;
        productForm.querySelector('input[name=price]').value = product.price;
        productForm.querySelector('textarea[name=description]').value = product.description || '';
        productForm.querySelector('input[name=image_url]').value = product.image_url || '';
        productForm.querySelector('input[name=active]').checked = !!product.active;
    }

    function resetProductForm() {
        productForm.reset();
        productForm.querySelector('input[name=product_id]').value = '';
        productForm.querySelector('input[name=active]').checked = true;
    }

    function renderManageProducts(products) {
        if (!products.length) {
            panelProductList.innerHTML = '<p>Nenhum produto cadastrado.</p>';
            return;
        }

        panelProductList.innerHTML = products
            .map(
                (product) => `
                    <article class="panel-row" data-id="${product.id}">
                        <img src="${product.image_source}" alt="${product.name}">
                        <div>
                            <strong>${product.name}</strong>
                            <div class="cart-meta">R$ ${product.price} | ${product.active ? 'Ativo' : 'Inativo'}</div>
                            <div class="panel-row-actions">
                                <button type="button" data-edit="${product.id}">Editar</button>
                                <button type="button" data-delete="${product.id}" class="danger-btn">Remover</button>
                            </div>
                        </div>
                    </article>
                `
            )
            .join('');

        panelProductList.querySelectorAll('[data-edit]').forEach((button) => {
            button.addEventListener('click', () => {
                const id = Number(button.dataset.edit);
                const product = products.find((item) => item.id === id);
                if (product) {
                    fillProductForm(product);
                }
            });
        });

        panelProductList.querySelectorAll('[data-delete]').forEach((button) => {
            button.addEventListener('click', async () => {
                const id = Number(button.dataset.delete);
                if (!window.confirm('Deseja remover este produto?')) {
                    return;
                }

                try {
                    const deleteUrl = manageProductsDeleteTemplate.replace('/0/', `/${id}/`);
                    await post(deleteUrl, {});
                    window.location.reload();
                } catch (error) {
                    showError(error.message);
                }
            });
        });
    }

    async function loadManageProductsAndOpen() {
        if (!isStaffUser) {
            showError('Faça login com usuário administrador para abrir o painel.');
            return;
        }

        try {
            const payload = await getJson(manageProductsUrl);
            renderManageProducts(payload.products || []);
            openModal(productPanelModal);
        } catch (error) {
            showError(error.message);
        }
    }

    function bindLoginForm() {
        loginForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            const formData = new FormData(loginForm);

            try {
                const payload = await post(authLoginUrl, {
                    username: formData.get('username') || '',
                    password: formData.get('password') || '',
                });
                isStaffUser = !!(payload.user && payload.user.is_staff);
                syncStaffUI();
                closeAuthModals();
                if (isStaffUser) {
                    await loadManageProductsAndOpen();
                } else {
                    window.alert('Login realizado, mas seu usuário não possui permissão de administrador.');
                }
            } catch (error) {
                showError(error.message);
            }
        });
    }

    function bindProductForm() {
        productForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            const formData = new FormData(productForm);

            try {
                await postMultipart(manageProductsSaveUrl, formData);
                window.location.reload();
            } catch (error) {
                showError(error.message);
            }
        });

        newProductBtn.addEventListener('click', resetProductForm);
    }

    openCartButtons.forEach((button) => button.addEventListener('click', openCart));
    closeCartButton.addEventListener('click', closeCart);
    cartOverlay.addEventListener('click', closeCart);

    openLoginButtons.forEach((button) => {
        button.addEventListener('click', () => openModal(loginModal));
    });

    openPanelButtons.forEach((button) => {
        button.addEventListener('click', loadManageProductsAndOpen);
    });

    closeLoginModalButton.addEventListener('click', closeAuthModals);
    closeProductPanelButton.addEventListener('click', closeAuthModals);
    closePaymentModalButton.addEventListener('click', closeAuthModals);
    authOverlay.addEventListener('click', closeAuthModals);
    copyPixCodeButton.addEventListener('click', copyPixCode);

    bindCardQuantityControls();
    bindAddToCartForms();
    bindCartActions();
    bindCheckoutForm();
    bindLoginForm();
    bindProductForm();
    syncStaffUI();
    renderCart(initialCart);
})();
