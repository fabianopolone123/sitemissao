import hashlib
import hmac
import json
import os
import random
import time
from decimal import Decimal, InvalidOperation
from urllib import error, request as urllib_request

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import Order, Product, ProductVariant, WhatsAppRecipient


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


def _staff_guard(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'FaÃ§a login primeiro.'}, status=401)
    return None


def _can_manage(user):
    return user.is_authenticated


def _save_product_from_request(request, product=None):
    if product is None:
        product = Product()

    product.name = request.POST.get('name', '').strip()
    product.description = request.POST.get('description', '').strip()
    product.cause = request.POST.get('cause', '').strip() or 'MissÃµes'
    active_value = request.POST.get('active', 'false').strip().lower()
    product.active = active_value in {'true', '1', 'on', 'yes'}

    try:
        product.price = Decimal(request.POST.get('price', '0').replace(',', '.'))
    except (InvalidOperation, AttributeError):
        return None, 'PreÃ§o invÃ¡lido.'

    image_url = request.POST.get('image_url', '').strip()
    image_file = request.FILES.get('image_file')

    if image_url:
        product.image_url = image_url
    elif not product.image_url:
        product.image_url = 'https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=900&q=80'

    if image_file:
        product.image_file = image_file

    if not product.name:
        return None, 'Nome do produto Ã© obrigatÃ³rio.'

    product.save()
    variants_text = request.POST.get('variants_text', '').strip()
    parsed_variants = []
    if variants_text:
        lines = [line.strip() for line in variants_text.splitlines() if line.strip()]
        for line in lines:
            if '|' not in line:
                return None, 'Formato de variaÃ§Ã£o invÃ¡lido. Use: nome|preÃ§o'
            variant_name, variant_price_text = [part.strip() for part in line.split('|', 1)]
            if not variant_name:
                return None, 'Nome da variaÃ§Ã£o Ã© obrigatÃ³rio.'
            try:
                variant_price = Decimal(variant_price_text.replace(',', '.'))
            except (InvalidOperation, AttributeError):
                return None, f'PreÃ§o invÃ¡lido na variaÃ§Ã£o: {variant_name}'
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


def _normalize_whatsapp_phone(value):
    digits = ''.join(ch for ch in (value or '') if ch.isdigit())
    if not digits:
        return ''
    digits = digits.lstrip('0')
    if digits.startswith('55'):
        return digits
    if len(digits) in {10, 11}:
        return f'55{digits}'
    return digits


def _wapi_send_text(phone, message):
    instance_id = os.getenv('WAPI_INSTANCE_ID', '').strip()
    token = os.getenv('WAPI_TOKEN', '').strip()
    if not instance_id or not token:
        raise ValueError('W-API nao configurada. Defina WAPI_INSTANCE_ID e WAPI_TOKEN.')

    url = f'https://api.w-api.app/v1/message/send-text?instanceId={instance_id}'
    payload = {
        'phone': phone,
        'message': message,
    }
    req = urllib_request.Request(
        url=url,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        },
        method='POST',
    )
    try:
        with urllib_request.urlopen(req, timeout=30) as response:
            if response.status != 200:
                raise ValueError(f'W-API retornou HTTP {response.status}.')
    except error.HTTPError as exc:
        body = exc.read().decode('utf-8', 'ignore')
        raise ValueError(f'Erro W-API HTTP {exc.code}: {body}') from exc


def _build_order_whatsapp_message(order):
    lines = [
        'Pagamento aprovado!',
        f'Pedido #{order.id}',
        f'Cliente: {order.first_name} {order.last_name}',
        f'WhatsApp: {order.whatsapp}',
        f'Total: R$ {order.total:.2f}',
        '',
        'Itens:',
    ]
    for item in order.items_json:
        qty = item.get('quantity', 0)
        name = item.get('name', 'Item')
        subtotal = item.get('subtotal', '0.00')
        lines.append(f'- {qty}x {name} | R$ {subtotal}')

    lines.extend(
        [
            '',
            'Retirada: Colegio Adventista de Sao Carlos',
            'Data: 21/02/2026 a partir das 19:30',
            '',
            'Obrigado! Sua contribuicao ajuda a Missao Andrews a alcancar mais criancas e familias.',
        ]
    )
    return '\n'.join(lines)


def _wapi_delay_bounds():
    min_delay = os.getenv('WAPI_QUEUE_MIN_DELAY_SECONDS', '2').strip()
    max_delay = os.getenv('WAPI_QUEUE_MAX_DELAY_SECONDS', '5').strip()
    try:
        minimum = max(0.0, float(min_delay))
    except ValueError:
        minimum = 2.0
    try:
        maximum = max(0.0, float(max_delay))
    except ValueError:
        maximum = 5.0
    if minimum > maximum:
        minimum, maximum = maximum, minimum
    return minimum, maximum


