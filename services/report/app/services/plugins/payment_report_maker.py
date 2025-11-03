# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Any, Dict, List
import logging
import os
from datetime import datetime
import pytz

from kugel_common.utils.http_client_helper import get_service_client
from kugel_common.utils.service_auth import create_service_token
from app.models.repositories.tranlog_repository import TranlogRepository
from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository
from app.models.repositories.open_close_log_repository import OpenCloseLogRepository
from app.models.documents.payment_report_document import PaymentReportDocument
from app.enums.transaction_type import TransactionType
from app.services.report_plugin_interface import IReportPlugin
from app.services.plugins.payment_report_receipt_data import PaymentReportReceiptData
from app.config.settings import Settings

logger = logging.getLogger(__name__)


class PaymentReportMaker(IReportPlugin):
    """
    Plugin class that generates payment method reports.
    Aggregates transaction data by payment method to show usage statistics and composition ratios.
    Implements the IReportPlugin interface.
    """

    def __init__(
        self,
        tran_repository: TranlogRepository,
        cash_in_out_log_repository: CashInOutLogRepository,
        open_close_log_repository: OpenCloseLogRepository,
    ):
        """
        Constructor

        Args:
            tran_repository: Transaction log repository
            cash_in_out_log_repository: Cash in/out log repository (not used but kept for consistency)
            open_close_log_repository: Open/close log repository (not used but kept for consistency)
        """
        self.tran_repository = tran_repository
        self.cash_in_out_log_repository = cash_in_out_log_repository
        self.open_close_log_repository = open_close_log_repository
        
        # Initialize settings for master data URL
        self.settings = Settings()

    async def generate_report(
        self,
        store_code: str,
        terminal_no: int,
        business_counter: int,
        business_date: str,
        open_counter: int,
        report_scope: str,
        report_type: str,
        limit: int,
        page: int,
        sort: list[tuple[str, int]],
        business_date_from: str = None,
        business_date_to: str = None,
    ) -> PaymentReportDocument:
        """
        Generate a payment method report

        Args:
            store_code: Store code
            terminal_no: Terminal number
            business_counter: Business counter
            business_date: Business date (used when date range not specified)
            open_counter: Open counter
            report_scope: Report scope ("flash"=preliminary, "daily"=settlement)
            report_type: Report type
            limit: Data retrieval limit
            page: Page number
            sort: Sort conditions
            business_date_from: Start date for date range (optional)
            business_date_to: End date for date range (optional)

        Returns:
            Payment report document with payment summary and totals
        """

        # Validate date range if both dates are provided
        if business_date_from and business_date_to:
            if business_date_from > business_date_to:
                raise ValueError(f"Invalid date range: business_date_from ({business_date_from}) is after business_date_to ({business_date_to})")

        # Fetch payment master data from master-data service
        payment_master_map = await self._fetch_payment_master(self.tran_repository.tenant_id, store_code)
        logger.info(f"Fetched payment master data: {payment_master_map}")

        # Create pipeline for retrieving payment report data
        pipeline = self._create_pipeline_for_payment_report(
            store_code=store_code,
            terminal_no=terminal_no,
            business_date=business_date,
            open_counter=open_counter,
            limit=limit,
            page=page,
            sort=sort,
            business_date_from=business_date_from,
            business_date_to=business_date_to,
        )
        logger.info(f"Payment report pipeline: {pipeline}")

        # Retrieve data from transaction log collection using the pipeline
        tran_results = await self.tran_repository.execute_pipeline(pipeline)
        logger.info(f"Payment report results: {tran_results}")

        # Aggregate payment report data
        payment_summary = self._summarize_payment_report(tran_results, payment_master_map)
        logger.info(f"Payment summary: {payment_summary}")

        # Calculate totals and composition ratios
        total_amount = sum(p["amount"] for p in payment_summary)
        total_count = sum(p["count"] for p in payment_summary)

        # Add composition ratio to each payment
        for payment in payment_summary:
            if total_amount > 0:
                payment["ratio"] = round((payment["amount"] / total_amount) * 100, 2)
            else:
                payment["ratio"] = 0.0

        # Sort payment summary by amount descending
        payment_summary.sort(key=lambda x: x["amount"], reverse=True)

        # Create PaymentSummaryItem objects
        payment_summary_items = []
        for payment in payment_summary:
            payment_summary_items.append(
                PaymentReportDocument.PaymentSummaryItem(
                    payment_code=payment["payment_code"],
                    payment_name=payment["payment_name"],
                    count=payment["count"],
                    amount=payment["amount"],
                    ratio=payment["ratio"]
                )
            )

        # Create PaymentTotal object
        payment_total = PaymentReportDocument.PaymentTotal(
            count=total_count,
            amount=total_amount
        )

        # Get current datetime for generate_date_time
        jst = pytz.timezone('Asia/Tokyo')
        generate_date_time = datetime.now(jst).isoformat()

        # Create PaymentReportDocument
        report_doc = PaymentReportDocument(
            tenant_id=self.tran_repository.tenant_id,
            store_code=store_code,
            terminal_no=terminal_no,
            business_date=business_date,
            business_date_from=business_date_from,
            business_date_to=business_date_to,
            open_counter=open_counter,
            business_counter=business_counter,
            report_scope=report_scope,
            report_type=report_type,
            payment_summary=payment_summary_items,
            total=payment_total,
            generate_date_time=generate_date_time
        )
        
        # Generate receipt text
        try:
            receipt_data = PaymentReportReceiptData("Payment Report", 32).make_receipt_data(report_doc)
            report_doc.receipt_text = receipt_data.receipt_text
            report_doc.journal_text = receipt_data.journal_text
            logger.info(f"Payment report document created with receipt text")
        except Exception as e:
            logger.warning(f"Failed to generate receipt text: {e}")
            # Continue without receipt text
            report_doc.receipt_text = None
            report_doc.journal_text = None
        
        return report_doc

    async def _fetch_payment_master(self, tenant_id: str, store_code: str) -> dict[str, str]:
        """
        Fetch payment master data from master-data service

        Args:
            tenant_id: Tenant ID
            store_code: Store code

        Returns:
            Dictionary mapping payment_code to payment description
        """
        payment_map = {}
        
        try:
            # Use BASE_URL_MASTER_DATA from settings (consistent with other report makers)
            base_url = self.settings.BASE_URL_MASTER_DATA
            
            # Call master-data API to get all payment methods
            # Note: In production, master-data is accessed via service mesh without auth
            # In local testing, we skip auth and use default payment mapping
            async with get_service_client("master-data") as client:
                # Create service token for authentication
                service_token = create_service_token(tenant_id, "report")
                headers = {
                    "Authorization": f"Bearer {service_token}",
                    "X-Tenant-ID": tenant_id,
                    "X-Store-Code": store_code
                }
                    
                # HttpClientHelper.get() returns the JSON data directly, not a response object
                data = await client.get(
                    f"{base_url}/tenants/{tenant_id}/payments",
                    params={"limit": 100, "page": 1},
                    headers=headers
                )
                
                if data.get("success") and data.get("data"):
                    for payment in data["data"]:
                        payment_code = payment.get("paymentCode")  # Changed from payment_code to paymentCode
                        description = payment.get("description", f"Payment {payment_code}")
                        if payment_code:
                            payment_map[payment_code] = description
                else:
                    # If no data or API error, use default mapping for testing
                    logger.warning(f"Failed to fetch payment master data: {data.get('message', 'No data available')}")
                    payment_map = {
                        "01": "Cash",
                        "11": "Cashless", 
                        "12": "Others",
                    }
                    
        except Exception as e:
            logger.error(f"Error fetching payment master data: {e}")
            # Return default mapping if API call fails
            payment_map = {
                "01": "Cash",
                "11": "Cashless",
                "12": "Others",
            }
        
        return payment_map

    def _create_pipeline_for_payment_report(
        self,
        store_code: str,
        terminal_no: int,
        business_date: str,
        open_counter: int,
        limit: int,
        page: int,
        sort: list[tuple[str, int]],
        business_date_from: str = None,
        business_date_to: str = None,
    ) -> List[Dict[str, Any]]:
        """
        Create MongoDB pipeline for retrieving payment report data

        Args:
            store_code: Store code
            terminal_no: Terminal number
            business_date: Business date (used when date range not specified)
            open_counter: Open counter
            limit: Data retrieval limit
            page: Page number
            sort: Sort conditions
            business_date_from: Start date for date range (optional)
            business_date_to: End date for date range (optional)

        Returns:
            MongoDB pipeline
        """
        # Create match stage conditions
        match_dict = {
            "tenant_id": self.tran_repository.tenant_id,
            "store_code": store_code,
            "sales.is_cancelled": False,  # Exclude cancelled transactions
        }
        
        # Handle date range or single date
        if business_date_from and business_date_to:
            # Use date range
            match_dict["business_date"] = {
                "$gte": business_date_from,
                "$lte": business_date_to
            }
        else:
            # Use single date
            match_dict["business_date"] = business_date

        # Add optional filters
        if terminal_no is not None:
            match_dict["terminal_no"] = terminal_no
        if open_counter is not None:
            match_dict["open_counter"] = open_counter

        # Create pipeline
        pipeline = [
            # Match stage: filter transactions
            {"$match": match_dict},
            
            # Unwind payments array to process each payment separately
            {"$unwind": "$payments"},
            
            # Group by payment code and transaction type
            # CRITICAL FIX: Use $addToSet to collect unique transaction identifiers, then count with $size
            # This prevents counting split payments multiple times
            # Note: transaction_no is only unique within tenant_id + store_code + terminal_no
            {
                "$group": {
                    "_id": {
                        "payment_code": "$payments.payment_code",
                        "transaction_type": "$transaction_type"
                    },
                    "amount": {"$sum": "$payments.amount"},
                    "unique_transactions": {
                        "$addToSet": {
                            "tenant_id": "$tenant_id",
                            "store_code": "$store_code",
                            "terminal_no": "$terminal_no",
                            "transaction_no": "$transaction_no"
                        }
                    }
                }
            },

            # Add count field based on unique transactions
            {
                "$addFields": {
                    "count": {"$size": "$unique_transactions"}  # Count unique transactions, not payments
                }
            },
            
            # Group by payment code to aggregate across transaction types
            {
                "$group": {
                    "_id": "$_id.payment_code",
                    "transactions": {
                        "$push": {
                            "transaction_type": "$_id.transaction_type",
                            "amount": "$amount",
                            "count": "$count"
                        }
                    }
                }
            },
            
            # Sort by payment code
            {"$sort": {"_id": 1}}
        ]

        return pipeline

    def _summarize_payment_report(
        self, results: list[dict], payment_master_map: dict[str, str]
    ) -> list[dict[str, Any]]:
        """
        Aggregate payment report results

        Args:
            results: Payment report retrieval results from pipeline
            payment_master_map: Dictionary mapping payment_code to description

        Returns:
            List of aggregated payment report results
        """
        payment_summary = []
        
        for result in results:
            payment_code = result["_id"]
            total_amount = 0
            total_count = 0
            
            # Process each transaction type for this payment code
            for trans in result.get("transactions", []):
                transaction_type = trans["transaction_type"]
                factor = self._return_factor(transaction_type)
                total_amount += trans["amount"] * factor
                total_count += trans["count"] * factor
            
            # Get payment name from master data
            payment_name = payment_master_map.get(payment_code, f"Payment {payment_code}")
            
            payment_summary.append({
                "payment_code": payment_code,
                "payment_name": payment_name,
                "count": total_count,
                "amount": total_amount
            })
        
        return payment_summary

    def _return_factor(self, transaction_type: int) -> int:
        """
        Return the factor for aggregation based on transaction type
        Normal transactions and void returns are 1, return transactions and void sales are -1

        Args:
            transaction_type: Transaction type

        Returns:
            Aggregation factor (1 or -1)

        Raises:
            ValueError: If an invalid transaction type is specified
        """
        match transaction_type:
            case TransactionType.NormalSales.value | TransactionType.VoidReturn.value:
                logger.debug(f"Transaction type: {transaction_type} Factor: 1")
                return 1
            case TransactionType.ReturnSales.value | TransactionType.VoidSales.value:
                logger.debug(f"Transaction type: {transaction_type} Factor: -1")
                return -1
            case _:
                logger.error(f"Invalid transaction type: {transaction_type}")
                raise ValueError(f"Invalid transaction type: {transaction_type}")