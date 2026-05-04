from django.contrib import admin
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from core.auth import AdminTokenObtainPairView
from core import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", views.health_check, name="health"),
    path("health", views.health_check, name="health_no_slash"),
    path("api/products/", views.products, name="products"),
    path("api/products", views.products, name="products_no_slash"),
    path("api/pay/ton", views.pay_ton),
    path("api/pay/ton/", views.pay_ton),
    path("api/pay/solana", views.pay_solana),
    path("api/pay/solana/", views.pay_solana),
    path(
        "api/admin/auth/token/",
        AdminTokenObtainPairView.as_view(),
        name="token_obtain_pair"),
    path(
        "api/admin/auth/token/refresh/",
        TokenRefreshView.as_view(),
        name="token_refresh"),
    path("api/admin/products/", views.admin_products, name="admin_products"),
    path(
        "api/admin/products/<int:product_id>/",
        views.admin_product_detail,
        name="admin_product_detail"),
    path(
        "api/admin/payments/",
        views.admin_payment_logs,
        name="admin_payment_logs"),
    path("api/idia/token-info/", views.token_info, name="token_info"),
    path("api/idia/token-info", views.token_info, name="token_info_no_slash"),
    path(
        "api/idia/balance/<str:address>/",
        views.idia_balance,
        name="idia_balance"),
    path(
        "api/idia/balance/<str:address>",
        views.idia_balance,
        name="idia_balance_no_slash"),
    path("api/idia/transfer/", views.transfer_idia, name="transfer_idia"),
    path("api/idia/transfer", views.transfer_idia, name="transfer_idia_no_slash"),
    path("api/idia/estimate-gas/", views.estimate_gas, name="estimate_gas"),
    path("api/idia/estimate-gas", views.estimate_gas, name="estimate_gas_no_slash"),
    path(
        "api/idia/verify-contract/",
        views.verify_contract,
        name="verify_contract"),
    path(
        "api/idia/verify-contract",
        views.verify_contract,
        name="verify_contract_no_slash"),
    path("payments/process/", views.process_payment, name="process_payment"),
    path("payments/process", views.process_payment, name="process_payment_no_slash"),
]
