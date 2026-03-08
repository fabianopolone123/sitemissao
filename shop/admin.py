from django.contrib import admin

from .models import DonationEntry, Order, Product, ProductVariant, ProfitDistributionConfig, ProfitDistributionPerson


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'cause', 'price', 'active', 'created_at')
    list_filter = ('cause', 'active')
    search_fields = ('name', 'description', 'cause')
    inlines = [ProductVariantInline]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'first_name', 'last_name', 'payment_method', 'total', 'created_at')
    list_filter = ('payment_method', 'created_at')
    search_fields = ('first_name', 'last_name', 'whatsapp')
    readonly_fields = ('pix_code', 'items_json', 'created_at')


@admin.register(DonationEntry)
class DonationEntryAdmin(admin.ModelAdmin):
    list_display = ('name', 'amount', 'created_at')
    search_fields = ('name',)


@admin.register(ProfitDistributionConfig)
class ProfitDistributionConfigAdmin(admin.ModelAdmin):
    list_display = ('base_amount', 'updated_at')


@admin.register(ProfitDistributionPerson)
class ProfitDistributionPersonAdmin(admin.ModelAdmin):
    list_display = ('name', 'amount', 'updated_at')
    search_fields = ('name',)
