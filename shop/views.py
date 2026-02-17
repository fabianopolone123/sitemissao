import base64
import io
import os
import unicodedata
import uuid
from decimal import Decimal, InvalidOperation

import qrcode
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from .models import Order, Product, ProductVariant


def _get_cart(session):
    cart = session.get('cart')
    if not isinstance(cart, dict):
        cart = {}
        session['cart'] = cart
    return cart


def _product_payload(product):
    variants = product.variants.filter(active=True)
    return {
        'id': product.id,
        'name': product.name,
        'description': product.description,
        'cause': product.cause,
        'price': f'{product.price:.2f}',
        'image_url': product.image_url,
        'image_source': product.image_source,
        'active': product.active,
        'variants': [
            {
                'id': variant.id,
                'name': variant.name,
                'price': f'{variant.price:.2f}',
            }
            for variant in variants
        ],
    }


def _cart_item_key(product_id, variant_id=None):
    return f'{product_id}:{variant_id or 0}'


def _build_cart_payload(cart):
    product_ids = []
    variant_ids = []
    parsed_keys = []

    for item_key in cart.keys():
        try:
            pid_text, vid_text = str(item_key).split(':', 1)
            pid = int(pid_text)
            vid = int(vid_text)
            product_ids.append(pid)
            if vid > 0:
                variant_ids.append(vid)
            parsed_keys.append((item_key, pid, vid))
        except (ValueError, TypeError):
            continue

    products = Product.objects.filter(id__in=product_ids, active=True).prefetch_related('variants')
    product_map = {p.id: p for p in products}
    variant_map = {}
    if variant_ids:
        variants = ProductVariant.objects.filter(id__in=variant_ids, active=True)
        variant_map = {variant.id: variant for variant in variants}

    items = []
    total = Decimal('0.00')

    for item_key, pid, vid in parsed_keys:
        qty = cart.get(item_key, 0)
        product = product_map.get(pid)
        if not product:
            continue
        quantity = int(qty)
        variant = variant_map.get(vid) if vid > 0 else None
        if vid > 0 and (not variant or variant.product_id != product.id):
            continue
        unit_price = variant.price if variant else product.price
        subtotal = unit_price * quantity
        total += subtotal
        item_label = product.name
        if variant:
            item_label = f'{product.name} - {variant.name}'
        items.append(
            {
                'item_key': item_key,
                'id': product.id,
                'variant_id': variant.id if variant else None,
                'variant_name': variant.name if variant else '',
                'name': item_label,
                'price': f'{unit_price:.2f}',
                'quantity': quantity,
                'image_url': product.image_source,
                'subtotal': f'{subtotal:.2f}',
            }
        )

    return {
        'items': items,
        'total': f'{total:.2f}',
        'count': sum(item['quantity'] for item in items),
    }


def _emv_field(field_id, value):
    return f'{field_id}{len(value):02d}{value}'


def _crc16_ccitt(payload):
    crc = 0xFFFF
    for byte in payload.encode('utf-8'):
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return f'{crc:04X}'


def _sanitize_pix_text(text, max_len):
    normalized = unicodedata.normalize('NFKD', text)
    ascii_text = normalized.encode('ascii', 'ignore').decode('ascii')
    return ascii_text.strip().upper()[:max_len]


def _build_pix_code(amount, txid):
    pix_key = os.getenv('PIX_KEY', 'mission.andrews@example.com')
    merchant_name = _sanitize_pix_text(os.getenv('PIX_MERCHANT_NAME', 'MISSAO ANDREWS'), 25)
    merchant_city = _sanitize_pix_text(os.getenv('PIX_MERCHANT_CITY', 'SAO CARLOS'), 15)
    description = _sanitize_pix_text(os.getenv('PIX_DESCRIPTION', 'LOJA MISSAO ANDREWS'), 50)

    merchant_account = (
        _emv_field('00', 'BR.GOV.BCB.PIX')
        + _emv_field('01', pix_key)
        + _emv_field('02', description)
    )
    additional_data = _emv_field('05', _sanitize_pix_text(txid, 25))
    payload = (
        _emv_field('00', '01')
        + _emv_field('26', merchant_account)
        + _emv_field('52', '0000')
        + _emv_field('53', '986')
        + _emv_field('54', f'{amount:.2f}')
        + _emv_field('58', 'BR')
        + _emv_field('59', merchant_name)
        + _emv_field('60', merchant_city)
        + _emv_field('62', additional_data)
        + '6304'
    )
    crc = _crc16_ccitt(payload)
    return payload + crc


