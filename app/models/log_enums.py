from __future__ import annotations

"""Mappings mirroring the .NET Logger enums (Table_t / LogType_t) and the
snake_case table names used throughout this codebase.

IMPORTANT: Table_t ordering is fixed because the integer is stored in the
database (mirrors the .NET comment "this enum is in database, so do not change
the order !!!")."""


# ── Table_t (name -> int) ──
LOG_TABLE_INT: dict[str, int] = {
    "Addresses": 0,
    "AdminParameters": 1,
    "BankInfoes": 2,
    "Brands": 3,
    "Captchas": 4,
    "Categories": 5,
    "Logs": 6,
    "CategoryTechnicalFeatures": 7,
    "Claims": 8,
    "Comments": 9,
    "Currencies": 10,
    "CurrencyDetails": 11,
    "Customer": 12,
    "Discounts": 13,
    "FavoriteListItems": 14,
    "FavoriteProductLists": 15,
    "InvoiceProducts": 16,
    "Invoices": 17,
    "Medias": 18,
    "MenuDatasheets": 19,
    "MobileNumbers": 20,
    "NotifiedProducts": 21,
    "OrderProducts": 22,
    "Orders": 23,
    "OrderStatusRecords": 24,
    "PaymentRequests": 25,
    "PayMethods": 26,
    "PurchaseOrders": 27,
    "PurchaseOrderDetails": 28,
    "ProductImages": 29,
    "Products": 30,
    "PriceHistories": 31,
    "PostTypes": 32,
    "ProductTags": 33,
    "ProductTypes": 34,
    "ProductUnits": 35,
    "ProvinceCities": 36,
    "Receipts": 37,
    "RelatedProducts": 38,
    "RoleClaims": 39,
    "Roles": 40,
    "SearchHistory": 41,
    "SimilarProducts": 42,
    "SiteSettings": 43,
    "Suppliers": 44,
    "SmsCodes": 45,
    "TechnicalFeatures": 46,
    "TechnicalFeatureValues": 47,
    "TechnicalFeatureEnums": 48,
    "SuggestedProducts": 49,
    "Tags": 50,
    "TechnicalTableProducts": 51,
    "TechnicalTables": 52,
    "Transaction": 53,
    "UserClaims": 54,
    "UserLogins": 55,
    "UserRoles": 56,
    "Users": 57,
    "UserTokens": 58,
    "VisitedProducts": 59,
    "Wallet": 60,
    "WalletTransfer": 61,
    "CategoryOptions": 62,
    "OptionItems": 63,
    "ProductVarieties": 64,
    "Varieties": 65,
    "SupplierProducts": 66,
    "IdentityInformations": 67,
}

LOG_TABLE_NAME: dict[int, str] = {v: k for k, v in LOG_TABLE_INT.items()}

# Table returned by the Table_t enum -> per-table listing order
LOG_TABLE_ORDER: list[str] = [
    name for name, _ in sorted(LOG_TABLE_INT.items(), key=lambda kv: kv[1])
]


# ── snake_case table names used across this codebase -> .NET enum name ──
LOG_TABLE_NAME_MAP: dict[str, str] = {
    "addresses": "Addresses",
    "admin_parameters": "AdminParameters",
    "bank_infos": "BankInfoes",
    "brands": "Brands",
    "captchas": "Captchas",
    "categories": "Categories",
    "logs": "Logs",
    "category_technical_features": "CategoryTechnicalFeatures",
    "claims": "Claims",
    "comments": "Comments",
    "currencies": "Currencies",
    "currency_details": "CurrencyDetails",
    "customer": "Customer",
    "discounts": "Discounts",
    "favorite_list_items": "FavoriteListItems",
    "favorite_product_lists": "FavoriteProductLists",
    "invoice_products": "InvoiceProducts",
    "invoices": "Invoices",
    "medias": "Medias",
    "menu_datasheets": "MenuDatasheets",
    "mobile_numbers": "MobileNumbers",
    "notified_products": "NotifiedProducts",
    "order_products": "OrderProducts",
    "orders": "Orders",
    "order_status_records": "OrderStatusRecords",
    "payment_requests": "PaymentRequests",
    "pay_methods": "PayMethods",
    "purchase_orders": "PurchaseOrders",
    "purchase_order_details": "PurchaseOrderDetails",
    "product_images": "ProductImages",
    "products": "Products",
    "price_histories": "PriceHistories",
    "post_types": "PostTypes",
    "product_tags": "ProductTags",
    "product_types": "ProductTypes",
    "product_units": "ProductUnits",
    "province_cities": "ProvinceCities",
    "receipts": "Receipts",
    "related_products": "RelatedProducts",
    "role_claims": "RoleClaims",
    "roles": "Roles",
    "search_history": "SearchHistory",
    "similar_products": "SimilarProducts",
    "site_settings": "SiteSettings",
    "suppliers": "Suppliers",
    "sms_codes": "SmsCodes",
    "technical_features": "TechnicalFeatures",
    "technical_feature_values": "TechnicalFeatureValues",
    "technical_feature_enums": "TechnicalFeatureEnums",
    "suggested_products": "SuggestedProducts",
    "tags": "Tags",
    "technical_table_products": "TechnicalTableProducts",
    "technical_tables": "TechnicalTables",
    "transaction": "Transaction",
    "user_claims": "UserClaims",
    "user_logins": "UserLogins",
    "user_roles": "UserRoles",
    "users": "Users",
    "user_tokens": "UserTokens",
    "visited_products": "VisitedProducts",
    "wallet": "Wallet",
    "wallet_transfers": "WalletTransfer",
    "category_options": "CategoryOptions",
    "option_items": "OptionItems",
    "product_varieties": "ProductVarieties",
    "varieties": "Varieties",
    "supplier_products": "SupplierProducts",
    "identity_informations": "IdentityInformations",
}


# ── LogType_t (name -> int) ──
LOG_TYPE_INT: dict[str, int] = {
    "Create": 0,
    "Update": 1,
    "Delete": 2,
    "DeleteFromDatabase": 3,
    "Recovery": 4,
}

LOG_TYPE_NAME: dict[int, str] = {v: k for k, v in LOG_TYPE_INT.items()}


def resolve_table_int(value: object) -> int:
    """Resolve a table identifier to its .NET Table_t int value.

    Accepts an int, an enum name (e.g. 'Products') or a snake_case table name
    (e.g. 'products'). Unknown values fall back to 0 (Addresses).
    """
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value if value in LOG_TABLE_NAME else 0
    if isinstance(value, str):
        stripped = value.strip()
        if stripped in LOG_TABLE_INT:
            return LOG_TABLE_INT[stripped]
        enum_name = LOG_TABLE_NAME_MAP.get(stripped, stripped)
        if enum_name in LOG_TABLE_INT:
            return LOG_TABLE_INT[enum_name]
        try:
            num = int(stripped)
            if num in LOG_TABLE_NAME:
                return num
        except (TypeError, ValueError):
            pass
    return 0


def resolve_type_int(value: object) -> int:
    """Resolve a log-type identifier to its .NET LogType_t int value.

    Accepts an int or an enum name (e.g. 'Create'). Non-standard values used in
    this codebase (e.g. 'Batch') fall back to 0 (Create).
    """
    if isinstance(value, int):
        return value if value in LOG_TYPE_NAME else 0
    if isinstance(value, str):
        stripped = value.strip()
        if stripped in LOG_TYPE_INT:
            return LOG_TYPE_INT[stripped]
        try:
            num = int(stripped)
            if num in LOG_TYPE_NAME:
                return num
        except (TypeError, ValueError):
            pass
    return 0
