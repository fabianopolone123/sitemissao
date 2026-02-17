from django.db import models


class Product(models.Model):
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=255, blank=True)
    cause = models.CharField(max_length=80, default='Missoes')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image_url = models.URLField()
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class Order(models.Model):
    PAYMENT_PIX = 'pix'
    PAYMENT_CHOICES = [
        (PAYMENT_PIX, 'Pix'),
    ]

    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    whatsapp = models.CharField(max_length=25)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    pix_code = models.TextField()
    items_json = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'Pedido #{self.id} - {self.first_name} {self.last_name}'
