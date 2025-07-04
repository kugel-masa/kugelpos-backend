from typing import Optional
from kugel_common.models.documents.base_tranlog import BaseTransaction


class TranlogDocument(BaseTransaction):
    """
    Transaction log document model for POS transactions.

    This class extends BaseTransaction to provide a comprehensive data structure for storing
    all transaction-related information, including sales details, line items, payments,
    taxes, and discounts. It serves as the foundation for the transaction logging system.
    """

    invoice_issue_no: Optional[str] = None
