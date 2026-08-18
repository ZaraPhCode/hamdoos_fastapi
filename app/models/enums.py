"""All enums matching AshaShop.Domain/Enums/ (16 sub-folders)."""

from __future__ import annotations

import enum


# ── Address ──
class Country(str, enum.Enum):
    IRAN = "Iran"


class Province(str, enum.Enum):
    TEHRAN = "Tehran"
    ALBORZ = "Alborz"
    ISFAHAN = "Isfahan"
    KHORASAN_RAZAVI = "Khorasan Razavi"
    KHORASAN_JONOBI = "Khorasan Jonobi"
    KHORASAN_SHOMALI = "Khorasan Shomali"
    FARS = "Fars"
    KHUZESTAN = "Khuzestan"
    AZARBAYJAN_SHARGHI = "Azarbayjan Sharghi"
    AZARBAYJAN_GARBI = "Azarbayjan Garbi"
    ARDABIL = "Ardabil"
    SISTAN = "Sistan va Baluchestan"
    KERMAN = "Kerman"
    YAZD = "Yazd"
    QOM = "Qom"
    QAZVIN = "Qazvin"
    GILAN = "Gilan"
    MAZANDARAN = "Mazandaran"
    GOLESTAN = "Golestan"
    HAMEDAN = "Hamedan"
    KERMANSHAH = "Kermanshah"
    ILAM = "Ilam"
    LORESTAN = "Lorestan"
    KOHGILUYE = "Kohgiluye va Boyer Ahmad"
    CHAHARMAHAL = "Chaharmahal va Bakhtiari"
    BUSHEHR = "Bushehr"
    HORMOZGAN = "Hormozgan"
    ZANJAN = "Zanjan"
    SEMNAN = "Semnan"
    MARKAZI = "Markazi"
    KORDESTAN = "Kordestan"


# ── Common ──
class Gender(str, enum.Enum):
    UNKNOWN = "Unknown"
    MALE = "Male"
    FEMALE = "Female"


class LogType(str, enum.Enum):
    CREATE = "Create"
    UPDATE = "Update"
    DELETE = "Delete"
    DELETE_FROM_DATABASE = "DeleteFromDatabase"
    RECOVERY = "Recovery"


class ArrangeLogs(str, enum.Enum):
    INSERT_DATE = "InsertDate"
    UPDATE_DATE = "UpdateDate"
    TABLE = "Table"
    TYPE = "Type"
    DESCRIPTION = "Description"
    CREATOR = "Creator"


# ── Content ──
class ContentType(str, enum.Enum):
    UNKNOWN = "Unknown"
    IMAGE = "Image"
    VIDEO = "Video"
    FEATURE_IMAGE = "FeatureImage"
    COVER_IMAGE = "CoverImage"


class Rate(str, enum.Enum):
    NOT_ENTERED = "NotEntered"
    SO_BAD = "SoBad"
    BAD = "Bad"
    NORMAL = "Normal"
    GOOD = "Good"
    EXCELLENT = "Excellent"


# ── Customer ──
class CustomerType(str, enum.Enum):
    NATURAL_PERSON = "NaturalPerson"
    LEGAL_PERSON = "LegalPerson"


class RefundMethod(str, enum.Enum):
    BANK_CARD = "BankCard"
    WALLET = "Wallet"


class UserActionType(str, enum.Enum):
    ADD_FAVORITE = "AddFavorite"
    VISIT_PRODUCT = "VisitProduct"
    NOTIFY_PRODUCT = "NotifyProduct"


class NotifyType(str, enum.Enum):
    SMS = "SmsNotification"
    EMAIL = "EmailNotification"


class ArrangeNotifyProduct(str, enum.Enum):
    INSERT_DATE = "InsertDate"
    SMS_RESPONSE_DATE = "SmsResponseDate"
    EMAIL_RESPONSE_DATE = "EmailResponseDate"
    USER_NAME = "UserName"
    PRODUCT = "Product"
    SUPPLY_DATE = "SupplyDate"


# ── Finance ──
class PaymentRequestStatus(str, enum.Enum):
    PAYING = "Paying"
    SUCCESS = "Success"
    CANCELED = "Canceled"


class PaymentWage(str, enum.Enum):
    UNKNOWN = "Unknown"
    MERCHANT = "Merchant"


class ReceiptStatus(str, enum.Enum):
    AWAITING_CONFIRMATION = "AwaitingConfirmation"
    FAILED = "Failed"
    CONFIRMED = "Confirmed"


