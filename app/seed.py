"""Database seed data — mirrors Seed.cs, SD.cs, ClaimTypes.cs, SiteModel.cs.

Creates default roles, admin user, policies, and initial site settings.
Run via: python -m app.seed
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base import BaseEntityMixin
from app.core.security import hash_password
from app.database import async_session_factory, engine
from app.models.identity import User, Role, UserRole, RoleClaim, Claim
from app.models.common import SiteSetting, AdminParameter
from app.models.enums import OperationType
from app.models.product import CategoryOption
from app.config.site_config import SEED_USERS


# ── Static Data (mirrors SD.cs) ──

class SD:
    ADMIN = "Admin"
    PRODUCT_MANAGER = "Product Manager"
    PRODUCT_OFFICER = "Product Officer"
    WAREHOUSE_KEEPER = "Warehouse Keeper"
    ORDERS_MANAGER = "Orders Manager"
    ORDERS_OFFICER = "Orders Officer"
    FINANCIAL_MANAGER = "Financial Manager"
    SYSTEM = "System"
    CUSTOMER = "Customer"

    ROLE_DESCRIPTIONS = {
        ADMIN: "مدیر سیستم",
        PRODUCT_MANAGER: "مدیر محصولات",
        PRODUCT_OFFICER: "کارشناس محصولات",
        FINANCIAL_MANAGER: "مدیر مالی",
        ORDERS_MANAGER: "مدیر سفارشات",
        ORDERS_OFFICER: "کارشناس سفارشات",
        WAREHOUSE_KEEPER: "مدیر انبار",
    }

    SEED_USERS = SEED_USERS


# ── Permission Policy (mirrors OperationAR.cs) ──

class OperationAR:
    """Operation Authorization Requirement — defines a permission policy."""

    def __init__(self, name: str, op_type: str, policy_name: str):
        self.name = name
        self.type = op_type
        self.policy_name = policy_name

    def __repr__(self):
        return f"OperationAR({self.policy_name})"


class Operations:
    """Static operation factories — mirrors Operations.cs."""

    @staticmethod
    def _policy_name(entity_name: str, operation: str) -> str:
        return f"{entity_name}.{operation}"

    @classmethod
    def Read(cls, entity_name: str = "") -> OperationAR:
        return OperationAR(entity_name, OperationType.READ.value, cls._policy_name(entity_name, "Read"))

    @classmethod
    def Detail(cls, entity_name: str = "") -> OperationAR:
        return OperationAR(entity_name, OperationType.DETAIL.value, cls._policy_name(entity_name, "Detail"))

    @classmethod
    def Create(cls, entity_name: str = "") -> OperationAR:
        return OperationAR(entity_name, OperationType.CREATE.value, cls._policy_name(entity_name, "Create"))

    @classmethod
    def Update(cls, entity_name: str = "") -> OperationAR:
        return OperationAR(entity_name, OperationType.UPDATE.value, cls._policy_name(entity_name, "Update"))

    @classmethod
    def Delete(cls, entity_name: str = "") -> OperationAR:
        return OperationAR(entity_name, OperationType.DELETE.value, cls._policy_name(entity_name, "Delete"))

    @classmethod
    def Report(cls, entity_name: str = "") -> OperationAR:
        return OperationAR(entity_name, OperationType.REPORT.value, cls._policy_name(entity_name, "Report"))

    @classmethod
    def FullControl(cls, entity_name: str = "") -> OperationAR:
        return OperationAR(entity_name, OperationType.FULL_CONTROL.value, cls._policy_name(entity_name, "FullControl"))


# ── All Policies (mirrors Seed.cs Policies list) ──

def get_all_policies() -> list[OperationAR]:
    entities = [
        "Log", "CurrencyDetail", "Currency", "IdentityInformation", "Claim",
        "User", "Role", "UserRole", "RoleClaim", "Receipt", "Tag", "ProductTag",
        "RelatedProduct", "ProductUnit", "Product", "ProductType", "Brand",
        "SimilarProduct", "ProductImage", "CategoryOption", "Variety",
        "ProductVariety", "MenuDatasheet", "Category", "OrderProduct", "Order",
        "OrderStatusRecord", "PayMethod", "PostType",
        "PaymentRequest", "CategoryTechnicalFeature", "TechnicalFeature",
        "TechnicalFeatureEnum", "TechnicalFeatureValue", "TechnicalTable",
        "TechnicalTableProduct", "Supplier", "SupplierProduct", "Invoice",
        "PurchaseOrder", "PurchaseOrderDetail", "InvoiceProduct",
        "Notification", "NotifiedProduct", "Comment", "Media",
        "Address", "BankInfo", "SiteSetting", "AdminParameter",
    ]
    policies = []
    for entity in entities:
        for op in ["Read", "Detail", "Create", "Update", "Delete"]:
            policies.append(OperationAR(entity, op, f"{entity}.{op}"))
    policies.append(OperationAR("Invoice", "FullControl", "Invoice.FullControl"))
    policies.append(OperationAR("Product", "Report", "Product.Report"))
    return policies


# ── Product Manager Role Claims ──

PRODUCT_MANAGER_ENTITIES = [
    "Category", "Product", "ProductType", "SimilarProduct", "RelatedProduct",
    "Tag", "ProductTag", "Brand", "ProductUnit", "CategoryOption",
    "TechnicalFeature", "TechnicalTable", "TechnicalTableProduct",
    "CategoryTechnicalFeature", "TechnicalFeatureEnum", "TechnicalFeatureValue",
    "MenuDatasheet", "ProductImage", "Media", "Variety", "ProductVariety",
    "Supplier", "SupplierProduct", "PurchaseOrder",
]

ORDERS_MANAGER_ENTITIES = [
    "Order", "OrderProduct", "Receipt", "NotifiedProduct", "PurchaseOrder",
]

FINANCIAL_MANAGER_ENTITIES = [
    "Invoice", "InvoiceProduct", "PurchaseOrder", "Currency", "CurrencyDetail",
    "IdentityInformation",
]


# ── Seed Runner ──

async def seed_database():
    """Run all seed operations."""
    async with async_session_factory() as db:
        print("Seeding database...")

        # 1. Default Category Option
        existing_co = await db.execute(select(CategoryOption).limit(1))
        if not existing_co.scalar_one_or_none():
            co = CategoryOption(id=uuid.uuid4(), name="پیش‌فرض",
                                insert_date=datetime.now(timezone.utc), update_date=datetime.now(timezone.utc))
            db.add(co)
            await db.flush()

        # 2. Roles
        roles = {}
        for role_name, desc in SD.ROLE_DESCRIPTIONS.items():
            existing = await db.execute(select(Role).where(Role.name == role_name))
            role = existing.scalar_one_or_none()
            if not role:
                role = Role(id=uuid.uuid4(), name=role_name, description=desc,
                            insert_date=datetime.now(timezone.utc), update_date=datetime.now(timezone.utc))
                db.add(role)
                await db.flush()
            roles[role_name] = role

        # Customer role
        existing_cust = await db.execute(select(Role).where(Role.name == SD.CUSTOMER))
        if not existing_cust.scalar_one_or_none():
            cust_role = Role(id=uuid.uuid4(), name=SD.CUSTOMER,
                             insert_date=datetime.now(timezone.utc), update_date=datetime.now(timezone.utc))
            db.add(cust_role)
            await db.flush()

        await db.flush()

        # 3. Users
        users = {}
        for key, data in SD.SEED_USERS.items():
            existing = await db.execute(select(User).where(User.user_name == data["username"]))
            user = existing.scalar_one_or_none()
            if not user:
                user = User(
                    id=uuid.uuid4(), user_name=data["username"], first_name=data["first_name"],
                    last_name=data["last_name"], phone_number=data["phone"], email=data["username"],
                    phone_number_confirmed=True, password_hash=hash_password(data["password"]),
                    has_password=True, insert_date=datetime.now(timezone.utc), update_date=datetime.now(timezone.utc),
                )
                db.add(user)
                await db.flush()
            users[key] = user

        # 4. Assign Admin role to admin user
        if SD.ADMIN in users and SD.ADMIN in roles:
            existing_ur = await db.execute(
                select(UserRole).where(UserRole.user_id == users[SD.ADMIN].id, UserRole.role_id == roles[SD.ADMIN].id)
            )
            if not existing_ur.scalar_one_or_none():
                ur = UserRole(id=uuid.uuid4(), user_id=users[SD.ADMIN].id, role_id=roles[SD.ADMIN].id,
                              insert_date=datetime.now(timezone.utc), update_date=datetime.now(timezone.utc))
                db.add(ur)

        # 5. Claims & Policies
        policies = get_all_policies()
        for policy in policies:
            existing_claim = await db.execute(
                select(Claim).where(Claim.type == policy.name, Claim.operation_type == policy.type)
            )
            if not existing_claim.scalar_one_or_none():
                claim = Claim(id=uuid.uuid4(), type=policy.name, operation_type=policy.type,
                              insert_date=datetime.now(timezone.utc), update_date=datetime.now(timezone.utc))
                db.add(claim)

        # 6. Admin Role Claims (all policies)
        if SD.ADMIN in roles:
            for policy in policies:
                existing_rc = await db.execute(
                    select(RoleClaim).where(
                        RoleClaim.role_id == roles[SD.ADMIN].id,
                        RoleClaim.operation_type == policy.type,
                        RoleClaim.operation_name == policy.policy_name,
                    )
                )
                if not existing_rc.scalar_one_or_none():
                    rc = RoleClaim(
                        id=uuid.uuid4(), role_id=roles[SD.ADMIN].id,
                        claim_type="Permission", claim_value=policy.name,
                        operation_type=policy.type, operation_name=policy.policy_name,
                        insert_date=datetime.now(timezone.utc), update_date=datetime.now(timezone.utc),
                    )
                    db.add(rc)

        # 7. Role-specific claims
        # Product Manager
        if SD.PRODUCT_MANAGER in roles:
            for entity in PRODUCT_MANAGER_ENTITIES:
                for op in ["Read", "Create", "Update", "Delete", "Detail"]:
                    policy_name = f"{entity}.{op}"
                    existing = await db.execute(
                        select(RoleClaim).where(
                            RoleClaim.role_id == roles[SD.PRODUCT_MANAGER].id,
                            RoleClaim.operation_name == policy_name,
                        )
                    )
                    if not existing.scalar_one_or_none():
                        rc = RoleClaim(id=uuid.uuid4(), role_id=roles[SD.PRODUCT_MANAGER].id,
                                       claim_type="Permission", claim_value=op,
                                       operation_type=op, operation_name=policy_name,
                                       insert_date=datetime.now(timezone.utc), update_date=datetime.now(timezone.utc))
                        db.add(rc)
            # Add Order.Read for product manager
            existing = await db.execute(select(RoleClaim).where(
                RoleClaim.role_id == roles[SD.PRODUCT_MANAGER].id, RoleClaim.operation_name == "Order.Read"))
            if not existing.scalar_one_or_none():
                db.add(RoleClaim(id=uuid.uuid4(), role_id=roles[SD.PRODUCT_MANAGER].id,
                                 claim_type="Permission", claim_value="Read",
                                 operation_type="Read", operation_name="Order.Read",
                                 insert_date=datetime.now(timezone.utc), update_date=datetime.now(timezone.utc)))

        # Orders Manager
        if SD.ORDERS_MANAGER in roles:
            for entity in ORDERS_MANAGER_ENTITIES:
                for op in ["Read", "Create", "Update", "Delete", "Detail"]:
                    policy_name = f"{entity}.{op}"
                    existing = await db.execute(select(RoleClaim).where(
                        RoleClaim.role_id == roles[SD.ORDERS_MANAGER].id, RoleClaim.operation_name == policy_name))
                    if not existing.scalar_one_or_none():
                        db.add(RoleClaim(id=uuid.uuid4(), role_id=roles[SD.ORDERS_MANAGER].id,
                                         claim_type="Permission", claim_value=op,
                                         operation_type=op, operation_name=policy_name,
                                         insert_date=datetime.now(timezone.utc), update_date=datetime.now(timezone.utc)))
            db.add(RoleClaim(id=uuid.uuid4(), role_id=roles[SD.ORDERS_MANAGER].id,
                             claim_type="Permission", claim_value="Read",
                             operation_type="Read", operation_name="Product.Read",
                             insert_date=datetime.now(timezone.utc), update_date=datetime.now(timezone.utc)))

        # Financial Manager
        if SD.FINANCIAL_MANAGER in roles:
            for entity in FINANCIAL_MANAGER_ENTITIES:
                for op in ["Read", "Create", "Update", "Delete", "Detail"]:
                    policy_name = f"{entity}.{op}"
                    existing = await db.execute(select(RoleClaim).where(
                        RoleClaim.role_id == roles[SD.FINANCIAL_MANAGER].id, RoleClaim.operation_name == policy_name))
                    if not existing.scalar_one_or_none():
                        db.add(RoleClaim(id=uuid.uuid4(), role_id=roles[SD.FINANCIAL_MANAGER].id,
                                         claim_type="Permission", claim_value=op,
                                         operation_type=op, operation_name=policy_name,
                                         insert_date=datetime.now(timezone.utc), update_date=datetime.now(timezone.utc)))
            db.add(RoleClaim(id=uuid.uuid4(), role_id=roles[SD.FINANCIAL_MANAGER].id,
                             claim_type="Permission", claim_value="FullControl",
                             operation_type="FullControl", operation_name="Invoice.FullControl",
                             insert_date=datetime.now(timezone.utc), update_date=datetime.now(timezone.utc)))
            db.add(RoleClaim(id=uuid.uuid4(), role_id=roles[SD.FINANCIAL_MANAGER].id,
                             claim_type="Permission", claim_value="Read",
                             operation_type="Read", operation_name="Product.Read",
                             insert_date=datetime.now(timezone.utc), update_date=datetime.now(timezone.utc)))
            db.add(RoleClaim(id=uuid.uuid4(), role_id=roles[SD.FINANCIAL_MANAGER].id,
                             claim_type="Permission", claim_value="Read",
                             operation_type="Read", operation_name="Order.Read",
                             insert_date=datetime.now(timezone.utc), update_date=datetime.now(timezone.utc)))

        # Orders Officer - read only
        if SD.ORDERS_OFFICER in roles:
            for entity in ["Order", "OrderProduct", "PurchaseOrder", "Product"]:
                for op in ["Read", "Detail"]:
                    existing = await db.execute(select(RoleClaim).where(
                        RoleClaim.role_id == roles[SD.ORDERS_OFFICER].id, RoleClaim.operation_name == f"{entity}.{op}"))
                    if not existing.scalar_one_or_none():
                        db.add(RoleClaim(id=uuid.uuid4(), role_id=roles[SD.ORDERS_OFFICER].id,
                                         claim_type="Permission", claim_value=op,
                                         operation_type=op, operation_name=f"{entity}.{op}",
                                         insert_date=datetime.now(timezone.utc), update_date=datetime.now(timezone.utc)))

        # Product Officer - product read/create/update + order read
        if SD.PRODUCT_OFFICER in roles:
            for op in ["Read", "Create", "Update", "Detail"]:
                existing = await db.execute(select(RoleClaim).where(
                    RoleClaim.role_id == roles[SD.PRODUCT_OFFICER].id, RoleClaim.operation_name == f"Product.{op}"))
                if not existing.scalar_one_or_none():
                    db.add(RoleClaim(id=uuid.uuid4(), role_id=roles[SD.PRODUCT_OFFICER].id,
                                     claim_type="Permission", claim_value=op,
                                     operation_type=op, operation_name=f"Product.{op}",
                                     insert_date=datetime.now(timezone.utc), update_date=datetime.now(timezone.utc)))
            existing = await db.execute(select(RoleClaim).where(
                RoleClaim.role_id == roles[SD.PRODUCT_OFFICER].id, RoleClaim.operation_name == "Order.Read"))
            if not existing.scalar_one_or_none():
                db.add(RoleClaim(id=uuid.uuid4(), role_id=roles[SD.PRODUCT_OFFICER].id,
                                 claim_type="Permission", claim_value="Read",
                                 operation_type="Read", operation_name="Order.Read",
                                 insert_date=datetime.now(timezone.utc), update_date=datetime.now(timezone.utc)))

        # Warehouse Keeper
        if SD.WAREHOUSE_KEEPER in roles:
            for entity in ["PostType", "PurchaseOrder", "Invoice", "InvoiceProduct", "Product", "Order"]:
                for op in ["Read", "Create", "Update", "Delete", "Detail"] if entity in ["PostType", "PurchaseOrder", "Invoice", "InvoiceProduct"] else ["Read"]:
                    existing = await db.execute(select(RoleClaim).where(
                        RoleClaim.role_id == roles[SD.WAREHOUSE_KEEPER].id, RoleClaim.operation_name == f"{entity}.{op}"))
                    if not existing.scalar_one_or_none():
                        db.add(RoleClaim(id=uuid.uuid4(), role_id=roles[SD.WAREHOUSE_KEEPER].id,
                                         claim_type="Permission", claim_value=op,
                                         operation_type=op, operation_name=f"{entity}.{op}",
                                         insert_date=datetime.now(timezone.utc), update_date=datetime.now(timezone.utc)))

        # 8. Default Admin Parameter
        existing_ap = await db.execute(select(AdminParameter).limit(1))
        if not existing_ap.scalar_one_or_none():
            ap = AdminParameter(id=uuid.uuid4(), ConfirmOrderPN="09930003120", ConfrimOrderEm="hamdoos@outlook.com",
                                insert_date=datetime.now(timezone.utc), update_date=datetime.now(timezone.utc))
            db.add(ap)

        await db.commit()
        print("Database seeded successfully!")
        print(f"  - Roles created: {len(roles)}")
        print(f"  - Users created: {len(SD.SEED_USERS)}")
        print(f"  - Policies created: {len(policies)}")


async def main():
    try:
        await seed_database()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())