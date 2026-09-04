"""Domain models for business event footprints and audit records."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional


@dataclass
class DocumentLineFootprint:
    """Represents a row in business_document_line."""
    id: int
    doc_id: int
    item_name: str
    amount: Decimal
    quantity: int = 1


@dataclass
class DocumentFootprint:
    """Represents a row in business_document."""
    id: int
    org_id: int
    type: str
    doc_no: str
    applicant: str
    nature: str
    amount: Decimal
    submit_time: datetime
    approve_time: datetime
    status: str
    lines: List[DocumentLineFootprint] = field(default_factory=list)


@dataclass
class VoucherLineFootprint:
    """Represents a row in accounting_voucher_line."""
    id: int
    voucher_id: int
    subject_code: str
    subject_name: str
    debit: Decimal = Decimal("0.00")
    credit: Decimal = Decimal("0.00")


@dataclass
class VoucherFootprint:
    """Represents a row in accounting_voucher."""
    id: int
    org_id: int
    voucher_no: str
    type: str
    gen_time: datetime
    int_time: datetime
    status: str
    debit: Decimal
    credit: Decimal
    lines: List[VoucherLineFootprint] = field(default_factory=list)


@dataclass
class LinkFootprint:
    """Represents a row in document_voucher_link."""
    doc_id: int
    voucher_id: int


@dataclass
class IntegrationFootprint:
    """Represents a row in integration_result."""
    id: int
    voucher_id: int
    status: str  # "SUCCESS" or "FAIL"
    retry_count: int
    error_code: str
    error_message: str
    integration_time: datetime


@dataclass
class EventFootprint:
    """A cohesive business event footprint spanning all related tables."""
    document: DocumentFootprint
    voucher: VoucherFootprint
    link: LinkFootprint
    integration: IntegrationFootprint


@dataclass
class SimulationAuditRecord:
    """Structured audit trail record for simulation writes."""
    run_id: str
    timestamp: str
    business_type: str
    event_count: int
    rows_written: Dict[str, int]
    status: str  # "SUCCESS", "FAILED", "ROLLED_BACK", "BLOCKED"
    error: Optional[str] = None
    duration_ms: float = 0.0


def validate_footprint(event: EventFootprint) -> None:
    """Strictly validate multi-table footprint consistency and causal ordering."""
    doc = event.document
    vch = event.voucher
    link = event.link
    integ = event.integration

    if doc.amount <= Decimal("0.00"):
        raise ValueError(f"Document amount must be positive, got {doc.amount}")

    if not doc.lines:
        raise ValueError("Document must have at least one line item")

    line_sum = sum((line.amount for line in doc.lines), Decimal("0.00"))
    if line_sum != doc.amount:
        raise ValueError(
            f"Document lines sum ({line_sum}) does not equal document amount ({doc.amount})"
        )

    for line in doc.lines:
        if line.doc_id != doc.id:
            raise ValueError(f"Document line doc_id mismatch: {line.doc_id} != {doc.id}")

    if vch.debit != doc.amount or vch.credit != doc.amount:
        raise ValueError(
            f"Voucher amount mismatch: debit={vch.debit}, credit={vch.credit}, doc={doc.amount}"
        )

    if len(vch.lines) < 2:
        raise ValueError(f"Voucher must have at least two entries, got {len(vch.lines)}")

    total_debit = sum((vl.debit for vl in vch.lines), Decimal("0.00"))
    total_credit = sum((vl.credit for vl in vch.lines), Decimal("0.00"))
    if total_debit != total_credit or total_debit != doc.amount:
        raise ValueError(
            f"Voucher line debit/credit mismatch: debit={total_debit}, credit={total_credit}, expected={doc.amount}"
        )

    for vl in vch.lines:
        if vl.voucher_id != vch.id:
            raise ValueError(f"Voucher line voucher_id mismatch: {vl.voucher_id} != {vch.id}")

    if link.doc_id != doc.id or link.voucher_id != vch.id:
        raise ValueError(
            f"Link mismatch: link=({link.doc_id}, {link.voucher_id}), expected=({doc.id}, {vch.id})"
        )

    if integ.voucher_id != vch.id:
        raise ValueError(
            f"Integration voucher_id mismatch: {integ.voucher_id} != {vch.id}"
        )

    if doc.org_id != vch.org_id:
        raise ValueError(
            f"Organization ID mismatch between doc ({doc.org_id}) and voucher ({vch.org_id})"
        )

    if not (doc.submit_time <= doc.approve_time <= vch.gen_time <= vch.int_time):
        raise ValueError(
            f"Timeline inversion detected: submit={doc.submit_time}, approve={doc.approve_time}, "
            f"gen={vch.gen_time}, int={vch.int_time}"
        )

    if vch.int_time != integ.integration_time:
        raise ValueError(
            f"Integration time mismatch: voucher.int_time={vch.int_time}, integ={integ.integration_time}"
        )

    if not doc.applicant.strip():
        raise ValueError("Document applicant must not be empty")
