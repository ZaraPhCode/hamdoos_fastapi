"""PDF generation service — invoice, order reports.

Mirrors the PDF functionality from Invoice.cs (ToPdf), PDFsharp/MigraDoc usage.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image,
)


def generate_invoice_pdf(invoice_data: dict) -> io.BytesIO:
    """Generate a PDF for an invoice. Mirrors Invoice.ToPdf()."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    elements = []

    # Title
    elements.append(Paragraph(f"<b>فاکتور فروش</b>", styles["Title"]))
    elements.append(Spacer(1, 10))

    # Invoice info
    info_style = ParagraphStyle("Info", parent=styles["Normal"], fontSize=10)
    elements.append(Paragraph(f"شماره: {invoice_data.get('reference_code', '-')}", info_style))
    elements.append(Paragraph(f"تاریخ: {invoice_data.get('date', datetime.now().strftime('%Y-%m-%d'))}", info_style))
    elements.append(Spacer(1, 10))

    # Seller/Buyer info
    elements.append(Paragraph(f"<b>فروشنده:</b> {invoice_data.get('identity_name', 'آشا شاپ')}", info_style))
    elements.append(Paragraph(f"<b>خریدار:</b> {invoice_data.get('identity_name', '-')}", info_style))
    if invoice_data.get('national_code_or_id'):
        elements.append(Paragraph(f"کد ملی: {invoice_data['national_code_or_id']}", info_style))
    elements.append(Spacer(1, 15))

    # Products table
    products = invoice_data.get('invoice_products', [])
    if products:
        data = [["ردیف", "کالا", "تعداد", "قیمت واحد", "تخفیف", "مالیات", "جمع"]]
        for i, p in enumerate(products, 1):
            data.append([
                str(i),
                p.get('name', '-'),
                str(p.get('count', 0)),
                f"{p.get('unit_price', 0):,.0f}",
                f"{p.get('discount_amount', 0):,.0f}",
                f"{p.get('taxes_and_duties', 0):,.0f}",
                f"{p.get('total_price', 0):,.0f}",
            ])
        table = Table(data, colWidths=[30, 200, 50, 80, 60, 60, 80])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4F46E5')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F3F4F6')]),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 15))

    # Totals
    total_style = ParagraphStyle("Total", parent=styles["Normal"], fontSize=11)
    elements.append(Paragraph(f"<b>جمع کل:</b> {invoice_data.get('total_price', 0):,.0f} تومان", total_style))
    elements.append(Paragraph(f"<b>تخفیف:</b> {invoice_data.get('total_discount_price', 0):,.0f} تومان", total_style))
    elements.append(Paragraph(f"<b>مالیات:</b> {invoice_data.get('total_taxes_and_duties', 0):,.0f} تومان", total_style))
    elements.append(Paragraph(f"<b>قابل پرداخت:</b> {invoice_data.get('payable', 0):,.0f} تومان", ParagraphStyle("Payable", parent=styles["Normal"], fontSize=12, textColor=colors.HexColor('#4F46E5'))))

    doc.build(elements)
    buf.seek(0)
    return buf


def generate_order_pdf(order_data: dict) -> io.BytesIO:
    """Generate a PDF for an order slip."""
    return generate_invoice_pdf(order_data)  # Similar layout