def _build_qr_base64(content):
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(content)
    qr.make(fit=True)
    image = qr.make_image(fill_color='black', back_color='white')
    stream = io.BytesIO()
    image.save(stream, format='PNG')
    return base64.b64encode(stream.getvalue()).decode('ascii')


def _staff_guard(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Faça login primeiro.'}, status=401)
    return None


def _can_manage(user):
    return user.is_authenticated


def _save_product_from_request(request, product=None):
    if product is None:
        product = Product()

    product.name = request.POST.get('name', '').strip()
    product.description = request.POST.get('description', '').strip()
    product.cause = request.POST.get('cause', '').strip() or 'Missões'
    active_value = request.POST.get('active', 'false').strip().lower()
    product.active = active_value in {'true', '1', 'on', 'yes'}

    try:
        product.price = Decimal(request.POST.get('price', '0').replace(',', '.'))
    except (InvalidOperation, AttributeError):
        return None, 'Preço inválido.'

    image_url = request.POST.get('image_url', '').strip()
    image_file = request.FILES.get('image_file')

    if image_url:
        product.image_url = image_url
    elif not product.image_url:
        product.image_url = 'https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=900&q=80'

    if image_file:
        product.image_file = image_file

    if not product.name:
        return None, 'Nome do produto é obrigatório.'

    product.save()
    variants_text = request.POST.get('variants_text', '').strip()
    parsed_variants = []
    if variants_text:
        lines = [line.strip() for line in variants_text.splitlines() if line.strip()]
        for line in lines:
            if '|' not in line:
                return None, 'Formato de variação inválido. Use: nome|preço'
            variant_name, variant_price_text = [part.strip() for part in line.split('|', 1)]
            if not variant_name:
                return None, 'Nome da variação é obrigatório.'
            try:
                variant_price = Decimal(variant_price_text.replace(',', '.'))
            except (InvalidOperation, AttributeError):
                return None, f'Preço inválido na variação: {variant_name}'
            parsed_variants.append((variant_name, variant_price))

    product.variants.all().delete()
    for variant_name, variant_price in parsed_variants:
        ProductVariant.objects.create(
            product=product,
            name=variant_name,
            price=variant_price,
            active=True,
        )
    return product, None


@require_GET
def home(request):
    products = Product.objects.filter(active=True).prefetch_related('variants')
    for product in products:
        product.active_variants = [variant for variant in product.variants.all() if variant.active]
        if product.active_variants:
            product.display_price = min(variant.price for variant in product.active_variants)
        else:
            product.display_price = product.price
    cart = _get_cart(request.session)
    cart_payload = _build_cart_payload(cart)
    return render(
        request,
        'shop/home.html',
        {
            'products': products,
            'cart': cart_payload,
        },
    )


@require_POST
def auth_login(request):
    username = request.POST.get('username', '').strip()
    password = request.POST.get('password', '')

    user = authenticate(request, username=username, password=password)
    if not user:
        return JsonResponse({'error': 'Usuário ou senha inválidos.'}, status=400)

    login(request, user)
    return JsonResponse(
        {
            'message': 'Login realizado com sucesso.',
            'user': {
                'username': user.username,
                'is_staff': user.is_staff,
            },
        }
    )


@require_POST
def auth_logout(request):
    logout(request)
    return JsonResponse({'message': 'Logout realizado com sucesso.'})


@login_required
@user_passes_test(_can_manage)
@require_GET
def manage_products_page(request):
    products = Product.objects.all().prefetch_related('variants').order_by('name')
    active_products = products.filter(active=True)
    inactive_products = products.filter(active=False)
    edit_id = request.GET.get('edit')
    editing_product = None
    editing_variants_text = ''
    if edit_id:
        editing_product = get_object_or_404(Product, id=edit_id)
        editing_variants_text = '\n'.join(
            f'{variant.name}|{variant.price:.2f}'
            for variant in editing_product.variants.filter(active=True).order_by('name')
        )

    return render(
        request,
        'shop/manage_products.html',
        {
            'products': products,
            'active_products': active_products,
            'inactive_products': inactive_products,
            'editing_product': editing_product,
            'editing_variants_text': editing_variants_text,
        },
    )


@login_required
@user_passes_test(_can_manage)
@require_POST
def manage_products_save_page(request):
    product_id = request.POST.get('product_id', '').strip()
    product = get_object_or_404(Product, id=product_id) if product_id else None
    saved_product, error = _save_product_from_request(request, product)
    if error:
        messages.error(request, error)
        if product_id:
            return redirect(f"/manage/products/page/?edit={product_id}")
        return redirect('manage_products_page')

    messages.success(request, 'Produto salvo com sucesso.')
    return redirect(f"/manage/products/page/?edit={saved_product.id}")


@login_required
@user_passes_test(_can_manage)
@require_POST
def manage_products_delete_page(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    product.delete()
    messages.success(request, 'Produto removido com sucesso.')
    return redirect('manage_products_page')


@require_GET
def product_manage_list(request):
    guard = _staff_guard(request)
    if guard:
        return guard

    products = Product.objects.all().order_by('name')
    return JsonResponse({'products': [_product_payload(product) for product in products]})


@require_POST
def product_manage_save(request):
    guard = _staff_guard(request)
    if guard:
        return guard

    product_id = request.POST.get('product_id', '').strip()
    product = get_object_or_404(Product, id=product_id) if product_id else None
    saved_product, error = _save_product_from_request(request, product)
    if error:
        return JsonResponse({'error': error}, status=400)

    return JsonResponse({'message': 'Produto salvo com sucesso.', 'product': _product_payload(saved_product)})


@require_POST
def product_manage_delete(request, product_id):
    guard = _staff_guard(request)
    if guard:
        return guard

    product = get_object_or_404(Product, id=product_id)
    product.delete()
    return JsonResponse({'message': 'Produto removido com sucesso.'})


@require_POST
def cart_add(request, product_id):
    product = get_object_or_404(Product, id=product_id, active=True)
    variant_id = request.POST.get('variant_id')
    variant = None
    if variant_id:
        try:
            variant = ProductVariant.objects.get(id=int(variant_id), product=product, active=True)
        except (ProductVariant.DoesNotExist, ValueError, TypeError):
            return JsonResponse({'error': 'Variação inválida para este produto.'}, status=400)

    try:
        quantity = int(request.POST.get('quantity', 1))
    except (TypeError, ValueError):
        quantity = 1
    quantity = max(1, quantity)
    cart = _get_cart(request.session)
    key = _cart_item_key(product.id, variant.id if variant else None)
    cart[key] = cart.get(key, 0) + quantity
    request.session.modified = True
    payload = _build_cart_payload(cart)
    return JsonResponse(payload)


@require_POST
def cart_update(request, product_id):
    product = get_object_or_404(Product, id=product_id, active=True)
    variant_id = request.POST.get('variant_id')
    variant = None
    if variant_id:
        try:
            variant = ProductVariant.objects.get(id=int(variant_id), product=product, active=True)
        except (ProductVariant.DoesNotExist, ValueError, TypeError):
            return JsonResponse({'error': 'Variação inválida para este produto.'}, status=400)

    action = request.POST.get('action', 'set')
    cart = _get_cart(request.session)
    key = _cart_item_key(product.id, variant.id if variant else None)
    current = int(cart.get(key, 0))

    if action == 'inc':
        current += 1
    elif action == 'dec':
        current -= 1
    else:
        try:
            current = int(request.POST.get('quantity', 1))
        except (TypeError, ValueError):
            current = 1

    if current <= 0:
        cart.pop(key, None)
    else:
        cart[key] = current

    request.session.modified = True
    payload = _build_cart_payload(cart)
    return JsonResponse(payload)


@require_POST
def checkout_finalize(request):
    first_name = request.POST.get('first_name', '').strip()
    last_name = request.POST.get('last_name', '').strip()
    whatsapp = request.POST.get('whatsapp', '').strip()
    payment_method = request.POST.get('payment_method', '').strip().lower()

    if not first_name or not last_name or not whatsapp:
        return JsonResponse({'error': 'Preencha nome, sobrenome e WhatsApp.'}, status=400)

    if payment_method != Order.PAYMENT_PIX:
        return JsonResponse({'error': 'Selecione a forma de pagamento Pix.'}, status=400)

    cart = _get_cart(request.session)
    cart_payload = _build_cart_payload(cart)
    if cart_payload['count'] <= 0:
        return JsonResponse({'error': 'Seu carrinho está vazio.'}, status=400)

    amount = Decimal(cart_payload['total'])
    txid = f'PED{uuid.uuid4().hex[:12].upper()}'
    pix_code = _build_pix_code(amount, txid)
    qr_base64 = _build_qr_base64(pix_code)

    order = Order.objects.create(
        first_name=first_name,
        last_name=last_name,
        whatsapp=whatsapp,
        payment_method=payment_method,
        total=amount,
        pix_code=pix_code,
        items_json=cart_payload['items'],
    )

    request.session['cart'] = {}
    request.session.modified = True

    return JsonResponse(
        {
            'message': 'Pedido gerado com sucesso. Faça o pagamento no Pix.',
            'order_id': order.id,
            'qr_code_base64': qr_base64,
            'pix_code': pix_code,
            'cart': _build_cart_payload(request.session['cart']),
        }
    )
