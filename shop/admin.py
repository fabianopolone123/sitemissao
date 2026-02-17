from django.contrib import admin

from .models import Order, Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'cause', 'price', 'active', 'created_at')
    list_filter = ('cause', 'active')
    search_fields = ('name', 'description', 'cause')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'first_name', 'last_name', 'payment_method', 'total', 'created_at')
    list_filter = ('payment_method', 'created_at')
    search_fields = ('first_name', 'last_name', 'whatsapp')
    readonly_fields = ('pix_code', 'items_json', 'created_at')
