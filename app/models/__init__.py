# Import all models so they are registered with SQLAlchemy Base.metadata
# Order matters only for FK references — SQLAlchemy resolves strings lazily

from app.core.base import Base, BaseEntityMixin

# Common
from app.models.common import (
    ProvinceCity, City, Address, SiteSetting, Captcha, BankInfo,
    MobileNumber, SmsCode, Log, AdminParameter,
)

# Identity
from app.models.identity import (
    User, Role, UserRole, RoleClaim, Claim, IdentityInformation,
    UserLogin, UserToken,
)

# Products
from app.models.product import (
    Category, Brand, ProductType, ProductUnit, Currency,
    Product, Variety, CategoryOption, ProductVariety,
    ProductImage, Tag, ProductTag, RelatedProduct, SimilarProduct,
    SuggestedProduct, FavoriteProductList, FavoriteListItem,
    VisitedProduct, MenuDatasheet, PriceHistory, Warranty,
    CategoryMedia, ProductMedia,
)

# Product Features
from app.models.product_features import (
    TechnicalFeature, TechnicalFeatureEnum, CategoryTechnicalFeature,
    TechnicalTable, TechnicalTableProduct, TechnicalFeatureValue,
    Feature, ProductAccessory,
)

# Orders
from app.models.order import (
    PayMethod, PostType, Discount, OrderModel, OrderProduct, OrderStatusRecord,
)

# Invoices
from app.models.invoice import (
    Supplier, SupplierProduct, PurchaseOrder, PurchaseOrderDetail,
    Invoice, InvoiceProduct, InvoiceReference,
)

# Finance, Wallet, Warehouse
from app.models.finance import (
    CurrencyDetail, PaymentRequest, Receipt, Transaction,
    Wallet, WalletTransfer, WarehouseMovement,
)

# Customer, Content
from app.models.customer_content import (
    Customer, Notification, NotifiedProduct, SearchHistory,
    SearchDetail, UserAction, Comment, Media,
)

# Support
from app.models.support import (
    Ticket, Chat, ChatMessage, ChatReferenceHistory,
)

# Manufacturer
from app.models.manufacturer import (
    Manufacturer, ASHAInfo, Capability, Paragraph,
)

__all__ = [
    # Core
    "Base", "BaseEntityMixin",

    # Common
    "ProvinceCity", "City", "Address", "SiteSetting", "Captcha",
    "BankInfo", "MobileNumber", "SmsCode", "Log", "AdminParameter",

    # Identity
    "User", "Role", "UserRole", "RoleClaim", "Claim",
    "IdentityInformation", "UserLogin", "UserToken",

    # Products
    "Category", "Brand", "ProductType", "ProductUnit", "Currency",
    "Product", "Variety", "CategoryOption", "ProductVariety",
    "ProductImage", "Tag", "ProductTag", "RelatedProduct", "SimilarProduct",
    "SuggestedProduct", "FavoriteProductList", "FavoriteListItem",
    "VisitedProduct", "MenuDatasheet", "PriceHistory", "Warranty",
    "CategoryMedia", "ProductMedia",

    # Product Features
    "TechnicalFeature", "TechnicalFeatureEnum", "CategoryTechnicalFeature",
    "TechnicalTable", "TechnicalTableProduct", "TechnicalFeatureValue",
    "Feature", "ProductAccessory",

    # Orders
    "PayMethod", "PostType", "Discount", "OrderModel", "OrderProduct",
    "OrderStatusRecord",

    # Invoices
    "Supplier", "SupplierProduct", "PurchaseOrder", "PurchaseOrderDetail",
    "Invoice", "InvoiceProduct", "InvoiceReference",

    # Finance
    "CurrencyDetail", "PaymentRequest", "Receipt", "Transaction",

    # Wallet & Warehouse
    "Wallet", "WalletTransfer", "WarehouseMovement",

    # Customer & Content
    "Customer", "Notification", "NotifiedProduct", "SearchHistory",
    "SearchDetail", "UserAction", "Comment", "Media",

    # Support
    "Ticket", "Chat", "ChatMessage", "ChatReferenceHistory",

    # Manufacturer
    "Manufacturer", "ASHAInfo", "Capability", "Paragraph",
]