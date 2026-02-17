import base64
import io
import os
import unicodedata
import uuid
from decimal import Decimal

import qrcode
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from .models import Order, Product


def _get_cart(session):
    cart = session.get('cart')
    if not isinstance(cart, dict):
        cart = {}
        session['cart'] = cart
    return cart


def _build_cart_payload(cart):
    product_ids = [int(pid) for pid in cart.keys()]
    products = Product.objects.filter(id__in=product_ids, active=True)
    product_map = {str(p.id): p for p in products}
    items = []
    total = Decimal('0.00')

    for pid, qty in cart.items():
        product = product_map.get(pid)
        if not product:
            continue
        quantity = int(qty)
        subtotal = product.price * quantity
        total += subtotal
        items.append(
            {
                'id': product.id,
                'name': product.name,
                'price': f'{product.price:.2f}',
                'quantity': quantity,
                'image_url': product.image_url,
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


@require_GET
def home(request):
    products = Product.objects.filter(active=True)
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
def cart_add(request, product_id):
    product = get_object_or_404(Product, id=product_id, active=True)
    try:
        quantity = int(request.POST.get('quantity', 1))
    except (TypeError, ValueError):
        quantity = 1
    quantity = max(1, quantity)
    cart = _get_cart(request.session)
    key = str(product.id)
    cart[key] = cart.get(key, 0) + quantity
    request.session.modified = True
    payload = _build_cart_payload(cart)
    return JsonResponse(payload)


@require_POST
def cart_update(request, product_id):
    product = get_object_or_404(Product, id=product_id, active=True)
    action = request.POST.get('action', 'set')
    cart = _get_cart(request.session)
    key = str(product.id)
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