class Bank(str, enum.Enum):
    AIANDEH = "Aiandeh"
    MELLAT = "Mellat"
    MELLI = "Melli"
    SADERAT = "Saderat"
    PASARGHAD = "Pasarghad"


class ArrangeVarieties(str, enum.Enum):
    PRODUCT_NAME = "ProductName"
    STOCK_QUANTITY = "StockQuantity"
    PRICE = "Price"
    DISCOUNT = "Discound"
    PROFIT_RATE = "ProfitRate"
    CURRENCY_PRICE = "CurrencyPrice"
    DATE = "Date"
    PART_NUMBER = "PartNumber"


class Tab(str, enum.Enum):
    LOAD_IMAGE = "loadImage"
    PAYMENT_INFO = "paymentInfo"


# ── Identity ──
class IdentityStatus(str, enum.Enum):
    AWAITING_CONFIRMATION = "AwaitingConfirmation"
    CONFIRMED = "Confirmed"
    PENDING_DELETION = "PendingDeletion"
    REJECTED = "Rejected"


class IdentityType(str, enum.Enum):
    REAL = "Real"
    LEGAL = "Legal"
    CIVIC_PARTICIPATION = "CivicParticipation"
    NON_IRANIAN = "Non_IranianNationals"


class OperationType(str, enum.Enum):
    UNKNOWN = "Unknown"
    READ = "Read"
    DETAIL = "Detail"
    UPDATE = "Update"
    CREATE = "Create"
    DELETE = "Delete"
    REPORT = "Report"
    FULL_CONTROL = "FullControl"


class ArrangeIdentity(str, enum.Enum):
    NAME = "Name"
    NATIONAL_CODE = "NationalCodeOrId"
    USER_NAME = "UserName"
    TYPE = "Type"
    STATUS = "Status"


class ArrangeRoleClaims(str, enum.Enum):
    OPERATION_NAME = "OperationName"
    OPERATION_TYPE = "OperationType"
    ROLE = "Role"


class ArrangeUsers(str, enum.Enum):
    FULL_NAME = "FullName"
    PHONE_NUMBER = "PhoneNumber"
    GENDER = "Gender"
    USERNAME = "UserName"


# ── Inventory ──
class InventoryOperation(str, enum.Enum):
    IMPORT = "Import"
    EXPORT = "Export"


# ── Invoice ──
class InvoiceType(str, enum.Enum):
    SALE = "Sale"
    PURCHASE = "Purchase"
    WASTAGE = "Wastage"
    RETURN_FROM_SALE = "ReturnFromSale"


class InvoiceStatus(str, enum.Enum):
    SHOPPING = "Shopping"
    BOUGHT = "Bought"
    PROCESSING = "Processing"
    CONFIRMED = "Confirmed"
    CANCELED = "Canceled"


class InvoiceProductType(str, enum.Enum):
    PRODUCT = "Product"
    SERVICE = "Service"
    POST = "Post"
    PACKING = "Packing"


class PurchaseOrderStatus(str, enum.Enum):
    IN_TRANSIT = "InTransit"
    ORDERED = "Ordered"
    DISCHARGED = "Discharged"
    ENTERING_WAREHOUSE = "EnteringWarehouse"
    SUPPLIED = "Supplied"
    CANCELED = "Canceled"


class ArrangeInvoices(str, enum.Enum):
    REFERENCE_CODE = "ReferenceCode"
    DATE = "Date"
    FULL_NAME = "FullName"
    TOTAL_PRICE = "TotalPrice"
    PURCHASE_STATUS = "PurchaseStatus"
    TYPE = "Type"


class ArrangePurchaseOrder(str, enum.Enum):
    USER = "User"
    DATE = "Date"
    REFERENCE_CODE = "ReferenceCode"


# ── Manufacturers ──
class ManufacturerType(str, enum.Enum):
    UNDEFINED = "Undefined"
    ASHA = "ASHA"
    GENTEC = "Gentec"
    THORLABS = "Thorlabs"
    MARKTECH = "Marktech"
    MINILI = "MiNiLi"
    NEWPORT = "NewPort"


class CapabilityType(str, enum.Enum):
    pass


# ── Orders ──
class OrderStatus(str, enum.Enum):
    ORDERING = "Ordering"
    AWAITING_PAYMENT = "AwaitingPayment"
    PAID = "Paid"
    CONFIRMED_PAYMENT = "ConfirmedPayment"
    PROCESSING = "Processing"
    COLLECTING = "Collecting"
    PACKING = "Packing"
    SENDING = "Sending"
    POSTED = "Posted"
    CANCELED = "Canceled"
    NEEDS_CHECK = "NeedsToBeChecked"
    NEXT_ORDER = "NextOrder"


