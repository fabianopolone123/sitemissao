from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import DonationEntry, Order, Product, ProductVariant


class StoreFlowTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='Pastel de Queijo',
            description='Tradicional',
            cause='Missoes',
            price=Decimal('10.00'),
            image_url='https://example.com/pastel.jpg',
            active=True,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            name='Grande',
            price=Decimal('12.50'),
            active=True,
        )
        self.inactive_product = Product.objects.create(
            name='Produto Inativo',
            description='Nao aparece na loja',
            cause='Missoes',
            price=Decimal('9.00'),
            image_url='https://example.com/inativo.jpg',
            active=False,
        )
        self.user = User.objects.create_user(username='admin', password='senha-segura')

    def test_home_shows_only_active_products(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.name)
        self.assertNotContains(response, self.inactive_product.name)

    def test_cart_add_and_update_quantity(self):
        add_response = self.client.post(
            reverse('cart_add', args=[self.product.id]),
            {'quantity': 2, 'variant_id': self.variant.id},
        )

        self.assertEqual(add_response.status_code, 200)
        add_payload = add_response.json()
        self.assertEqual(add_payload['count'], 2)
        self.assertEqual(add_payload['total'], '25.00')

        update_response = self.client.post(
            reverse('cart_update', args=[self.product.id]),
            {'action': 'dec', 'variant_id': self.variant.id},
        )

        self.assertEqual(update_response.status_code, 200)
        update_payload = update_response.json()
        self.assertEqual(update_payload['count'], 1)
        self.assertEqual(update_payload['total'], '12.50')

    def test_checkout_finalize_requires_items_in_cart(self):
        response = self.client.post(
            reverse('checkout_finalize'),
            {
                'first_name': 'Joao',
                'last_name': 'Silva',
                'whatsapp': '16999999999',
                'payment_method': 'pix',
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('carrinho', response.json()['error'].lower())

    @patch('shop.views._create_mp_pix_payment')
    def test_checkout_finalize_success_creates_order_and_clears_cart(self, create_pix_mock):
        create_pix_mock.return_value = {
            'payment_id': '123456789',
            'external_reference': 'ORDER_1',
            'status': 'pending',
            'status_detail': 'pending_waiting_transfer',
            'pix_code': 'pix-code-copy-paste',
            'qr_base64': 'base64-image',
        }

        self.client.post(
            reverse('cart_add', args=[self.product.id]),
            {'quantity': 2},
        )

        response = self.client.post(
            reverse('checkout_finalize'),
            {
                'first_name': 'Maria',
                'last_name': 'Souza',
                'whatsapp': '16999999999',
                'payment_method': 'pix',
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['order_status'], 'pending')
        self.assertEqual(payload['cart']['count'], 0)

        self.assertEqual(Order.objects.count(), 1)
        order = Order.objects.first()
        self.assertEqual(order.first_name, 'Maria')
        self.assertEqual(order.total, self.product.price * 2)
        self.assertFalse(order.is_paid)
        self.assertEqual(order.mp_payment_id, '123456789')

        session = self.client.session
        self.assertEqual(session.get('cart'), {})
        self.assertEqual(session.get('last_public_print_order_id'), order.id)

    def test_auth_login_success(self):
        response = self.client.post(
            reverse('auth_login'),
            {
                'username': 'admin',
                'password': 'senha-segura',
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['user']['username'], 'admin')

    def test_manage_reports_requires_login(self):
        response = self.client.get(reverse('manage_reports_page'))
        self.assertEqual(response.status_code, 302)

    def test_manage_reports_logged_user_access(self):
        self.client.login(username='admin', password='senha-segura')
        response = self.client.get(reverse('manage_reports_page'))

        self.assertEqual(response.status_code, 200)

    def test_manage_reports_export_pdf_returns_pdf(self):
        Order.objects.create(
            first_name='Cliente',
            last_name='PDF',
            whatsapp='16999990000',
            payment_method=Order.PAYMENT_CASH,
            total=Decimal('20.00'),
            pix_code='',
            items_json=[{'id': self.product.id, 'name': self.product.name, 'price': '20.00', 'quantity': 1, 'subtotal': '20.00'}],
            is_paid=True,
        )
        DonationEntry.objects.create(name='Doacao PDF', amount=Decimal('5.00'))

        self.client.login(username='admin', password='senha-segura')
        response = self.client.get(reverse('manage_reports_export_pdf'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_manage_reports_includes_donations_in_profit(self):
        Order.objects.create(
            first_name='Cliente',
            last_name='Pago',
            whatsapp='16999990000',
            payment_method=Order.PAYMENT_CASH,
            total=Decimal('20.00'),
            pix_code='',
            items_json=[{'id': self.product.id, 'name': self.product.name, 'price': '20.00', 'quantity': 1, 'subtotal': '20.00'}],
            is_paid=True,
        )
        DonationEntry.objects.create(name='Doacao teste', amount=Decimal('5.00'))

        self.client.login(username='admin', password='senha-segura')
        response = self.client.get(reverse('manage_reports_page'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'R$ 5,00')
        self.assertContains(response, 'R$ 25,00')

    def test_manage_donations_create_page_creates_positive_entry(self):
        self.client.login(username='admin', password='senha-segura')
        response = self.client.post(
            reverse('manage_donations_create_page'),
            {'name': 'Oferta especial', 'amount': '12.50', 'return_tab': 'secao-custos'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(DonationEntry.objects.filter(name='Oferta especial', amount=Decimal('12.50')).exists())

    def test_manage_sales_create_order_card_defaults_to_unpaid(self):
        self.client.login(username='admin', password='senha-segura')
        response = self.client.post(
            reverse('manage_sales_create_order'),
            {
                'customer_name': 'Venda Balcao',
                'whatsapp': '16999999999',
                'payment_method': 'card',
                'items_json': f'[{{\"product_id\": {self.product.id}, \"variant_id\": {self.variant.id}, \"quantity\": 2}}]',
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload['is_paid'])
        self.assertEqual(payload['status_label'], 'Aguardando pagamento')

        order = Order.objects.latest('id')
        self.assertEqual(order.payment_method, Order.PAYMENT_CARD)
        self.assertFalse(order.is_paid)
        self.assertEqual(order.mp_status, 'pending')
        self.assertTrue(order.created_by_staff)

    @patch('shop.views._create_mp_pix_payment')
    def test_manage_sales_create_order_pix_returns_qr(self, create_pix_mock):
        create_pix_mock.return_value = {
            'payment_id': '111222333',
            'external_reference': 'ORDER_1',
            'status': 'pending',
            'status_detail': 'pending_waiting_transfer',
            'pix_code': 'pix-code-venda',
            'qr_base64': 'qr-base64',
        }

        self.client.login(username='admin', password='senha-segura')
        response = self.client.post(
            reverse('manage_sales_create_order'),
            {
                'customer_name': 'Venda Pix',
                'whatsapp': '16988887777',
                'payment_method': 'pix',
                'items_json': f'[{{\"product_id\": {self.product.id}, \"variant_id\": {self.variant.id}, \"quantity\": 1}}]',
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('qr_code_base64', payload)
        self.assertFalse(payload['is_paid'])

        order = Order.objects.latest('id')
        self.assertEqual(order.payment_method, Order.PAYMENT_PIX)
        self.assertFalse(order.is_paid)
        self.assertEqual(order.mp_payment_id, '111222333')

    def test_manage_sales_create_order_requires_variant_when_product_has_variants(self):
        self.client.login(username='admin', password='senha-segura')
        response = self.client.post(
            reverse('manage_sales_create_order'),
            {
                'customer_name': 'Sem Variacao',
                'whatsapp': '16977776666',
                'payment_method': 'cash',
                'items_json': f'[{{\"product_id\": {self.product.id}, \"quantity\": 1}}]',
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('Selecione uma variacao', response.json()['error'])

    def test_manage_order_mark_paid_page_marks_order_paid(self):
        order = Order.objects.create(
            first_name='Cliente',
            last_name='Teste',
            whatsapp='16999998888',
            payment_method=Order.PAYMENT_CARD,
            total=Decimal('20.00'),
            pix_code='',
            items_json=[{'id': self.product.id, 'name': self.product.name, 'price': '20.00', 'quantity': 1, 'subtotal': '20.00'}],
            mp_status='pending',
        )

        self.client.login(username='admin', password='senha-segura')
        response = self.client.post(reverse('manage_order_mark_paid_page', args=[order.id]))

        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertTrue(order.is_paid)
        self.assertIsNotNone(order.paid_at)
        self.assertEqual(order.mp_status, 'approved_manual')

    def test_manage_order_delivery_page_marks_order_delivered(self):
        order = Order.objects.create(
            first_name='Cliente',
            last_name='Entrega',
            whatsapp='16999997777',
            payment_method=Order.PAYMENT_PIX,
            total=Decimal('15.00'),
            pix_code='',
            items_json=[{'id': self.product.id, 'name': self.product.name, 'price': '15.00', 'quantity': 1, 'subtotal': '15.00'}],
            mp_status='pending',
        )

        self.client.login(username='admin', password='senha-segura')
        response = self.client.post(
            reverse('manage_order_delivery_page', args=[order.id]),
            {'action': 'mark_delivered'},
        )

        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertTrue(order.is_delivered)
        self.assertIsNotNone(order.delivered_at)
        self.assertEqual(order.items_json[0]['delivered_quantity'], 1)

    def test_manage_order_delivery_page_registers_partial_delivery(self):
        order = Order.objects.create(
            first_name='Cliente',
            last_name='Parcial',
            whatsapp='16999997777',
            payment_method=Order.PAYMENT_PIX,
            total=Decimal('30.00'),
            pix_code='',
            items_json=[{'id': self.product.id, 'name': self.product.name, 'price': '10.00', 'quantity': 5, 'subtotal': '50.00'}],
            mp_status='pending',
        )

        self.client.login(username='admin', password='senha-segura')
        response = self.client.post(
            reverse('manage_order_delivery_page', args=[order.id]),
            {'action': 'mark_partial_delivery', 'deliver_item_0': '3'},
        )

        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertFalse(order.is_delivered)
        self.assertIsNone(order.delivered_at)
        self.assertEqual(order.items_json[0]['delivered_quantity'], 3)
        self.assertEqual(self.client.session.get('print_order_scope'), 'last_delivery')

    def test_manage_order_print_page_shows_only_remaining_items_after_partial_delivery(self):
        order = Order.objects.create(
            first_name='Cliente',
            last_name='Saldo',
            whatsapp='16999997777',
            payment_method=Order.PAYMENT_PIX,
            total=Decimal('30.00'),
            pix_code='',
            items_json=[{'id': self.product.id, 'name': self.product.name, 'price': '10.00', 'quantity': 5, 'delivered_quantity': 3, 'subtotal': '50.00'}],
            mp_status='pending',
        )

        self.client.login(username='admin', password='senha-segura')
        response = self.client.get(
            reverse('manage_order_print_page', args=[order.id]) + '?scope=remaining'
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '2x')
        self.assertNotContains(response, '5x')

    def test_manage_order_mark_paid_page_keeps_current_tab_in_redirect(self):
        order = Order.objects.create(
            first_name='Cliente',
            last_name='Aba',
            whatsapp='16999997777',
            payment_method=Order.PAYMENT_PIX,
            total=Decimal('15.00'),
            pix_code='',
            items_json=[{'id': self.product.id, 'name': self.product.name, 'price': '15.00', 'quantity': 1, 'subtotal': '15.00'}],
            mp_status='pending',
        )

        self.client.login(username='admin', password='senha-segura')
        response = self.client.post(
            reverse('manage_order_mark_paid_page', args=[order.id]),
            {'return_tab': 'secao-pedidos'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn('tab=secao-pedidos', response['Location'])

    def test_manage_orders_mark_all_delivered_requires_password(self):
        order = Order.objects.create(
            first_name='Cliente',
            last_name='Lote',
            whatsapp='16999996666',
            payment_method=Order.PAYMENT_CASH,
            total=Decimal('12.00'),
            pix_code='',
            items_json=[{'id': self.product.id, 'name': self.product.name, 'price': '12.00', 'quantity': 1, 'subtotal': '12.00'}],
            mp_status='pending',
            is_delivered=False,
        )

        self.client.login(username='admin', password='senha-segura')
        wrong = self.client.post(
            reverse('manage_orders_mark_all_delivered_page'),
            {'bulk_delivered_password': '999'},
        )
        self.assertEqual(wrong.status_code, 302)
        order.refresh_from_db()
        self.assertFalse(order.is_delivered)

        ok = self.client.post(
            reverse('manage_orders_mark_all_delivered_page'),
            {'bulk_delivered_password': '123'},
        )
        self.assertEqual(ok.status_code, 302)
        order.refresh_from_db()
        self.assertTrue(order.is_delivered)
        self.assertIsNotNone(order.delivered_at)
        self.assertEqual(order.items_json[0]['delivered_quantity'], 1)

    @patch('shop.views._wapi_send_text')
    def test_manage_order_notify_ready_page_sends_whatsapp(self, send_text_mock):
        order = Order.objects.create(
            first_name='Cliente',
            last_name='Pronto',
            whatsapp='16999995555',
            payment_method=Order.PAYMENT_CASH,
            total=Decimal('25.00'),
            pix_code='',
            items_json=[{'id': self.product.id, 'name': self.product.name, 'price': '25.00', 'quantity': 1, 'subtotal': '25.00'}],
            mp_status='pending',
        )

        self.client.login(username='admin', password='senha-segura')
        response = self.client.post(reverse('manage_order_notify_ready_page', args=[order.id]))

        self.assertEqual(response.status_code, 302)
        send_text_mock.assert_called_once()
        args, _ = send_text_mock.call_args
        self.assertEqual(args[0], '5516999995555')
        self.assertIn(f'#{order.id}', args[1])
