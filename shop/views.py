from decimal import Decimal

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from .models import Product


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
