"""Tenant, store and terminal responses tolerate a stored record with gaps.

The response schemas required fields that the documents allow to be None, and
transform_tenant iterated ``stores`` without a fallback. The API itself always
writes these fields, but a record written straight to the database (a migration,
another system) need not. One such record turned the single GET, and the whole
list, into a ValidationError (422) or a TypeError (500).
"""

from app.api.v1.schemas_transformer import SchemasTransformerV1
from app.models.documents.tenant_info_document import StoreInfo, TenantInfoDocument
from app.models.documents.terminal_info_document import TerminalInfoDocument


def test_tenant_without_created_at_name_or_tags():
    tenant = SchemasTransformerV1().transform_tenant(TenantInfoDocument(tenant_id="T1", stores=[]))

    assert tenant.tenant_id == "T1"
    assert tenant.tenant_name is None
    assert tenant.tags is None
    assert tenant.entry_datetime is None


def test_tenant_with_null_stores_reads_as_none():
    tenant = SchemasTransformerV1().transform_tenant(
        TenantInfoDocument(tenant_id="T1", tenant_name="n", tags=[], stores=None)
    )

    assert tenant.stores == []


def test_store_without_created_at():
    store = SchemasTransformerV1().transform_store(StoreInfo(store_code="S1"))

    assert store.store_code == "S1"
    assert store.store_name is None
    assert store.entry_datetime is None


def test_terminal_with_only_its_identity():
    terminal = SchemasTransformerV1().transform_terminal(
        TerminalInfoDocument(tenant_id="T1", store_code="S1", terminal_no=1, terminal_id="T1-S1-1")
    )

    assert terminal.terminal_id == "T1-S1-1"
    assert terminal.description is None
    assert terminal.function_mode is None
    assert terminal.status is None
    assert terminal.open_counter is None
    assert terminal.business_counter is None
    assert terminal.entry_datetime is None