def _send_whatsapp_notifications_for_order(order):
    # Lock idempotente: se outro processo/webhook ja marcou envio, nao envia de novo.
    updated = Order.objects.filter(id=order.id, whatsapp_notified=False).update(
        whatsapp_notified=True,
        whatsapp_notified_at=timezone.now(),
        whatsapp_notify_error='',
    )
    if updated == 0:
        return

    phones = set()
    buyer_phone = _normalize_whatsapp_phone(order.whatsapp)
    if buyer_phone:
        phones.add(buyer_phone)

    for recipient in WhatsAppRecipient.objects.filter(active=True):
        normalized = _normalize_whatsapp_phone(recipient.phone)
        if normalized:
            phones.add(normalized)

    if not phones:
        order.whatsapp_notify_error = 'Nenhum telefone valido para envio.'
        order.save(update_fields=['whatsapp_notify_error'])
        return

    message = _build_order_whatsapp_message(order)
    errors = []
    minimum_delay, maximum_delay = _wapi_delay_bounds()
    for index, phone in enumerate(sorted(phones)):
        if index > 0 and maximum_delay > 0:
            time.sleep(random.uniform(minimum_delay, maximum_delay))
        try:
            _wapi_send_text(phone, message)
        except ValueError as exc:
            errors.append(str(exc))

    order.whatsapp_notify_error = '; '.join(errors)[:255] if errors else ''
    order.save(update_fields=['whatsapp_notify_error'])


def _mp_access_token():
    return os.getenv('MP_ACCESS_TOKEN_PROD', '').strip()


def _mp_api_request(method, path, payload=None):
    token = _mp_access_token()
    if not token:
        raise ValueError('MP_ACCESS_TOKEN_PROD nÃ£o configurado no servidor.')

    url = f'https://api.mercadopago.com{path}'
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json',
    }
    data = None

    if payload is not None:
        headers['Content-Type'] = 'application/json'
        headers['X-Idempotency-Key'] = hashlib.sha256(os.urandom(16)).hexdigest()
        data = json.dumps(payload).encode('utf-8')

    req = urllib_request.Request(url=url, data=data, headers=headers, method=method)
    try:
        with urllib_request.urlopen(req, timeout=30) as response:
            body = response.read().decode('utf-8')
            return json.loads(body) if body else {}
    except error.HTTPError as exc:
        try:
            body = exc.read().decode('utf-8')
            details = json.loads(body)
            message = details.get('message') or details.get('error') or body
        except Exception:
            message = str(exc)
        raise ValueError(f'Erro Mercado Pago: {message}') from exc


def _mp_generate_payer_email(order):
    digits = ''.join(ch for ch in order.whatsapp if ch.isdigit())
    suffix = digits[-11:] if digits else 'cliente'
    return f'pedido{order.id}.{suffix}@missaoandrewsc.com.br'


def _create_mp_pix_payment(order):
    external_reference = f'ORDER_{order.id}'
    payload = {
        'transaction_amount': float(order.total),
        'description': f'Pedido #{order.id} - Loja MissÃ£o Andrews',
        'payment_method_id': 'pix',
        'external_reference': external_reference,
        'notification_url': os.getenv('MP_NOTIFICATION_URL', 'https://missaoandrewsc.com.br/payments/webhook/'),
        'payer': {
            'email': _mp_generate_payer_email(order),
            'first_name': order.first_name[:60],
            'last_name': order.last_name[:60],
        },
    }
    payment = _mp_api_request('POST', '/v1/payments', payload)
    tx_data = payment.get('point_of_interaction', {}).get('transaction_data', {})
    pix_code = tx_data.get('qr_code', '')
    qr_base64 = tx_data.get('qr_code_base64', '')

    if not pix_code or not qr_base64:
        raise ValueError('Mercado Pago nÃ£o retornou QR Code Pix para este pagamento.')

    return {
        'payment_id': str(payment.get('id', '')),
        'external_reference': external_reference,
        'status': payment.get('status', '') or '',
        'status_detail': payment.get('status_detail', '') or '',
        'pix_code': pix_code,
        'qr_base64': qr_base64,
    }


def _get_mp_payment(payment_id):
    return _mp_api_request('GET', f'/v1/payments/{payment_id}')


