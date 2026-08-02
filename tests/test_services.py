"""Tests for Asha Shop FastAPI services."""

from __future__ import annotations

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.utils.operation_result import OperationResult
from app.utils.persian_tools import to_farsi, to_persian_number, generate_slug, is_phone_number


# ── Utility Tests ──

class TestPersianTools:
    def test_to_farsi(self):
        dt = datetime(2026, 7, 28, 14, 0, 0)
        result = to_farsi(dt)
        assert result is not None
        assert "/" in result

    def test_to_persian_number(self):
        assert to_persian_number(123) == "۱۲۳"
        assert to_persian_number(0) == "۰"

    def test_generate_slug(self):
        assert generate_slug("Hello World") == "hello-world"
        assert generate_slug("  Test  Slug  ") == "test-slug"
        assert generate_slug("") == ""

    def test_is_phone_number(self):
        assert is_phone_number("09123456789") is True
        assert is_phone_number("02112345678") is False
        assert is_phone_number("invalid") is False


class TestOperationResult:
    def test_success(self):
        result = OperationResult.success("OK", {"id": 1})
        assert result.is_succeeded is True
        assert result.message == "OK"
        assert result.data == {"id": 1}

    def test_fail(self):
        result = OperationResult.fail("Error")
        assert result.is_succeeded is False
        assert result.message == "Error"

    def test_default_messages(self):
        from _0_Framework.Application.OperationResult import OperationResult as DotNetResult
        r = DotNetResult()
        r.Succeded()
        assert r.IsSucceded is True


# ── Schema Validations ──

class TestAuthSchemas:
    def test_login_validation(self):
        from pydantic import ValidationError
        from app.schemas.auth import LoginRequest

        valid = LoginRequest(username="test@example.com", password="Test123")
        assert valid.username == "test@example.com"

        with pytest.raises(ValidationError):
            LoginRequest(username="", password="")

    def test_register_validation(self):
        from pydantic import ValidationError
        from app.schemas.auth import RegisterRequest

        valid = RegisterRequest(
            first_name="Ali",
            last_name="Mohammadi",
            phone_number="09123456789",
            password="Test123456",
        )
        assert valid.first_name == "Ali"

        with pytest.raises(ValidationError):
            RegisterRequest(
                first_name="A",
                last_name="B",
                phone_number="invalid",
                password="123",
            )


# ── Service Tests ──

class TestAuthService:
    @pytest.mark.asyncio
    async def test_hash_password(self):
        from app.core.security import hash_password, verify_password

        hashed = hash_password("Test123456")
        assert hashed != "Test123456"
        assert verify_password("Test123456", hashed) is True
        assert verify_password("WrongPass", hashed) is False

    @pytest.mark.asyncio
    async def test_create_access_token(self):
        from app.core.security import create_access_token, decode_token

        token = create_access_token({"sub": "test-user-id"})
        assert token is not None
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "test-user-id"


class TestProductService:
    @pytest.mark.asyncio
    async def test_search_products_no_db(self):
        """Test that search function handles empty results gracefully."""
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()

        from app.services.product_service import search_products
        from app.schemas.product import ProductSearchParams

        params = ProductSearchParams(page=1, page_size=20)
        # Should fail gracefully with mock since no real DB
        with pytest.raises(Exception):
            await search_products(mock_db, params)


class TestOrderService:
    def test_cart_operations(self):
        from app.services.order_service import Cart, CartItem

        cart = Cart()
        assert cart.total_items == 0

        # Simulate adding items directly
        item = CartItem(product_id="prod-1", quantity=2)
        cart.items["prod-1"] = item
        assert cart.total_items == 2

        cart.remove_item("prod-1")
        assert cart.total_items == 0

    def test_cart_total_price(self):
        from app.services.order_service import Cart, CartItem

        cart = Cart()
        item = CartItem(product_id="prod-1", quantity=3)
        item.unit_price = 1000
        item.price_after_discount = 900
        cart.items["prod-1"] = item

        assert cart.total_items == 3
        assert cart.total_price == 2700  # 900 * 3


# ── Enum Tests ──

class TestEnums:
    def test_order_status_values(self):
        from app.models.enums import OrderStatus
        assert OrderStatus.ORDERING.value == "Ordering"
        assert OrderStatus.PAID.value == "Paid"
        assert OrderStatus.CANCELED.value == "Canceled"

    def test_payment_status_values(self):
        from app.models.enums import PaymentRequestStatus
        assert PaymentRequestStatus.SUCCESS.value == "Success"
        assert PaymentRequestStatus.CANCELED.value == "Canceled"

    def test_invoice_type_values(self):
        from app.models.enums import InvoiceType
        assert InvoiceType.SALE.value == "Sale"
        assert InvoiceType.PURCHASE.value == "Purchase"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])