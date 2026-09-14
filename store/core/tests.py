import base64
import json
import os
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase

from .models import Payment, Product


class HealthCheckTests(TestCase):
    def test_health_endpoint(self) -> None:
        client = Client()
        response = client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["service"], "store")


class ProductApiContractTests(TestCase):
    def test_products_endpoint_returns_catalog_fields(self) -> None:
        Product.objects.create(
            name="Bronze Pendant",
            description="Replica",
            price="25.00",
            stock=10,
            image="https://example.com/bronze.jpg",
            category="jewelry",
        )

        client = Client()
        response = client.get("/api/products/")
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["name"], "Bronze Pendant")
        self.assertEqual(payload[0]["category"], "jewelry")
        self.assertEqual(payload[0]["image"], "https://example.com/bronze.jpg")


class PaymentValidationTests(TestCase):
    def setUp(self) -> None:
        self.product = Product.objects.create(
            name="Test Product",
            description="Test",
            price="10.00",
            stock=5,
        )

    def test_payment_rejects_unsupported_chain(self) -> None:
        client = Client()
        response = client.post(
            "/payments/process/",
            data={
                "chain": "bitcoin",
                "wallet": "abc",
                "amount": 1,
                "product_id": self.product.id},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_solana_chain_is_rejected(self) -> None:
        client = Client()
        response = client.post(
            "/payments/process/",
            data={
                "chain": "solana",
                "wallet": "abc",
                "amount": 1,
                "product_id": self.product.id,
                "proof": {},
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("TON only", response.json()["error"])

    def test_ton_requires_tx_hash_proof(self) -> None:
        client = Client()
        response = client.post(
            "/payments/process/",
            data={
                "chain": "ton",
                "wallet": "abc",
                "amount": 1,
                "product_id": self.product.id,
                "proof": {}},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)


class AdminApiTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.user_model = get_user_model()
        self.admin = self.user_model.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="strong-pass-123",
        )

    def _admin_headers(self) -> dict[str, str]:
        token_response = self.client.post(
            "/api/admin/auth/token/",
            data={"username": "admin", "password": "strong-pass-123"},
            content_type="application/json",
        )
        self.assertEqual(token_response.status_code, 200)
        access = token_response.json()["access"]
        return {"HTTP_AUTHORIZATION": f"Bearer {access}"}

    def _login_admin(self) -> None:
        self.client.force_login(self.admin)

    def test_admin_products_requires_authentication(self) -> None:
        # 401, not 403: with JWTAuthentication registered, DRF returns
        # "unauthenticated" (plus a WWW-Authenticate header) when no
        # credentials are supplied at all.
        response = self.client.get("/api/admin/products/")
        self.assertEqual(response.status_code, 401)

    def test_admin_can_create_and_update_product(self) -> None:
        self._login_admin()

        create_response = self.client.post(
            "/api/admin/products/",
            data={
                "name": "Palm Oil",
                "description": "Freshly sourced",
                "price": "23.50",
                "stock": 22,
                "image": "https://example.com/palm-oil.jpg",
                "category": "food",
            },
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.json()["category"], "food")
        product_id = create_response.json()["id"]

        patch_response = self.client.patch(
            f"/api/admin/products/{product_id}/",
            data={"stock": 18},
            content_type="application/json",
        )
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(patch_response.json()["stock"], 18)

    def test_admin_rejects_invalid_category(self) -> None:
        self._login_admin()
        response = self.client.post(
            "/api/admin/products/",
            data={
                "name": "Invalid Category Product",
                "description": "Bad category",
                "price": "10.00",
                "stock": 1,
                "category": "invalid",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("category", response.json())

    def test_admin_can_view_payment_logs(self) -> None:
        self._login_admin()
        product = Product.objects.create(
            name="Shea Butter",
            description="Raw",
            price="12.00",
            stock=8)
        Payment.objects.create(
            product=product,
            tx_hash="abc123",
            blockchain="TON",
            status="confirmed")

        response = self.client.get("/api/admin/payments/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)


class DedicatedPaymentEndpointTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.product = Product.objects.create(
            name="Cocoa",
            description="Premium",
            price="9.50",
            stock=12,
        )

    def test_pay_ton_requires_tx_hash_proof(self) -> None:
        response = self.client.post(
            "/api/pay/ton",
            data={
                "wallet": "ton-wallet-1",
                "amount": "9.50",
                "product_id": self.product.id,
                "proof": {},
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("proof.tx_hash", response.json()["error"])

    def test_pay_solana_route_is_gone(self) -> None:
        response = self.client.post(
            "/api/pay/solana",
            data={
                "wallet": "sol-wallet-1",
                "amount": "9.50",
                "product_id": self.product.id,
                "proof": {},
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_pay_ton_rejects_insufficient_amount(self) -> None:
        response = self.client.post(
            "/api/pay/ton",
            data={
                "wallet": "ton-wallet-1",
                "amount": "2.00",
                "product_id": self.product.id,
                "proof": {"tx_hash": "ton-low-amount"},
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Insufficient payment amount", response.json()["error"])


class AdminJwtAuthTests(TestCase):
    """
    The admin API is reached with a Bearer token in production. The other admin
    tests use force_login (session auth), which cannot catch DRF being
    misconfigured to ignore the Authorization header - so assert the token path
    explicitly.
    """

    def setUp(self) -> None:
        self.client = Client()
        self.user_model = get_user_model()
        self.admin = self.user_model.objects.create_superuser(
            username="jwtadmin@example.com",
            email="jwtadmin@example.com",
            password="jwt-admin-pass-123",
        )

    def _token(self, username: str, password: str):
        return self.client.post(
            "/api/admin/auth/token/",
            data={"username": username, "password": password},
            content_type="application/json",
        )

    def test_admin_api_rejects_request_without_token(self) -> None:
        response = self.client.get("/api/admin/products/")
        self.assertIn(response.status_code, (401, 403))

    def test_bearer_token_grants_access_to_admin_api(self) -> None:
        token_response = self._token("jwtadmin@example.com", "jwt-admin-pass-123")
        self.assertEqual(token_response.status_code, 200)
        access = token_response.json()["access"]

        response = self.client.get(
            "/api/admin/products/",
            HTTP_AUTHORIZATION=f"Bearer {access}",
        )
        self.assertEqual(response.status_code, 200)

    def test_token_carries_staff_claim(self) -> None:
        payload = self._token("jwtadmin@example.com", "jwt-admin-pass-123").json()
        claims = json.loads(
            base64.urlsafe_b64decode(payload["access"].split(".")[1] + "==")
        )
        self.assertTrue(claims["is_staff"])
        self.assertEqual(claims["username"], "jwtadmin@example.com")

    def test_wrong_password_is_rejected(self) -> None:
        self.assertEqual(self._token("jwtadmin@example.com", "nope").status_code, 401)

    def test_non_staff_user_cannot_obtain_admin_token(self) -> None:
        self.user_model.objects.create_user(
            username="shopper", password="shopper-pass-123"
        )
        response = self._token("shopper", "shopper-pass-123")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Only admin users can log in.", str(response.json()))

    def test_public_endpoints_stay_open(self) -> None:
        self.assertEqual(self.client.get("/api/products/").status_code, 200)
        self.assertEqual(self.client.get("/health/").status_code, 200)


class CreateAdminCommandTests(TestCase):
    def setUp(self) -> None:
        self.user_model = get_user_model()

    def test_creates_admin_from_environment(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"ADMIN_EMAIL": "boss@ekioba.com", "ADMIN_PASSWORD": "first-pass-123"},
        ):
            call_command("createadmin", stdout=StringIO())

        user = self.user_model.objects.get(username="boss@ekioba.com")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_active)
        self.assertEqual(user.email, "boss@ekioba.com")
        self.assertTrue(user.check_password("first-pass-123"))

    def test_is_idempotent_and_resyncs_a_rotated_password(self) -> None:
        env = {"ADMIN_EMAIL": "boss@ekioba.com", "ADMIN_PASSWORD": "first-pass-123"}
        with mock.patch.dict(os.environ, env):
            call_command("createadmin", stdout=StringIO())
        with mock.patch.dict(
            os.environ, {**env, "ADMIN_PASSWORD": "rotated-pass-456"}
        ):
            call_command("createadmin", stdout=StringIO())

        self.assertEqual(
            self.user_model.objects.filter(username="boss@ekioba.com").count(), 1
        )
        user = self.user_model.objects.get(username="boss@ekioba.com")
        self.assertTrue(user.check_password("rotated-pass-456"))

    def test_skip_password_update_leaves_password_alone(self) -> None:
        env = {"ADMIN_EMAIL": "boss@ekioba.com", "ADMIN_PASSWORD": "first-pass-123"}
        with mock.patch.dict(os.environ, env):
            call_command("createadmin", stdout=StringIO())
        with mock.patch.dict(
            os.environ, {**env, "ADMIN_PASSWORD": "rotated-pass-456"}
        ):
            call_command("createadmin", "--skip-password-update", stdout=StringIO())

        user = self.user_model.objects.get(username="boss@ekioba.com")
        self.assertTrue(user.check_password("first-pass-123"))

    def test_promotes_an_existing_non_staff_user(self) -> None:
        self.user_model.objects.create_user(
            username="boss@ekioba.com", password="old-pass-123"
        )
        with mock.patch.dict(
            os.environ,
            {"ADMIN_EMAIL": "boss@ekioba.com", "ADMIN_PASSWORD": "new-pass-123"},
        ):
            call_command("createadmin", stdout=StringIO())

        user = self.user_model.objects.get(username="boss@ekioba.com")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_refuses_without_a_password(self) -> None:
        with mock.patch.dict(
            os.environ, {"ADMIN_EMAIL": "boss@ekioba.com", "ADMIN_PASSWORD": ""}
        ):
            with self.assertRaises(CommandError):
                call_command("createadmin", stdout=StringIO())
        self.assertFalse(self.user_model.objects.filter(username="boss@ekioba.com").exists())

    def test_falls_back_to_django_superuser_variables(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "ADMIN_EMAIL": "",
                "ADMIN_PASSWORD": "",
                "DJANGO_SUPERUSER_USERNAME": "legacyadmin",
                "DJANGO_SUPERUSER_PASSWORD": "legacy-pass-123",
                "DJANGO_SUPERUSER_EMAIL": "legacy@ekioba.com",
            },
        ):
            call_command("createadmin", stdout=StringIO())

        user = self.user_model.objects.get(username="legacyadmin")
        self.assertTrue(user.is_staff)
        self.assertEqual(user.email, "legacy@ekioba.com")


class IdiaEndpointTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()

    def test_token_info_returns_503_without_ton_client(self) -> None:
        response = self.client.get("/api/idia/token-info/")
        self.assertEqual(response.status_code, 503)
        self.assertIn("error", response.json())

    def test_idia_balance_returns_503_without_ton_client(self) -> None:
        response = self.client.get("/api/idia/balance/wallet123/")
        self.assertEqual(response.status_code, 503)
        self.assertIn("error", response.json())

    def test_transfer_idia_returns_503_without_ton_client(self) -> None:
        response = self.client.post(
            "/api/idia/transfer/",
            data={"to_address": "wallet_dest", "amount": 200},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 503)
        self.assertIn("error", response.json())