def _sync_order_from_mp_payment(order, payment_data):
    status = (payment_data.get('status') or '').lower()
    status_detail = payment_data.get('status_detail') or ''
    payment_id = str(payment_data.get('id') or '')
    external_reference = payment_data.get('external_reference') or order.mp_external_reference

    update_fields = []
    if payment_id and payment_id != order.mp_payment_id:
        order.mp_payment_id = payment_id
        update_fields.append('mp_payment_id')
    if external_reference and external_reference != order.mp_external_reference:
        order.mp_external_reference = external_reference
        update_fields.append('mp_external_reference')
    if status != order.mp_status:
        order.mp_status = status
        update_fields.append('mp_status')
    if status_detail != order.mp_status_detail:
        order.mp_status_detail = status_detail
        update_fields.append('mp_status_detail')

    if status == 'approved' and not order.is_paid:
        order.is_paid = True
        order.paid_at = timezone.now()
        update_fields.extend(['is_paid', 'paid_at'])
    elif status != 'approved' and order.is_paid:
        order.is_paid = False
        order.paid_at = None
        update_fields.extend(['is_paid', 'paid_at'])

    if update_fields:
        order.save(update_fields=update_fields)

    if order.is_paid and not order.whatsapp_notified:
        _send_whatsapp_notifications_for_order(order)


def _is_valid_mp_webhook_signature(request, payment_id):
    secret = os.getenv('MP_WEBHOOK_SECRET', '').strip()
    if not secret:
        return True

    signature = request.headers.get('x-signature', '')
    request_id = request.headers.get('x-request-id', '')
    if not signature or not request_id:
        return False

    ts_value = ''
    v1_value = ''
    for part in signature.split(','):
        key, _, value = part.strip().partition('=')
        if key == 'ts':
            ts_value = value
        elif key == 'v1':
            v1_value = value

    if not ts_value or not v1_value:
        return False

    manifest = f'id:{payment_id};request-id:{request_id};ts:{ts_value};'
    expected = hmac.new(secret.encode('utf-8'), manifest.encode('utf-8'), hashlib.sha256).hexdigest()
    return constant_time_compare(expected, v1_value)


def _extract_webhook_payment_id(request):
    payment_id = request.GET.get('data.id') or request.GET.get('id')
    if payment_id:
        return str(payment_id)

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        payload = {}

    if isinstance(payload, dict):
        data = payload.get('data', {})
        if isinstance(data, dict) and data.get('id'):
            return str(data['id'])
        if payload.get('id'):
            return str(payload['id'])
    return ''


def _order_status_label(order):
    if order.is_paid:
        return 'Pagamento aprovado'
    status_map = {
        'pending': 'Aguardando pagamento',
        'in_process': 'Processando pagamento',
        'rejected': 'Pagamento recusado',
        'cancelled': 'Pagamento cancelado',
    }
    return status_map.get(order.mp_status, 'Aguardando pagamento')


@require_GET
def home(request):
    products = Product.objects.filter(active=True).prefetch_related('variants')
    for product in products:
        product.active_variants = [variant for variant in product.variants.all() if variant.active]
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
        return JsonResponse({'error': 'UsuÃ¡rio ou senha invÃ¡lidos.'}, status=400)

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
    orders = Order.objects.all().order_by('-created_at')
    whatsapp_recipients = WhatsAppRecipient.objects.all().order_by('name')
    users = User.objects.all().order_by('username')
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
            'orders': orders,
            'whatsapp_recipients': whatsapp_recipients,
            'users': users,
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


