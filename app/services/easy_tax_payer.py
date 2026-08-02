"""EasyTaxPayer — Iranian tax invoice library.

Mirrors the EasyTaxPayer/ project from the .NET solution.
Handles Iranian National Tax Administration (Sazman-e Maliat) invoice format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional


# ── Enums ──

class InvoiceType(str, Enum):
    """نوع صورتحساب"""
    SALE = "1"               # فروش
    CONTRACT = "2"           # قرارداد
    ADVANCE = "3"            # پیش‌فاکتور
    PROFORMA = "4"           # پیش‌نویس
    RETURN_SALE = "5"        # برگشت از فروش
    RETURN_BUY = "6"         # برگشت از خرید
    ADJUSTMENT = "7"         # تعدیل


class Pattern(str, Enum):
    """الگوی صورتحساب"""
    NORMAL = "1"             # عادی
    AGENCY = "2"             # نمایندگی
    MINI = "3"               # مختصر
    CONTRACTOR = "4"         # پیمانکاری


class Subject(str, Enum):
    """موضوع صورتحساب"""
    GOODS = "1"              # کالا
    SERVICES = "2"           # خدمات
    GOODS_AND_SERVICES = "3" # کالا و خدمات


class SettlementMethod(str, Enum):
    """روش تسویه"""
    CASH = "1"               # نقدی
    CREDIT = "2"             # نسیه
    INSTALLMENT = "3"        # اقساط
    CHEQUE = "4"             # چک
    CARD = "5"               # کارت خوان


class InvoiceStatus(str, Enum):
    DRAFT = "Draft"
    CONFIRMED = "Confirmed"
    SENT = "Sent"
    CANCELED = "Canceled"


# ── Models ──

@dataclass
class TaxPayer:
    """فروشنده / خریدار (شخص حقیقی/حقوقی)"""
    name: str = ""
    national_code: str = ""          # کد ملی / شناسه ملی
    economic_code: str = ""          # کد اقتصادی
    registration_number: str = ""    # شماره ثبت
    postal_code: str = ""
    address: str = ""
    phone_number: str = ""
    identity_type: str = "Real"      # Real=حقیقی, Legal=حقوقی

    def validate(self) -> list[str]:
        errors = []
        if not self.national_code:
            errors.append("National code is required")
        if not self.name:
            errors.append("Name is required")
        return errors


@dataclass
class ArticleOrService:
    """ردیف صورتحساب (کالا یا خدمت)"""
    row_number: int = 1
    stuff_id: str = ""               # شناسه کالا/خدمت
    description: str = ""
    quantity: Decimal = Decimal("1")
    unit: str = "عدد"
    unit_price: Decimal = Decimal("0")
    discount: Decimal = Decimal("0")
    vat_rate: Decimal = Decimal("9")  # نرخ مالیات بر ارزش افزوده
    vat_amount: Decimal = Decimal("0")
    total_after_discount: Decimal = Decimal("0")
    total_plus_vat: Decimal = Decimal("0")

    def calculate(self):
        subtotal = self.quantity * self.unit_price
        self.total_after_discount = subtotal - self.discount
        self.vat_amount = self.total_after_discount * self.vat_rate / Decimal("100")
        self.total_plus_vat = self.total_after_discount + self.vat_amount


@dataclass
class Payment:
    """اطلاعات پرداخت"""
    method: SettlementMethod = SettlementMethod.CASH
    amount: Decimal = Decimal("0")
    description: str = ""


@dataclass
class FiscalUniqueId:
    """شناسه یکتای مالیاتی"""
    fiscal_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    def generate(self) -> str:
        """Generate a unique fiscal ID."""
        from hashlib import sha256
        raw = f"{self.timestamp.isoformat()}-{id(self)}-{self.fiscal_id}"
        return sha256(raw.encode()).hexdigest()[:32]


@dataclass
class MeasurementUnit:
    """واحد اندازه‌گیری"""
    code: str = " unit"
    name: str = "عدد"


@dataclass
class PointOfSale:
    """اطلاعات محل فروش"""
    terminal_id: str = ""
    pos_code: str = ""


@dataclass
class PaymentTerminalUniqueId:
    """شناسه یکتای پایانه فروش"""
    terminal_id: str = ""
    fiscal_id: str = ""


@dataclass
class Stuff:
    """کالا / خدمت"""
    stuff_id: str = ""
    name: str = ""
    unit: str = "عدد"
    tariff_code: str = ""         # کد تعرفه گمرکی
    barcode: str = ""


@dataclass
class Customer:
    """خریدار نهایی"""
    name: str = ""
    national_code: str = ""
    economic_code: str = ""
    postal_code: str = ""
    address: str = ""
    phone: str = ""
    identity_type: str = "Real"   # Real=حقیقی, Legal=حقوقی
    is_final_consumer: bool = True  # مصرف‌کننده نهایی


@dataclass
class TaxInvoice:
    """صورتحساب مالیاتی — main invoice model matching Iranian tax authority format."""
    invoice_type: InvoiceType = InvoiceType.SALE
    pattern: Pattern = Pattern.NORMAL
    subject: Subject = Subject.GOODS
    status: InvoiceStatus = InvoiceStatus.DRAFT
    settlement_method: SettlementMethod = SettlementMethod.CASH

    # Identifiers
    fiscal_id: str = ""
    reference_code: str = ""
    easy_invoice_id: str = ""

    # Dates
    issue_date: datetime = field(default_factory=datetime.now)
    due_date: Optional[datetime] = None

    # Parties
    seller: TaxPayer = field(default_factory=TaxPayer)
    buyer: Customer = field(default_factory=Customer)

    # Line items
    articles: list[ArticleOrService] = field(default_factory=list)

    # Payments
    payments: list[Payment] = field(default_factory=list)

    # Totals
    total_gross: Decimal = Decimal("0")
    total_discount: Decimal = Decimal("0")
    total_net: Decimal = Decimal("0")
    total_vat: Decimal = Decimal("0")
    total_payable: Decimal = Decimal("0")

    # Shipping
    postage: Decimal = Decimal("0")
    post_vat: Decimal = Decimal("0")
    packaging: Decimal = Decimal("0")
    packaging_vat: Decimal = Decimal("0")

    # POS
    point_of_sale: Optional[PointOfSale] = None

    def calculate_totals(self):
        """Calculate all invoice totals."""
        self.total_gross = sum(a.quantity * a.unit_price for a in self.articles)
        self.total_discount = sum(a.discount for a in self.articles)
        self.total_net = self.total_gross - self.total_discount
        self.total_vat = sum(a.vat_amount for a in self.articles)
        self.total_payable = (
            self.total_net
            + self.total_vat
            + self.postage
            + self.post_vat
            + self.packaging
            + self.packaging_vat
        )

    def to_dict(self) -> dict:
        return {
            "invoice_type": self.invoice_type.value,
            "pattern": self.pattern.value,
            "subject": self.subject.value,
            "status": self.status.value,
            "settlement_method": self.settlement_method.value,
            "fiscal_id": self.fiscal_id,
            "reference_code": self.reference_code,
            "easy_invoice_id": self.easy_invoice_id,
            "issue_date": self.issue_date.isoformat(),
            "seller": {
                "name": self.seller.name,
                "national_code": self.seller.national_code,
                "economic_code": self.seller.economic_code,
            },
            "buyer": {
                "name": self.buyer.name,
                "national_code": self.buyer.national_code,
                "economic_code": self.buyer.economic_code,
                "is_final_consumer": self.buyer.is_final_consumer,
            },
            "articles": [
                {
                    "row": a.row_number,
                    "description": a.description,
                    "quantity": float(a.quantity),
                    "unit_price": float(a.unit_price),
                    "discount": float(a.discount),
                    "vat_rate": float(a.vat_rate),
                    "vat_amount": float(a.vat_amount),
                    "total": float(a.total_plus_vat),
                }
                for a in self.articles
            ],
            "total_gross": float(self.total_gross),
            "total_discount": float(self.total_discount),
            "total_net": float(self.total_net),
            "total_vat": float(self.total_vat),
            "total_payable": float(self.total_payable),
        }