from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('cart/add/<int:product_id>/', views.cart_add, name='cart_add'),
    path('cart/update/<int:product_id>/', views.cart_update, name='cart_update'),
    path('checkout/finalize/', views.checkout_finalize, name='checkout_finalize'),
]