@login_required
@user_passes_test(_can_manage)
@require_POST
def manage_order_delivery_page(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    action = request.POST.get('action', '').strip().lower()

    if action == 'mark_delivered':
        order.is_delivered = True
        order.delivered_at = timezone.now()
        order.save(update_fields=['is_delivered', 'delivered_at'])
        messages.success(request, f'Pedido #{order.id} marcado como entregue.')
    elif action == 'mark_undelivered':
        order.is_delivered = False
        order.delivered_at = None
        order.save(update_fields=['is_delivered', 'delivered_at'])
        messages.success(request, f'Pedido #{order.id} marcado como nao entregue.')
    else:
        messages.error(request, 'Acao invalida para status de entrega.')

    return redirect('manage_products_page')


@login_required
@user_passes_test(_can_manage)
@require_POST
def manage_users_create_page(request):
    username = request.POST.get('username', '').strip()
    password = request.POST.get('password', '').strip()
    password_confirm = request.POST.get('password_confirm', '').strip()
    is_staff = request.POST.get('is_staff', '').strip().lower() in {'1', 'true', 'on', 'yes'}

    if not username or not password:
        messages.error(request, 'Preencha usuÃ¡rio e senha para criar o login.')
        return redirect('manage_products_page')

    if password != password_confirm:
        messages.error(request, 'As senhas nÃ£o conferem.')
        return redirect('manage_products_page')

    if User.objects.filter(username=username).exists():
        messages.error(request, 'Este nome de usuÃ¡rio jÃ¡ existe.')
        return redirect('manage_products_page')

    user = User.objects.create_user(username=username, password=password)
    user.is_staff = is_staff
    user.save(update_fields=['is_staff'])
    messages.success(request, f'UsuÃ¡rio "{username}" criado com sucesso.')
    return redirect('manage_products_page')


@login_required
@user_passes_test(_can_manage)
@require_POST
def manage_whatsapp_recipient_create_page(request):
    name = request.POST.get('name', '').strip()
    phone_raw = request.POST.get('phone', '').strip()
    phone = _normalize_whatsapp_phone(phone_raw)

    if not name or not phone:
        messages.error(request, 'Informe nome e WhatsApp validos para cadastrar.')
        return redirect('manage_products_page')

    recipient, created = WhatsAppRecipient.objects.get_or_create(
        phone=phone,
        defaults={'name': name, 'active': True},
    )
    if created:
        messages.success(request, f'Contato WhatsApp "{name}" cadastrado.')
    else:
        recipient.name = name
        recipient.active = True
        recipient.save(update_fields=['name', 'active'])
        messages.success(request, f'Contato WhatsApp "{name}" atualizado.')
    return redirect('manage_products_page')


@login_required
@user_passes_test(_can_manage)
@require_POST
def manage_whatsapp_recipient_delete_page(request, recipient_id):
    recipient = get_object_or_404(WhatsAppRecipient, id=recipient_id)
    recipient.delete()
    messages.success(request, 'Contato WhatsApp removido.')
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
            return JsonResponse({'error': 'VariaÃ§Ã£o invÃ¡lida para este produto.'}, status=400)

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
            return JsonResponse({'error': 'VariaÃ§Ã£o invÃ¡lida para este produto.'}, status=400)

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
        return JsonResponse({'error': 'Seu carrinho estÃ¡ vazio.'}, status=400)

    amount = Decimal(cart_payload['total'])
    order = Order.objects.create(
        first_name=first_name,
        last_name=last_name,
        whatsapp=whatsapp,
        payment_method=payment_method,
        total=amount,
        pix_code='',
        items_json=cart_payload['items'],
        mp_status='pending',
    )

    try:
        pix_payload = _create_mp_pix_payment(order)
    except ValueError as exc:
        order.delete()
        return JsonResponse({'error': str(exc)}, status=400)

    order.pix_code = pix_payload['pix_code']
    order.mp_payment_id = pix_payload['payment_id']
    order.mp_external_reference = pix_payload['external_reference']
    order.mp_status = (pix_payload['status'] or 'pending').lower()
    order.mp_status_detail = pix_payload['status_detail']
    if order.mp_status == 'approved':
        order.is_paid = True
        order.paid_at = timezone.now()
    order.save()
    if order.is_paid and not order.whatsapp_notified:
        _send_whatsapp_notifications_for_order(order)

    request.session['cart'] = {}
    request.session.modified = True

    order_summary = {
        'customer_name': f'{order.first_name} {order.last_name}'.strip(),
        'whatsapp': order.whatsapp,
        'total': f'{order.total:.2f}',
        'items': order.items_json,
    }

    return JsonResponse(
        {
            'message': 'Pedido gerado com sucesso. FaÃ§a o pagamento no Pix.',
            'order_id': order.id,
            'order_status': order.mp_status,
            'status_label': _order_status_label(order),
            'qr_code_base64': pix_payload['qr_base64'],
            'pix_code': pix_payload['pix_code'],
            'order_summary': order_summary,
            'cart': _build_cart_payload(request.session['cart']),
        }
    )


@require_GET
def checkout_status(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    if order.mp_payment_id and not order.is_paid and order.mp_status in {'pending', 'in_process'}:
        try:
            payment_data = _get_mp_payment(order.mp_payment_id)
            _sync_order_from_mp_payment(order, payment_data)
            order.refresh_from_db()
        except ValueError:
            pass

    return JsonResponse(
        {
            'order_id': order.id,
            'is_paid': order.is_paid,
            'status': order.mp_status,
            'status_detail': order.mp_status_detail,
            'status_label': _order_status_label(order),
        }
    )


@csrf_exempt
@require_POST
def payments_webhook(request):
    payment_id = _extract_webhook_payment_id(request)
    if not payment_id:
        return JsonResponse({'ok': True, 'ignored': 'without_payment_id'})

    if not _is_valid_mp_webhook_signature(request, payment_id):
        return JsonResponse({'error': 'assinatura invÃ¡lida'}, status=401)

    try:
        payment_data = _get_mp_payment(payment_id)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'payment_lookup_failed'}, status=400)

    external_reference = payment_data.get('external_reference', '')
    order = None
    if external_reference.startswith('ORDER_'):
        try:
            order_id = int(external_reference.replace('ORDER_', '', 1))
            order = Order.objects.filter(id=order_id).first()
        except ValueError:
            order = None
    if order is None:
        order = Order.objects.filter(mp_payment_id=str(payment_data.get('id', ''))).first()
    if order is None:
        return JsonResponse({'ok': True, 'ignored': 'order_not_found'})

    _sync_order_from_mp_payment(order, payment_data)
    return JsonResponse({'ok': True})



