from django.db import models


class Product(models.Model):
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=255, blank=True)
    cause = models.CharField(max_length=80, default='Missoes')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image_url = models.URLField()
    image_file = models.ImageField(upload_to='products/', blank=True, null=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return self.name

    @property
    def image_source(self) -> str:
        if self.image_file:
            return self.image_file.url
        return self.image_url


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    name = models.CharField(max_length=120)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return f'{self.product.name} - {self.name}'


class Order(models.Model):
    PAYMENT_PIX = 'pix'
    PAYMENT_CARD = 'card'
    PAYMENT_CASH = 'cash'
    PAYMENT_CHOICES = [
        (PAYMENT_PIX, 'Pix'),
        (PAYMENT_CARD, 'Cartao'),
        (PAYMENT_CASH, 'Dinheiro'),
    ]

    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    whatsapp = models.CharField(max_length=25)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    pix_code = models.TextField()
    mp_payment_id = models.CharField(max_length=40, blank=True)
    mp_external_reference = models.CharField(max_length=80, blank=True)
    mp_status = models.CharField(max_length=40, blank=True)
    mp_status_detail = models.CharField(max_length=120, blank=True)
    items_json = models.JSONField(default=list)
    is_paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(blank=True, null=True)
    is_delivered = models.BooleanField(default=False)
    delivered_at = models.DateTimeField(blank=True, null=True)
    whatsapp_notified = models.BooleanField(default=False)
    whatsapp_notified_at = models.DateTimeField(blank=True, null=True)
    whatsapp_notify_error = models.CharField(max_length=255, blank=True)
    created_by_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'Pedido #{self.id} - {self.first_name} {self.last_name}'


class WhatsAppRecipient(models.Model):
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20, unique=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return f'{self.name} ({self.phone})'
