"""Invoice business logic — CRUD, tax calculations, purchase orders, suppliers.

Mirrors Invoice.cs, InvoiceProduct.cs, PurchaseOrder.cs from the .NET domain.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.invoice import (
    Invoice, InvoiceProduct, InvoiceReference,
    PurchaseOrder, PurchaseOrderDetail,
    Supplier, SupplierProduct,
)
from app.models.product import Product
from app.models.identity import User
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceProductBase,
    PurchaseOrderCreate,
    SupplierCreate,
)


# ── Suppliers ──

async def get_all_suppliers(db: AsyncSession) -> list[Supplier]:
    stmt = select(Supplier).where(Supplier.is_removed == False).order_by(Supplier.intermediary_name)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_supplier_by_id(db: AsyncSession, supplier_id: uuid.UUID) -> Optional[Supplier]:
    stmt = select(Supplier).where(Supplier.id == supplier_id, Supplier.is_removed == False)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_supplier(db: AsyncSession, request: SupplierCreate, user_id: uuid.UUID) -> Supplier:
    supplier = Supplier(
        id=uuid.uuid4(),
        **request.model_dump(),
        insert_date=datetime.now(timezone.utc),
        update_date=datetime.now(timezone.utc),
    )
    db.add(supplier)
    await db.flush()
    return supplier


async def update_supplier(db: AsyncSession, supplier: Supplier, data: dict) -> Supplier:
    for field in ("telephone", "address", "site", "intermediary_name"):
        if field in data:
            setattr(supplier, field, data[field])
    supplier.update_date = datetime.now(timezone.utc)
    await db.flush()
    return supplier


async def delete_supplier(db: AsyncSession, supplier: Supplier) -> None:
    supplier.is_removed = True
    supplier.update_date = datetime.now(timezone.utc)
    await db.flush()


# ── Invoices ──

async def generate_reference_code(db: AsyncSession) -> str:
    """Generate unique reference code for invoice."""
    stmt = select(func.count(Invoice.id)).where(Invoice.is_removed == False)
    result = await db.execute(stmt)
    count = result.scalar() or 0
    return f"INV-{datetime.now(timezone.utc).strftime('%Y%m')}-{count + 1:05d}"


async def create_invoice(
    db: AsyncSession,
    request: InvoiceCreate,
    user_id: uuid.UUID,
) -> Invoice:
    ref_code = await generate_reference_code(db)

    # Calculate totals
    total_price = 0.0
    total_discount = 0.0
    total_taxes = 0.0

    invoice = Invoice(
        id=uuid.uuid4(),
        reference_code=ref_code,
        type=request.type or "Sale",
        status=request.status or "Bought",
        date=datetime.now(timezone.utc),
        description=request.description,
        tracking_number=request.tracking_number,
        notes=request.notes,
        weight=request.weight,
        is_cash=request.is_cash,
        pay_method=request.pay_method,
        user_id=request.user_id,
        order_id=request.order_id,
        count=sum(p.count for p in request.invoice_products),
        identity_type=request.identity_type,
        identity_name=request.identity_name,
        national_code_or_id=request.national_code_or_id,
        economic_code=request.economic_code,
        identity_postal_code=request.identity_postal_code,
        identity_address=request.identity_address,
        identity_country=request.identity_country,
        identity_province=request.identity_province,
        identity_city=request.identity_city,
        identity_phone_number=request.identity_phone_number,
        final_consumer=request.final_consumer,
        post_type=request.post_type,
        postage_fee=request.postage_fee,
        post_vat=request.post_vat,
        post_vat_rate=request.post_vat_rate,
        packaging_cost=request.packaging_cost,
        packaging_vat=request.packaging_vat,
        packaging_vat_rate=request.packaging_vat_rate,
        insert_date=datetime.now(timezone.utc),
        update_date=datetime.now(timezone.utc),
    )
    db.add(invoice)
    await db.flush()

    # Create invoice products
    for idx, prod in enumerate(request.invoice_products):
        unit_price = prod.unit_price or 0
        count = prod.count or 1
        discount = prod.discount_amount or 0
        vat_rate = prod.vat_rate or 0
        line_total = unit_price * count
        line_discount = discount * count
        line_after_discount = line_total - line_discount
        line_taxes = line_after_discount * vat_rate / 100
        line_total_plus_taxes = line_after_discount + line_taxes

        total_price += line_total
        total_discount += line_discount
        total_taxes += line_taxes

        invoice_product = InvoiceProduct(
            id=uuid.uuid4(),
            invoice_id=invoice.id,
            product_id=prod.product_id,
            variety_id=prod.variety_id,
            part_number=prod.part_number,
            name=prod.name,
            model=prod.model,
            en_name=prod.en_name,
            image_url=prod.image_url,
            count=count,
            unit_price=unit_price,
            total_price=line_total,
            discount_amount=discount,
            price_after_discount=unit_price - discount,
            total_price_after_discount=line_after_discount,
            taxes_and_duties=line_taxes,
            vat_rate=vat_rate,
            total_amount_plus_taxes=line_total_plus_taxes,
            type=prod.type or "Product",
            currency_id=prod.currency_id,
            currency_price=prod.currency_price,
            supplier_id=prod.supplier_id,
            insert_date=datetime.now(timezone.utc),
            update_date=datetime.now(timezone.utc),
        )
        db.add(invoice_product)

    # Update invoice totals
    postage = request.postage_fee or 0
    post_vat = request.post_vat or 0
    packaging = request.packaging_cost or 0
    packaging_vat = request.packaging_vat or 0
    total_after_discount = total_price - total_discount
    payable = total_after_discount + total_taxes + postage + post_vat + packaging + packaging_vat

    invoice.total_price = total_price
    invoice.total_discount_price = total_discount
    invoice.total_price_after_discount = total_after_discount
    invoice.total_taxes_and_duties = total_taxes
    invoice.total_price_plus_taxes = total_after_discount + total_taxes
    invoice.vat = total_taxes
    invoice.payable = payable
    await db.flush()

    return invoice


async def get_invoice_by_id(db: AsyncSession, invoice_id: uuid.UUID) -> Optional[Invoice]:
    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.invoice_products))
        .where(Invoice.id == invoice_id, Invoice.is_removed == False)
    )
    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()


async def get_user_invoices(
    db: AsyncSession, user_id: uuid.UUID, page: int = 1, page_size: int = 20
) -> tuple[list[Invoice], int]:
    count_stmt = select(func.count(Invoice.id)).where(
        Invoice.user_id == user_id, Invoice.is_removed == False
    )
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    stmt = (
        select(Invoice)
        .where(Invoice.user_id == user_id, Invoice.is_removed == False)
        .order_by(Invoice.insert_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    invoices = result.scalars().all()
    return list(invoices), total


async def get_all_invoices(
    db: AsyncSession, page: int = 1, page_size: int = 20, type_filter: Optional[str] = None
) -> tuple[list[Invoice], int]:
    conditions = [Invoice.is_removed == False]
    if type_filter:
        conditions.append(Invoice.type == type_filter)

    count_stmt = select(func.count(Invoice.id)).where(*conditions)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.invoice_products), selectinload(Invoice.user))
        .where(*conditions)
        .order_by(Invoice.insert_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    invoices = result.unique().scalars().all()
    return list(invoices), total


async def update_invoice(db: AsyncSession, invoice: Invoice, data: dict) -> Invoice:
    for field in ("type", "status", "date", "description", "notes", "tracking_number",
                  "identity_type", "identity_name", "national_code_or_id", "economic_code",
                  "identity_postal_code", "identity_address", "identity_country",
                  "identity_province", "identity_city", "identity_phone_number",
                  "post_type", "pay_method", "is_cash"):
        if field in data:
            setattr(invoice, field, data[field])
    invoice.update_date = datetime.now(timezone.utc)
    await db.flush()
    return invoice


async def delete_invoice(db: AsyncSession, invoice: Invoice) -> None:
    invoice.is_removed = True
    invoice.update_date = datetime.now(timezone.utc)
    await db.flush()


async def create_invoice_from_order(db: AsyncSession, order_id: uuid.UUID) -> Optional[Invoice]:
    """Create a tax invoice from a completed order. Mirrors Order.CreateInvoice()."""
    from app.models.order import OrderModel as Order, OrderProduct

    stmt = (
        select(Order)
        .options(selectinload(Order.order_products))
        .where(Order.id == order_id, Order.is_removed == False)
    )
    result = await db.execute(stmt)
    order = result.unique().scalar_one_or_none()
    if not order:
        return None

    # Check if invoice already exists
    existing = select(Invoice).where(Invoice.order_id == order_id, Invoice.is_removed == False)
    existing_result = await db.execute(existing)
    if existing_result.scalar_one_or_none():
        return None

    invoice_products = []
    for op in order.order_products or []:
        invoice_products.append({
            "product_id": op.product_id,
            "variety_id": op.variety_id,
            "count": op.count,
            "unit_price": float(op.unit_price or 0),
            "discount_amount": float(op.discount or 0),
            "vat_rate": float(op.vat_rate or 0),
            "name": op.product.name if hasattr(op, 'product') and op.product else "",
        })

    create_data = InvoiceCreate(
        type="Sale",
        status="Bought",
        order_id=order.id,
        user_id=order.user_id,
        description=f"فاکتور سفارش شماره {order.reference_code}",
        identity_name=f"{order.first_name} {order.last_name}",
        identity_phone_number=order.phone_number,
        identity_address=order.address_description,
        identity_postal_code=order.postal_code,
        postage_fee=float(order.postage_fee or 0),
        post_vat=float(order.post_vat or 0),
        post_vat_rate=float(order.post_vat_rate or 0),
        packaging_cost=float(order.packaging_cost or 0),
        packaging_vat=float(order.packaging_vat or 0),
        packaging_vat_rate=float(order.packaging_vat_rate or 0),
        final_consumer=True,
        invoice_products=[InvoiceProductBase(**p) for p in invoice_products],
    )

    return await create_invoice(db, InvoiceCreate(**create_data.model_dump()), order.user_id or uuid.uuid4())


# ── Purchase Orders ──

async def create_purchase_order(db: AsyncSession, request: PurchaseOrderCreate, user_id: uuid.UUID) -> PurchaseOrder:
    from app.models.invoice import PurchaseOrder
    ref_code = f"PO-{datetime.now(timezone.utc).strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"

    po = PurchaseOrder(
        id=uuid.uuid4(),
        reference_code=ref_code,
        status=request.status or "Ordered",
        date=datetime.now(timezone.utc),
        shipping_and_clearance_price=request.shipping_and_clearance_price,
        insert_date=datetime.now(timezone.utc),
        update_date=datetime.now(timezone.utc),
    )
    db.add(po)
    await db.flush()

    for detail in request.details:
        po_detail = PurchaseOrderDetail(
            id=uuid.uuid4(),
            purchase_order_id=po.id,
            product_id=detail.product_id,
            variety_id=detail.variety_id,
            count=detail.count,
            currency_price=detail.currency_price,
            weight_percent=detail.weight_percent,
            currency_id=detail.currency_id,
            supplier_product_id=detail.supplier_product_id,
            insert_date=datetime.now(timezone.utc),
            update_date=datetime.now(timezone.utc),
        )
        db.add(po_detail)

    await db.flush()
    return po


async def get_purchase_order_by_id(db: AsyncSession, po_id: uuid.UUID) -> Optional[PurchaseOrder]:
    stmt = (
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.purchase_order_details))
        .where(PurchaseOrder.id == po_id, PurchaseOrder.is_removed == False)
    )
    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()


async def get_all_purchase_orders(
    db: AsyncSession, page: int = 1, page_size: int = 20
) -> tuple[list[PurchaseOrder], int]:
    count_stmt = select(func.count(PurchaseOrder.id)).where(PurchaseOrder.is_removed == False)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    stmt = (
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.purchase_order_details))
        .where(PurchaseOrder.is_removed == False)
        .order_by(PurchaseOrder.insert_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    pos = result.unique().scalars().all()
    return list(pos), total


async def update_purchase_order(db: AsyncSession, po: PurchaseOrder, data: dict) -> PurchaseOrder:
    if "date" in data:
        po.date = data["date"]
    if "status" in data:
        po.status = data["status"]
    if "shipping_and_clearance_price" in data:
        try:
            po.shipping_and_clearance_price = float(data["shipping_and_clearance_price"])
        except (ValueError, TypeError):
            pass
    po.update_date = datetime.now(timezone.utc)
    await db.flush()
    return po


async def delete_purchase_order(db: AsyncSession, po: PurchaseOrder) -> None:
    po.is_removed = True
    po.update_date = datetime.now(timezone.utc)
    await db.flush()


def build_invoice_response(invoice: Invoice) -> dict:
    return {
        "id": invoice.id,
        "reference_code": invoice.reference_code,
        "easy_invoice_id": invoice.easy_invoice_id,
        "type": invoice.type,
        "status": invoice.status,
        "date": invoice.date,
        "description": invoice.description,
        "tracking_number": invoice.tracking_number,
        "notes": invoice.notes,
        "weight": float(invoice.weight) if invoice.weight else None,
        "is_cash": invoice.is_cash,
        "pay_method": invoice.pay_method,
        "order_id": invoice.order_id,
        "purchase_order_id": invoice.purchase_order_id,
        "user_id": invoice.user_id,
        "count": invoice.count,
        "total_price": float(invoice.total_price) if invoice.total_price else None,
        "total_discount_price": float(invoice.total_discount_price) if invoice.total_discount_price else None,
        "total_price_after_discount": float(invoice.total_price_after_discount) if invoice.total_price_after_discount else None,
        "total_price_plus_taxes": float(invoice.total_price_plus_taxes) if invoice.total_price_plus_taxes else None,
        "total_taxes_and_duties": float(invoice.total_taxes_and_duties) if invoice.total_taxes_and_duties else None,
        "payable": float(invoice.payable) if invoice.payable else None,
        "vat": float(invoice.vat) if invoice.vat else None,
        "postage_fee": float(invoice.postage_fee) if invoice.postage_fee else None,
        "post_vat": float(invoice.post_vat) if invoice.post_vat else None,
        "post_vat_rate": float(invoice.post_vat_rate) if invoice.post_vat_rate else None,
        "packaging_cost": float(invoice.packaging_cost) if invoice.packaging_cost else None,
        "packaging_vat": float(invoice.packaging_vat) if invoice.packaging_vat else None,
        "packaging_vat_rate": float(invoice.packaging_vat_rate) if invoice.packaging_vat_rate else None,
        "identity_type": invoice.identity_type,
        "identity_name": invoice.identity_name,
        "national_code_or_id": invoice.national_code_or_id,
        "economic_code": invoice.economic_code,
        "identity_postal_code": invoice.identity_postal_code,
        "identity_address": invoice.identity_address,
        "identity_country": invoice.identity_country,
        "identity_province": invoice.identity_province,
        "identity_city": invoice.identity_city,
        "identity_phone_number": invoice.identity_phone_number,
        "final_consumer": invoice.final_consumer,
        "post_type": invoice.post_type,
        "insert_date": invoice.insert_date,
        "invoice_products": [
            {
                "id": ip.id,
                "invoice_id": ip.invoice_id,
                "product_id": ip.product_id,
                "variety_id": ip.variety_id,
                "part_number": ip.part_number,
                "name": ip.name,
                "model": ip.model,
                "en_name": ip.en_name,
                "image_url": ip.image_url,
                "count": ip.count,
                "unit_price": float(ip.unit_price) if ip.unit_price else None,
                "total_price": float(ip.total_price) if ip.total_price else None,
                "discount_amount": float(ip.discount_amount) if ip.discount_amount else None,
                "price_after_discount": float(ip.price_after_discount) if ip.price_after_discount else None,
                "total_price_after_discount": float(ip.total_price_after_discount) if ip.total_price_after_discount else None,
                "taxes_and_duties": float(ip.taxes_and_duties) if ip.taxes_and_duties else None,
                "vat_rate": float(ip.vat_rate) if ip.vat_rate else None,
                "total_amount_plus_taxes": float(ip.total_amount_plus_taxes) if ip.total_amount_plus_taxes else None,
                "type": ip.type,
                "currency_id": ip.currency_id,
                "currency_price": float(ip.currency_price) if ip.currency_price else None,
                "currency_name": ip.currency_name,
                "supplier_id": ip.supplier_id,
                "supplier_link": ip.supplier_link,
            }
            for ip in (invoice.invoice_products or [])
        ] if hasattr(invoice, 'invoice_products') else [],
    }


def build_purchase_order_response(po: PurchaseOrder) -> dict:
    return {
        "id": po.id,
        "reference_code": po.reference_code,
        "status": po.status,
        "date": po.date,
        "shipping_and_clearance_price": float(po.shipping_and_clearance_price) if po.shipping_and_clearance_price else None,
        "insert_date": po.insert_date,
        "details": [
            {
                "id": d.id,
                "purchase_order_id": d.purchase_order_id,
                "product_id": d.product_id,
                "variety_id": d.variety_id,
                "count": d.count,
                "currency_price": float(d.currency_price) if d.currency_price else None,
                "weight_percent": float(d.weight_percent) if d.weight_percent else None,
                "currency_id": d.currency_id,
                "supplier_product_id": d.supplier_product_id,
            }
            for d in (po.purchase_order_details or [])
        ] if hasattr(po, 'purchase_order_details') else [],
    }