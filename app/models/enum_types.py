"""Enum int storage compatible with the .NET (SQL Server) schema.

The .NET app persists all enums as ``int`` (the enum member's ordinal or
explicit value). The FastAPI app historically stored string values.  These
decorators make the PostgreSQL schema match the .NET schema (int columns)
while keeping the Python-facing string values the app code already uses, so
existing services/queries keep working unchanged.
"""

from __future__ import annotations

from sqlalchemy import Integer
from sqlalchemy.types import TypeDecorator


class EnumAsInt(TypeDecorator):
    """Stores an enum as the matching .NET int, exposes the app string value.

    ``value_map`` maps the app-side string value (e.g. ``"Paid"``) to the
    .NET int (e.g. ``2``).  Reads convert back to the app-side string.
    """

    impl = Integer
    cache_ok = False

    def __init__(self, value_map: dict[str, int]):
        super().__init__()
        self.value_map = dict(value_map)
        self.reverse_map = {v: k for k, v in value_map.items()}

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, int) and value in self.reverse_map:
            return value
        s = value.value if hasattr(value, "value") else value
        return self.value_map.get(s, s)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return self.reverse_map.get(value, value)


# ── .NET enum int maps (ordinal/declared order from AshaShop.Domain) ──

CountryEnum = EnumAsInt({"Iran": 0})

GenderEnum = EnumAsInt({"Unknown": 0, "Male": 1, "Female": 2})

ContentTypeEnum = EnumAsInt({
    "Unknown": 0, "Image": 1, "Video": 2, "FeatureImage": 3, "CoverImage": 4,
})

RateEnum = EnumAsInt({
    "NotEntered": 0, "SoBad": 1, "Bad": 2, "Normal": 3, "Good": 4, "Excellent": 5,
})

PaymentRequestStatusEnum = EnumAsInt({"Paying": 0, "Success": 1, "Canceled": 2})

PaymentWageEnum = EnumAsInt({"Unknown": 0, "Merchant": 1})

ReceiptStatusEnum = EnumAsInt({
    "AwaitingConfirmation": 0, "Failed": 1, "Confirmed": 2,
})

BankEnum = EnumAsInt({
    "Aiandeh": 0, "Mellat": 1, "Melli": 2, "Saderat": 3, "Pasarghad": 4,
})

TabEnum = EnumAsInt({"loadImage": 0, "paymentInfo": 1})

IdentityStatusEnum = EnumAsInt({
    "AwaitingConfirmation": 0, "Confirmed": 1, "PendingDeletion": 2, "Rejected": 3,
})

# .NET IdentityType_t uses explicit values 1..4
IdentityTypeEnum = EnumAsInt({
    "Real": 1, "Legal": 2, "CivicParticipation": 3, "Non_IranianNationals": 4,
})

OperationTypeEnum = EnumAsInt({
    "Unknown": 0, "Read": 1, "Detail": 2, "Update": 3, "Create": 4,
    "Delete": 5, "Report": 6, "FullControl": 7,
})

InvoiceTypeEnum = EnumAsInt({"Sale": 0, "Purchase": 1, "Wastage": 2, "ReturnFromSale": 3})

InvoiceStatusEnum = EnumAsInt({
    "Shopping": 0, "Bought": 1, "Processing": 2, "Confirmed": 3, "Canceled": 4,
})

InvoiceProductTypeEnum = EnumAsInt({"Product": 0, "Service": 1, "Post": 2, "Packing": 3})

PurchaseOrderStatusEnum = EnumAsInt({
    "InTransit": 0, "Ordered": 1, "Discharged": 2, "EnteringWarehouse": 3,
    "Supplied": 4, "Canceled": 5,
})

OrderStatusEnum = EnumAsInt({
    "Ordering": 0, "AwaitingPayment": 1, "Paid": 2, "ConfirmedPayment": 3,
    "Processing": 4, "Collecting": 5, "Packing": 6, "Sending": 7,
    "Posted": 8, "Canceled": 9, "NeedsToBeChecked": 10, "NextOrder": 11,
})

PaymentStatusEnum = EnumAsInt({"AwaitingPayment": 0, "Unpaid": 1, "Paid": 2})

PayMethodEnum = EnumAsInt({"Zarinpal": 0, "BankReceipt": 1})

PostTypeEnum_ = EnumAsInt({"FreeDelivery": 0})

DiscountTargetEnum = EnumAsInt({"Product": 0, "Category": 1, "User": 2})

DiscountTypeEnum = EnumAsInt({"Percentage": 0, "Amount": 1})

OrderProductActionEnum = EnumAsInt({"Add": 0, "Down": 1, "Up": 2, "Update": 3})

ProductStatusEnum = EnumAsInt({
    "Unknown": 0, "InProduction": 1, "Importing": 2, "InStock": 3,
    "OutOfStock": 4, "OnDemand": 5, "Obsolete": 6,
})

MenuDatasheetTypeEnum = EnumAsInt({"Datasheet": 0, "UserManual": 1, "QuickStart": 2})

TagTypeEnum = EnumAsInt({"News": 0})

CustomerTypeEnum = EnumAsInt({"NaturalPerson": 0, "LegalPerson": 1})

RefundMethodEnum = EnumAsInt({"BankCard": 0, "BankKart": 0, "Wallet": 1})

UserActionTypeEnum = EnumAsInt({"AddFavorite": 0, "VisitProduct": 1, "NotifyProduct": 2})

InventoryOperationEnum = EnumAsInt({"Import": 0, "Export": 1})

TransferStatusEnum = EnumAsInt({"Processing": 0, "Confirmed": 1, "Failed": 2})

WarrantyTypeEnum = EnumAsInt({
    "ManufacturerWarranty": 0, "ExtendedWarranty": 1,
    "ServiceWarranty": 2, "ReplacementWarranty": 3,
})

ManufacturerTypeEnum = EnumAsInt({
    "Undefined": 0, "ASHA": 1, "Gentec": 2, "Thorlabs": 3, "Marktech": 4,
    "MiNiLi": 5, "NewPort": 6,
})
