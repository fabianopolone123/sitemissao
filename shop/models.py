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
