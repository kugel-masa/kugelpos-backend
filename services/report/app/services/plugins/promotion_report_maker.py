# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Any, Dict, List
import logging

from kugel_common.utils.misc import get_app_time_str

from app.models.repositories.tranlog_repository import TranlogRepository
from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository
from app.models.repositories.open_close_log_repository import OpenCloseLogRepository
from app.models.documents.promotion_report_document import PromotionReportDocument
from app.enums.transaction_type import TransactionType
from app.services.report_plugin_interface import IReportPlugin

logger = logging.getLogger(__name__)


class PromotionReportMaker(IReportPlugin):
    """
    Plugin class that generates promotion performance reports.
    Aggregates transaction data by promotion code to provide insights into promotion effectiveness.
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
            cash_in_out_log_repository: Cash in/out log repository (not used for promotion reports)
            open_close_log_repository: Open/close log repository (not used for promotion reports)
        """
        self.tran_repository = tran_repository
        self.cash_in_out_log_repository = cash_in_out_log_repository
        self.open_close_log_repository = open_close_log_repository

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
    ) -> dict[str, Any]:
        """
        Generate a promotion performance report

        Args:
            store_code: Store code
            business_date: Business date (single date or None for date range)
            open_counter: Open counter
            terminal_no: Terminal number
            business_counter: Business counter
            report_scope: Report scope ("flash"=preliminary, "daily"=settlement)
            report_type: Report type
            limit: Data retrieval limit
            page: Page number
            sort: Sort conditions
            business_date_from: Start date for date range reports
            business_date_to: End date for date range reports

        Returns:
            Promotion report document
        """

        # Validate date range if provided
        if business_date_from and business_date_to:
            if business_date_from > business_date_to:
                raise ValueError(
                    f"Invalid date range: business_date_from ({business_date_from}) "
                    f"is after business_date_to ({business_date_to})"
                )

        # Create pipeline for retrieving promotion report data
        pipeline = self._create_pipeline_for_promotion_report(
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
        logger.info(f"Promotion report pipeline: {pipeline}")

        # Retrieve data from transaction log collection using the pipeline
        promotion_results = await self.tran_repository.execute_pipeline(pipeline)
        logger.info(f"Promotion report results: {promotion_results}")

        # Create promotion report items
        promotions = self._create_promotion_items(promotion_results)
        logger.debug(f"Created {len(promotions)} promotion items")

        # Calculate totals
        total_gross_amount = sum(promo.gross_amount for promo in promotions)
        total_discount_amount = sum(promo.discount_amount for promo in promotions)
        total_net_amount = sum(promo.net_amount for promo in promotions)
        total_quantity = sum(promo.quantity for promo in promotions)
        total_transaction_count = sum(promo.transaction_count for promo in promotions)

        # Create promotion report document
        return_doc = PromotionReportDocument(
            tenant_id=self.tran_repository.tenant_id,
            store_code=store_code,
            store_name=store_code,  # Store name is not included in data model
            terminal_no=terminal_no,
            business_date=business_date if not business_date_from else None,
            business_date_from=business_date_from,
            business_date_to=business_date_to,
            open_counter=open_counter,
            business_counter=business_counter,
            report_scope=report_scope,
            report_type=report_type,
            promotions=promotions,
            total_gross_amount=total_gross_amount,
            total_discount_amount=total_discount_amount,
            total_net_amount=total_net_amount,
            total_quantity=total_quantity,
            total_transaction_count=total_transaction_count,
            generate_date_time=get_app_time_str(),
            staff=None,
        )

        # Create simple receipt text (no fancy formatting for now)
        receipt_lines = [
            "=== PROMOTION REPORT ===",
            f"Store: {store_code}",
            f"Date: {business_date or f'{business_date_from} - {business_date_to}'}",
            "",
            "Promotion Performance:",
            "-" * 40,
        ]
        for promo in promotions:
            receipt_lines.append(f"{promo.promotion_code}: {promo.quantity} items, -{promo.discount_amount:.0f}")
        receipt_lines.extend([
            "-" * 40,
            f"Total Discount: -{total_discount_amount:.0f}",
            f"Total Items: {total_quantity}",
            "",
        ])
        return_doc.receipt_text = "\n".join(receipt_lines)
        return_doc.journal_text = return_doc.receipt_text

        logger.info("Promotion report document created successfully")
        return return_doc

    def _create_pipeline_for_promotion_report(
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
        Create MongoDB pipeline for retrieving promotion report data

        Args:
            store_code: Store code
            terminal_no: Terminal number
            business_date: Business date (single date or None for date range)
            open_counter: Open counter
            limit: Data retrieval limit
            page: Page number
            sort: Sort conditions
            business_date_from: Start date for date range reports
            business_date_to: End date for date range reports

        Returns:
            MongoDB pipeline
        """
        # Create match stage conditions
        match_dict = {
            "tenant_id": self.tran_repository.tenant_id,
            "store_code": store_code,
            "sales.is_cancelled": False,
        }

        # Add date filter
        if business_date_from and business_date_to:
            match_dict["business_date"] = {
                "$gte": business_date_from,
                "$lte": business_date_to,
            }
        elif business_date:
            match_dict["business_date"] = business_date

        # Add optional filters
        if terminal_no is not None:
            match_dict["terminal_no"] = terminal_no
        if open_counter is not None:
            match_dict["open_counter"] = open_counter

        # Create pipeline
        pipeline = [
            {"$match": match_dict},
            # Unwind line items
            {"$unwind": "$line_items"},
            # Unwind discounts on line items
            {"$unwind": {"path": "$line_items.discounts", "preserveNullAndEmptyArrays": False}},
            # Filter to only promotion discounts (those with promotion_code)
            {
                "$match": {
                    "line_items.discounts.promotion_code": {"$exists": True, "$ne": None},
                }
            },
            # Project necessary fields
            {
                "$project": {
                    "transaction_no": 1,
                    "transaction_type": 1,
                    "promotion_code": "$line_items.discounts.promotion_code",
                    "promotion_type": "$line_items.discounts.promotion_type",
                    "quantity": "$line_items.quantity",
                    "amount": "$line_items.amount",
                    "discount_amount": "$line_items.discounts.discount_amount",
                }
            },
            # Group by promotion_code
            {
                "$group": {
                    "_id": {
                        "promotion_code": "$promotion_code",
                        "promotion_type": "$promotion_type",
                    },
                    "transactions": {
                        "$push": {
                            "transaction_no": "$transaction_no",
                            "transaction_type": "$transaction_type",
                            "quantity": "$quantity",
                            "amount": "$amount",
                            "discount_amount": "$discount_amount",
                        }
                    },
                }
            },
            # Calculate aggregates
            {
                "$project": {
                    "promotion_code": "$_id.promotion_code",
                    "promotion_type": "$_id.promotion_type",
                    "gross_amount": {
                        "$sum": {
                            "$map": {
                                "input": "$transactions",
                                "as": "t",
                                "in": {
                                    "$multiply": [
                                        "$$t.amount",
                                        {
                                            "$cond": [
                                                {
                                                    "$in": [
                                                        "$$t.transaction_type",
                                                        [
                                                            TransactionType.NormalSales.value,
                                                            TransactionType.VoidReturn.value,
                                                        ],
                                                    ]
                                                },
                                                1,
                                                -1,
                                            ]
                                        },
                                    ]
                                },
                            }
                        }
                    },
                    "discount_amount": {
                        "$sum": {
                            "$map": {
                                "input": "$transactions",
                                "as": "t",
                                "in": {
                                    "$multiply": [
                                        "$$t.discount_amount",
                                        {
                                            "$cond": [
                                                {
                                                    "$in": [
                                                        "$$t.transaction_type",
                                                        [
                                                            TransactionType.NormalSales.value,
                                                            TransactionType.VoidReturn.value,
                                                        ],
                                                    ]
                                                },
                                                1,
                                                -1,
                                            ]
                                        },
                                    ]
                                },
                            }
                        }
                    },
                    "quantity": {
                        "$sum": {
                            "$map": {
                                "input": "$transactions",
                                "as": "t",
                                "in": {
                                    "$multiply": [
                                        "$$t.quantity",
                                        {
                                            "$cond": [
                                                {
                                                    "$in": [
                                                        "$$t.transaction_type",
                                                        [
                                                            TransactionType.NormalSales.value,
                                                            TransactionType.VoidReturn.value,
                                                        ],
                                                    ]
                                                },
                                                1,
                                                -1,
                                            ]
                                        },
                                    ]
                                },
                            }
                        }
                    },
                    "transaction_count": {
                        "$size": {
                            "$setUnion": [
                                {"$map": {"input": "$transactions", "as": "t", "in": "$$t.transaction_no"}}
                            ]
                        }
                    },
                }
            },
            # Calculate net amount
            {
                "$project": {
                    "promotion_code": 1,
                    "promotion_type": 1,
                    "gross_amount": 1,
                    "discount_amount": 1,
                    "net_amount": {"$subtract": ["$gross_amount", "$discount_amount"]},
                    "quantity": 1,
                    "transaction_count": 1,
                }
            },
        ]

        # Add sort stage
        if sort:
            sort_dict = {field: direction for field, direction in sort}
            pipeline.append({"$sort": sort_dict})
        else:
            # Default sort by discount amount (highest first)
            pipeline.append({"$sort": {"discount_amount": -1}})

        # Add pagination stage
        if page > 1:
            pipeline.append({"$skip": (page - 1) * limit})
        pipeline.append({"$limit": limit})

        return pipeline

    def _create_promotion_items(
        self, results: list[dict]
    ) -> list[PromotionReportDocument.PromotionReportItem]:
        """
        Create promotion report items from aggregation results

        Args:
            results: Aggregation pipeline results

        Returns:
            List of PromotionReportItem objects
        """
        promotions = []

        for result in results:
            promotion_item = PromotionReportDocument.PromotionReportItem(
                promotion_code=result.get("promotion_code", ""),
                promotion_type=result.get("promotion_type", ""),
                gross_amount=result.get("gross_amount", 0.0),
                discount_amount=result.get("discount_amount", 0.0),
                net_amount=result.get("net_amount", 0.0),
                quantity=result.get("quantity", 0),
                transaction_count=result.get("transaction_count", 0),
            )
            promotions.append(promotion_item)

        return promotions