class PaymentStatus(str, enum.Enum):
    AWAITING_PAYMENT = "AwaitingPayment"
    UNPAID = "Unpaid"
    PAID = "Paid"


class PayMethod(str, enum.Enum):
    ZARINPAL = "Zarinpal"
    BANK_RECEIPT = "BankReceipt"


class PostTypeEnum(str, enum.Enum):
    FREE_DELIVERY = "FreeDelivery"


class DiscountTarget(str, enum.Enum):
    PRODUCT = "Product"
    CATEGORY = "Category"
    USER = "User"


class DiscountType(str, enum.Enum):
    PERCENTAGE = "Percentage"
    AMOUNT = "Amount"


class OrderProductAction(str, enum.Enum):
    ADD = "Add"
    DOWN = "Down"
    UP = "Up"
    UPDATE = "Update"


class ArrangeOrders(str, enum.Enum):
    DATE = "Date"
    USER_FULL_NAME = "UserFullName"
    REFERENCE_CODE = "ReferenceCode"
    TOTAL_PRICE = "TotalPrice"
    TOTAL_PRICE_AFTER_DISCOUNT = "TotalPriceAfterDiscount"
    PAYABLE = "Payable"
    PAY_METHOD = "PayMethod"
    COUNT = "Count"
    STATUS = "Status"


# ── Products ──
class ProductStatus(str, enum.Enum):
    UNKNOWN = "Unknown"
    IN_PRODUCTION = "InProduction"
    IMPORTING = "Importing"
    IN_STOCK = "InStock"
    OUT_OF_STOCK = "OutOfStock"
    ON_DEMAND = "OnDemand"
    OBSOLETE = "Obsolete"


class MenuDatasheetType(str, enum.Enum):
    DATASHEET = "Datasheet"
    USER_MANUAL = "UserManual"
    QUICK_START = "QuickStart"


class TagType(str, enum.Enum):
    NEWS = "News"


class ArrangeProducts(str, enum.Enum):
    INSERT_DATE = "InsertDate"
    UPDATE_DATE = "UpdateDate"
    PRODUCT_NAME = "ProudctName"
    CATEGORY = "Category"
    PRICE = "Price"
    PART_NUMBER = "PartNumber"
    CREATOR = "Creator"


# ── Product Ordering ──
class ProductOrder(str, enum.Enum):
    INSERT_DATE = "InsertDate"
    PRICE = "Price"
    NAME = "Name"
    RATE = "Rate"
    VIEWS = "Views"


# ── Support ──
class TicketStatus(str, enum.Enum):
    OPEN = "Open"
    ANSWERED = "Answered"
    CLOSED = "Closed"
    PENDING = "Pending"


class TicketPriority(str, enum.Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class ProblemSubject(str, enum.Enum):
    GENERAL = "General"
    TECHNICAL = "Technical"
    ORDER_TRACKING = "OrderTracking"
    FINANCIAL = "Financial"
    SUGGESTION = "Suggestion"


class ChatSubject(str, enum.Enum):
    pass


# ── Technical Features ──
class TechnicalFeatureOrder(str, enum.Enum):
    D_VALUE = "DValue"
    UNIT = "Unit"
    S_VALUE = "SValue"
    E_VALUE = "EValue"
    B_VALUE = "BValue"
    MIN_VALUE = "MinValue"
    MIN_UNIT = "MinUnit"
    MAX_VALUE = "MaxValue"
    MAX_UNIT = "MaxUnit"
    X_VALUE = "XValue"
    X_UNIT = "XUnit"
    Y_VALUE = "YValue"
    Y_UNIT = "YUnit"
    Z_VALUE = "ZValue"
    Z_UNIT = "ZUnit"
    E_VALUE1 = "EValue1"


# ── Wallets ──
class TransferStatus(str, enum.Enum):
    PROCESSING = "Processing"
    CONFIRMED = "Confirmed"
    FAILED = "Failed"


# ── Warranty ──
class WarrantyType(str, enum.Enum):
    MANUFACTURER = "ManufacturerWarranty"
    EXTENDED = "ExtendedWarranty"
    SERVICE = "ServiceWarranty"
    REPLACEMENT = "ReplacementWarranty"