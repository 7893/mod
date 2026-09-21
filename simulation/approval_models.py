"""Domain models and validation for the staged approval-to-voucher pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from app.business_rules import DOC_STATUS_PENDING_APPROVAL, SIMULATED_FLOW_NATURE

from .footprint_models import (
    DocumentFootprint,
    IntegrationFootprint,
    LinkFootprint,
    VoucherFootprint,
)


@dataclass(frozen=True)
class DocumentTransition:
    doc_id: int
    from_status: str
    to_status: str
    approve_time: datetime | None = None


@dataclass(frozen=True)
class SourceDocument:
    id: int
    org_id: int
    type: str
    amount: Decimal
    submit_time: datetime
    approve_time: datetime
    item_names: tuple[str, ...]


@dataclass
class ApprovalFlowBatch:
    submissions: list[DocumentFootprint] = field(default_factory=list)
    transitions: list[DocumentTransition] = field(default_factory=list)
    source_documents: dict[int, SourceDocument] = field(default_factory=dict)
    vouchers: list[VoucherFootprint] = field(default_factory=list)
    links: list[LinkFootprint] = field(default_factory=list)
    integrations: list[IntegrationFootprint] = field(default_factory=list)

    @property
    def increment_counts(self) -> dict[str, int]:
        return {
            "documents": len(self.submissions),
            "vouchers": len(self.vouchers),
            "integrations": len(self.integrations),
        }


def validate_approval_flow(batch: ApprovalFlowBatch) -> None:
    """Validate submissions and every connected document-voucher component."""
    for doc in batch.submissions:
        if doc.nature != SIMULATED_FLOW_NATURE:
            raise ValueError(f"Submission {doc.id} is not isolated to the staged flow")
        if doc.status != DOC_STATUS_PENDING_APPROVAL or doc.approve_time is not None:
            raise ValueError(f"Submission {doc.id} must start in pending approval")
        line_total = sum((line.amount for line in doc.lines), Decimal("0.00"))
        if doc.amount <= 0 or line_total != doc.amount:
            raise ValueError(f"Submission {doc.id} line total does not match document amount")

    transition_ids = [item.doc_id for item in batch.transitions]
    if len(transition_ids) != len(set(transition_ids)):
        raise ValueError("A document cannot transition twice in one flow batch")

    voucher_by_id = {voucher.id: voucher for voucher in batch.vouchers}
    if len(voucher_by_id) != len(batch.vouchers):
        raise ValueError("Duplicate voucher IDs in flow batch")
    integration_ids = {item.voucher_id for item in batch.integrations}
    if len(batch.integrations) != len(batch.vouchers) or integration_ids != set(voucher_by_id):
        raise ValueError("Every staged voucher must have exactly one integration result")

    for voucher in batch.vouchers:
        debit = sum((line.debit for line in voucher.lines), Decimal("0.00"))
        credit = sum((line.credit for line in voucher.lines), Decimal("0.00"))
        if debit != credit or debit != voucher.debit or credit != voucher.credit:
            raise ValueError(f"Voucher {voucher.id} is not balanced")

    link_pairs = {(link.doc_id, link.voucher_id) for link in batch.links}
    if len(link_pairs) != len(batch.links):
        raise ValueError("Duplicate document-voucher links in flow batch")
    linked_docs = {link.doc_id for link in batch.links}
    linked_vouchers = {link.voucher_id for link in batch.links}
    if linked_docs - set(batch.source_documents):
        raise ValueError("Link references a document outside the staged source set")
    if linked_vouchers != set(voucher_by_id):
        raise ValueError("Every staged voucher must be linked to a source document")

    doc_to_vouchers: dict[int, set[int]] = {}
    voucher_to_docs: dict[int, set[int]] = {}
    for doc_id, voucher_id in link_pairs:
        doc_to_vouchers.setdefault(doc_id, set()).add(voucher_id)
        voucher_to_docs.setdefault(voucher_id, set()).add(doc_id)

    unseen_docs = set(doc_to_vouchers)
    while unseen_docs:
        pending_docs = [unseen_docs.pop()]
        component_docs: set[int] = set()
        component_vouchers: set[int] = set()
        while pending_docs:
            doc_id = pending_docs.pop()
            if doc_id in component_docs:
                continue
            component_docs.add(doc_id)
            for voucher_id in doc_to_vouchers.get(doc_id, set()):
                if voucher_id in component_vouchers:
                    continue
                component_vouchers.add(voucher_id)
                pending_docs.extend(voucher_to_docs.get(voucher_id, set()) - component_docs)
        unseen_docs -= component_docs

        doc_total = sum((batch.source_documents[item].amount for item in component_docs), Decimal("0.00"))
        voucher_total = sum((voucher_by_id[item].debit for item in component_vouchers), Decimal("0.00"))
        if doc_total != voucher_total:
            raise ValueError(
                f"Document-voucher component is out of balance: docs={doc_total}, vouchers={voucher_total}"
            )
        org_ids = {batch.source_documents[item].org_id for item in component_docs}
        org_ids.update(voucher_by_id[item].org_id for item in component_vouchers)
        if len(org_ids) != 1:
            raise ValueError("A voucher component cannot cross organizations")

    integration_by_voucher = {item.voucher_id: item for item in batch.integrations}
    for voucher in batch.vouchers:
        integration = integration_by_voucher[voucher.id]
        linked = voucher_to_docs[voucher.id]
        latest_approval = max(batch.source_documents[item].approve_time for item in linked)
        if not (latest_approval <= voucher.gen_time <= voucher.int_time):
            raise ValueError(f"Voucher {voucher.id} violates approval/integration time order")
        if integration.integration_time != voucher.int_time:
            raise ValueError(f"Voucher {voucher.id} integration timestamp mismatch")
