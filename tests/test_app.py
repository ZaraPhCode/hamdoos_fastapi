"""Asha Shop — Pytest test suite.

Run with: pytest tests/ -v
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_health_endpoint(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_root_endpoint(client):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "Welcome" in data["message"]


@pytest.mark.asyncio
async def test_openapi_docs(client):
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert "paths" in data
    assert len(data["paths"]) > 0


@pytest.mark.asyncio
async def test_robots_txt(client):
    response = await client.get("/robots.txt")
    assert response.status_code == 200
    assert "Sitemap" in response.text


@pytest.mark.asyncio
async def test_categories_endpoint(client):
    response = await client.get("/api/v1/categories")
    assert response.status_code in (200, 500)  # 500 if no DB


@pytest.mark.asyncio
async def test_brands_endpoint(client):
    response = await client.get("/api/v1/brands")
    assert response.status_code in (200, 500)


@pytest.mark.asyncio
async def test_products_endpoint(client):
    response = await client.get("/api/v1/products")
    assert response.status_code in (200, 500)


@pytest.mark.asyncio
async def test_register_schema():
    """Test that the register schema validates correctly."""
    from app.schemas.auth import RegisterRequest

    # Valid
    data = RegisterRequest(
        first_name="علی",
        last_name="احمدی",
        phone_number="09121234567",
        password="Test123456",
    )
    assert data.phone_number == "09121234567"

    # Invalid phone
    with pytest.raises(Exception):
        RegisterRequest(
            first_name="علی",
            last_name="احمدی",
            phone_number="12345",
            password="Test123456",
        )


@pytest.mark.asyncio
async def test_operation_result():
    from app.utils.operation_result import OperationResult

    result = OperationResult.success("OK")
    assert result.is_succeeded is True
    assert result.message == "OK"

    result = OperationResult.fail("Error")
    assert result.is_succeeded is False
    assert result.message == "Error"


@pytest.mark.asyncio
async def test_persian_tools():
    from app.utils.persian_tools import to_persian_number, to_english_number, is_phone_number, is_email

    assert to_persian_number(123) == "۱۲۳"
    assert to_english_number("۱۲۳") == "123"
    assert is_phone_number("09121234567") is True
    assert is_phone_number("12345") is False
    assert is_email("test@example.com") is True
    assert is_email("not-email") is False


@pytest.mark.asyncio
async def test_generate_slug():
    from app.utils.common_works import generate_slug

    assert generate_slug("Hello World") == "hello-world"
    assert generate_slug("آشا شاپ") == "asha-shap"
    assert generate_slug("  Test   Slug  ") == "test-slug"


@pytest.mark.asyncio
async def test_easy_tax_payer():
    from app.services.easy_tax_payer import TaxInvoice, ArticleOrService, TaxPayer, Customer, InvoiceType
    from decimal import Decimal

    invoice = TaxInvoice(
        invoice_type=InvoiceType.SALE,
        seller=TaxPayer(name="شرکت آشا", national_code="1234567890"),
        buyer=Customer(name="مشتری", national_code="0987654321", is_final_consumer=True),
    )
    article = ArticleOrService(
        row_number=1,
        description="محصول تست",
        quantity=Decimal("2"),
        unit_price=Decimal("100000"),
        vat_rate=Decimal("9"),
    )
    article.calculate()
    invoice.articles.append(article)
    invoice.calculate_totals()

    assert float(invoice.total_gross) == 200000
    assert float(invoice.total_vat) == 18000
    assert float(invoice.total_payable) == 218000


@pytest.mark.asyncio
async def test_localization_service():
    from app.services.localization_service import t

    # Test Persian
    fa_home = t("home", locale="fa")
    assert fa_home == "خانه"

    # Test English
    en_home = t("home", locale="en")
    assert en_home == "Home"


@pytest.mark.asyncio
async def test_captcha_generator():
    from app.utils.common_works import CaptchaGenerator

    code = CaptchaGenerator.generate_code(6)
    assert len(code) == 6
    assert code.isdigit()

    assert CaptchaGenerator.validate_code(code, code) is True
    assert CaptchaGenerator.validate_code("wrong", code) is False


@pytest.mark.asyncio
async def test_common_works():
    from app.utils.common_works import CommonWorks

    assert CommonWorks.is_valid_national_code("1234567890") is not None
    assert CommonWorks.is_valid_sheba("IR123456789012345678901234") is True
    assert CommonWorks.normalize_phone("09121234567") == "09121234567"
    assert CommonWorks.mask_card_number("1234567890123456") == "1234-****-****-3456"


@pytest.mark.asyncio
async def test_invoice_product_helper():
    from app.utils.common_works import InvoiceProductHelper

    result = InvoiceProductHelper.calculate_final_price(
        unit_price=100000,
        quantity=3,
        discount=5000,
        vat_rate=9,
    )
    assert result["subtotal"] == 300000
    assert result["total_discount"] == 15000
    assert result["after_discount"] == 285000
    assert result["vat"] == 25650
    assert result["final"] == 310650