from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('auth/login/', views.auth_login, name='auth_login'),
    path('auth/logout/', views.auth_logout, name='auth_logout'),
    path('manage/products/page/', views.manage_products_page, name='manage_products_page'),
    path('manage/products/page/save/', views.manage_products_save_page, name='manage_products_save_page'),
    path('manage/products/page/delete/<int:product_id>/', views.manage_products_delete_page, name='manage_products_delete_page'),
    path('manage/orders/page/payment/<int:order_id>/', views.manage_order_payment_page, name='manage_order_payment_page'),
    path('manage/products/', views.product_manage_list, name='product_manage_list'),
    path('manage/products/save/', views.product_manage_save, name='product_manage_save'),
    path('manage/products/delete/<int:product_id>/', views.product_manage_delete, name='product_manage_delete'),
    path('cart/add/<int:product_id>/', views.cart_add, name='cart_add'),
    path('cart/update/<int:product_id>/', views.cart_update, name='cart_update'),
    path('checkout/finalize/', views.checkout_finalize, name='checkout_finalize'),
]
