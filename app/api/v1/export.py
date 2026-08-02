"""Export/Download API routes — PDF, Excel, receipt upload."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.dependencies import get_current_active_user, get_admin_user, require_any_role
from app.models.identity import User
from app.models.finance import Receipt
from app.services import invoice_service, product_service, order_service
from app.services.pdf.invoice_pdf import generate_invoice_pdf
from app.services.excel.excel_export import export_products_to_excel, export_orders_to_excel, export_invoices_to_excel

router = APIRouter(prefix="/export", tags=["Export"])


# ── PDF Exports ──

@router.get("/invoice/{invoice_id}/pdf")
async def export_invoice_pdf(
    invoice_id: str,
    current_user: User = Depends(require_any_role("Admin", "Financial Manager")),
    db: AsyncSession = Depends(get_db),
):
    try:
        iid = uuid.UUID(invoice_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid invoice ID")
    invoice = await invoice_service.get_invoice_by_id(db, iid)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    data = invoice_service.build_invoice_response(invoice)
    pdf = generate_invoice_pdf(data)
    return StreamingResponse(
        pdf, media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=invoice_{invoice.reference_code or invoice_id}.pdf"},
    )


@router.get("/order/{order_id}/pdf")
async def export_order_pdf(
    order_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        oid = uuid.UUID(order_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid order ID")
    order = await order_service.get_order_by_id(db, oid)
    if not order or (order.user_id != current_user.id and "Admin" not in {ur.role.name for ur in current_user.roles}):
        raise HTTPException(status_code=404, detail="Order not found")
    data = order_service.build_order_response(order)
    pdf = generate_invoice_pdf(data)
    return StreamingResponse(
        pdf, media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=order_{order.reference_code or order_id}.pdf"},
    )


# ── Excel Exports ──

@router.get("/products/xlsx")
async def export_products_xlsx(
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    from app.schemas.product import ProductSearchParams
    products, _ = await product_service.search_products(db, ProductSearchParams(page=1, page_size=10000))
    items = [product_service._build_product_list_response(p).model_dump() for p in products]
    xlsx = export_products_to_excel(items)
    return StreamingResponse(
        xlsx, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=products_{datetime.now().strftime('%Y%m%d')}.xlsx"},
    )


@router.get("/orders/xlsx")
async def export_orders_xlsx(
    current_user: User = Depends(require_any_role("Admin", "Orders Manager")),
    db: AsyncSession = Depends(get_db),
):
    orders, _ = await order_service.get_all_orders(db, 1, 10000)
    items = [order_service.build_order_response(o) for o in orders]
    xlsx = export_orders_to_excel(items)
    return StreamingResponse(
        xlsx, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=orders_{datetime.now().strftime('%Y%m%d')}.xlsx"},
    )


@router.get("/invoices/xlsx")
async def export_invoices_xlsx(
    current_user: User = Depends(require_any_role("Admin", "Financial Manager")),
    db: AsyncSession = Depends(get_db),
):
    invoices, _ = await invoice_service.get_all_invoices(db, 1, 10000)
    items = [invoice_service.build_invoice_response(inv) for inv in invoices]
    xlsx = export_invoices_to_excel(items)
    return StreamingResponse(
        xlsx, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=invoices_{datetime.now().strftime('%Y%m%d')}.xlsx"},
    )


# ── Receipt Upload ──

@router.post("/receipt/upload")
async def upload_receipt(
    order_id: str = Form(...), price: float = Form(...),
    description: str = Form(""), image: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    import aiofiles
    from app.schemas.finance import ReceiptCreate

    file_ext = image.filename.split(".")[-1] if "." in image.filename else "jpg"
    file_name = f"receipt_{current_user.id.hex[:8]}_{uuid.uuid4().hex[:8]}.{file_ext}"
    file_path = f"app/static/uploads/receipts/{file_name}"

    content = await image.read()
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    try:
        oid = uuid.UUID(order_id) if order_id else None
    except ValueError:
        oid = None

    receipt = await finance_service.create_receipt(
        db, ReceiptCreate(price=price, description=description, image_url=f"/static/uploads/receipts/{file_name}", order_id=oid), current_user.id
    )
    return {"message": "رسید با موفقیت ثبت شد", "receipt_id": str(receipt.id)}


# Audit Log

@router.get("/audit-logs")
async def get_audit_logs(
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db),
):
    from app.models.common import Log
    from sqlalchemy import select, func
    count_stmt = select(func.count(Log.id)).where(Log.is_removed == False)
    total = (await db.execute(count_stmt)).scalar() or 0
    stmt = select(Log).where(Log.is_removed == False).order_by(Log.insert_date.desc()).offset((page-1)*page_size).limit(page_size)
    result = await db.execute(stmt)
    logs = result.scalars().all()
    return {
        "items": [{"id": str(l.id), "table": l.table_name, "description": l.description, "type": l.type, "date": l.insert_date} for l in logs],
        "total": total, "page": page, "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


from app.services import finance_service