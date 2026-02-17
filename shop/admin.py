from django.contrib import admin

from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'cause', 'price', 'active')
    list_filter = ('cause', 'active')
    search_fields = ('name', 'description', 'cause')
