import json
import os

from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from .payments import (
    process_solana_payment,
    process_ton_payment,
    verify_solana_transaction,
    verify_ton_transaction,
)
from .idia_contract_service import IdiaContractService
from .jetton_wallet_service import JettonWalletService
from .models import Payment, Product
from .serializers import PaymentSerializer, ProductSerializer


def _build_ton_client():
    try:
        from tonclient.client import TonClient
    except Exception:
        return None

    endpoint = os.getenv(
        "TONCENTER_RPC_URL",
        "https://toncenter.com/api/v2/jsonRPC")
    return TonClient(config={"network": {"server_address": endpoint}})


_ton_client = _build_ton_client()
idia_service = IdiaContractService(_ton_client) if _ton_client else None
wallet_service = JettonWalletService(_ton_client) if _ton_client else None


def health_check(_request):
    return JsonResponse({"status": "ok", "service": "store"})


def products(request):
    data = ProductSerializer(
        Product.objects.all().order_by("id"),
        many=True).data
    return JsonResponse(data, safe=False)


@api_view(["GET", "POST"])
@permission_classes([IsAdminUser])
def admin_products(request):
    if request.method == "GET":
        queryset = Product.objects.all().order_by("id")
        return Response(ProductSerializer(queryset, many=True).data)

    serializer = ProductSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data, status=201)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsAdminUser])
def admin_product_detail(request, product_id: int):
    product = get_object_or_404(Product, pk=product_id)

    if request.method == "GET":
        return Response(ProductSerializer(product).data)

    if request.method in ["PUT", "PATCH"]:
        serializer = ProductSerializer(
            product,
            data=request.data,
            partial=request.method == "PATCH")
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    product.delete()
    return Response(status=204)


@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_payment_logs(request):
    queryset = Payment.objects.select_related(
        "product").all().order_by("-created_at")
    return Response(PaymentSerializer(queryset, many=True).data)


@csrf_exempt
def _process_chain_payment(request, chain: str):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST is supported."}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    chain = str(chain).lower()
    if chain not in ["ton", "solana"]:
        return JsonResponse(
            {"error": "Unsupported chain. Use 'solana' or 'ton'."}, status=400)

    wallet = payload.get("wallet")
    amount = payload.get("amount")
    proof = payload.get("proof", {})
    product_id = payload.get("product_id")

    if product_id is None:
        cart = payload.get("cart", [])
        if isinstance(cart, list) and cart:
            product_id = cart[0].get("id")

    if product_id is None:
        return JsonResponse(
            {"error": "product_id is required (or include cart with product id)."},
            status=400,
        )

    try:
        product = Product.objects.get(pk=product_id)
    except Product.DoesNotExist:
        return JsonResponse({"error": "Product not found."}, status=404)

    if not wallet or amount is None:
        return JsonResponse(
            {"error": "wallet and amount are required."}, status=400)

    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return JsonResponse({"error": "amount must be numeric."}, status=400)

    if amount < float(product.price):
        return JsonResponse(
            {"error": f"Insufficient payment amount. Product '{product.name}' costs {product.price}."},
            status=400,
        )

    chain_label = "TON" if chain == "ton" else "Solana"
    if chain == "solana":
        tx_hash_value = str(proof.get("signature", ""))
        if not tx_hash_value:
            return JsonResponse(
                {"error": "proof.signature is required for Solana payments."},
                status=400,
            )
    else:
        tx_hash_value = str(proof.get("tx_hash", ""))
        if not tx_hash_value:
            return JsonResponse(
                {"error": "proof.tx_hash is required for TON payments."}, status=400
            )

    payment = Payment.objects.create(
        product=product,
        tx_hash=tx_hash_value,
        blockchain=chain_label,
        status="pending",
    )

    try:
        if chain == "solana":
            tx = process_solana_payment(wallet, amount, tx_hash_value)
        else:
            tx = process_ton_payment(wallet, amount, tx_hash_value)
        payment.tx_hash = tx_hash_value
    except Exception as exc:
        payment.save(update_fields=["tx_hash", "status"])
        return JsonResponse({"error": str(exc)}, status=502)

    payment.status = "confirmed"
    payment.save(update_fields=["tx_hash", "status"])

    return JsonResponse(
        {"status": "verified", "chain": chain, "payment_id": payment.id, "tx": tx}
    )


@csrf_exempt
def process_payment(request):
    chain = str(request.GET.get("chain", "")).lower()
    if not chain:
        try:
            payload = json.loads(request.body.decode("utf-8"))
            chain = str(payload.get("chain", "")).lower()
        except (json.JSONDecodeError, UnicodeDecodeError):
            chain = ""

    if chain not in ["ton", "solana"]:
        return JsonResponse(
            {"error": "Unsupported chain. Use 'solana' or 'ton'."}, status=400)

    return _process_chain_payment(request, chain)


@csrf_exempt
def pay_ton(request):
    return _process_chain_payment(request, "ton")


@csrf_exempt
def pay_solana(request):
    return _process_chain_payment(request, "solana")

@csrf_exempt
def token_info(request):
    if idia_service is None:
        return JsonResponse(
            {"error": "TON client is not configured."}, status=503)

    try:
        return JsonResponse(idia_service.get_token_info())
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=502)


def idia_balance(request, address: str):
    if wallet_service is None:
        return JsonResponse(
            {"error": "TON client is not configured."}, status=503)

    try:
        balance = wallet_service.get_balance(address)
        return JsonResponse({"balance": balance})
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=502)


@csrf_exempt
def transfer_idia(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST is supported."}, status=405)

    if wallet_service is None:
        return JsonResponse(
            {"error": "TON client is not configured."}, status=503)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    destination = data.get("to_address")
    amount = data.get("amount")
    forward_ton = data.get("forward_ton", 10000000)
    response_address = data.get("response_address")
    if not destination or amount is None:
        return JsonResponse(
            {"error": "to_address and amount are required."}, status=400
        )

    try:
        msg = wallet_service.build_transfer_message(
            str(destination),
            int(amount),
            int(forward_ton),
            str(response_address) if response_address else None,
        )
    except (TypeError, ValueError):
        return JsonResponse(
            {"error": "amount and forward_ton must be integers."}, status=400)
    except RuntimeError as exc:
        return JsonResponse({"error": str(exc)}, status=503)

    return JsonResponse({"transfer_message": msg})


def estimate_gas(_request):
    return JsonResponse({"estimated_fee": "0.05 TON"})


def verify_contract(_request):
    if idia_service is None:
        return JsonResponse(
            {"valid": False, "error": "TON client is not configured."}, status=503)

    try:
        info = idia_service.get_token_info()
        return JsonResponse({"valid": info is not None})
    except Exception as exc:
        return JsonResponse({"valid": False, "error": str(exc)}, status=502)
