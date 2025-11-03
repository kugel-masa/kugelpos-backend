# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Any, Dict, List
import logging

from kugel_common.utils.misc import get_app_time_str

from app.models.repositories.tranlog_repository import TranlogRepository
from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository
from app.models.repositories.open_close_log_repository import OpenCloseLogRepository
from app.models.repositories.category_master_web_repository import CategoryMasterWebRepository
from app.config.settings import Settings
from app.models.documents.category_report_document import CategoryReportDocument
from app.enums.transaction_type import TransactionType
from app.services.report_plugin_interface import IReportPlugin
from app.services.plugins.category_report_receipt_data import CategoryReportReceiptData

logger = logging.getLogger(__name__)


class CategoryReportMaker(IReportPlugin):
    """
    Plugin class that generates category-based sales reports.
    Aggregates transaction data by product category to provide insights into sales performance.
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
            cash_in_out_log_repository: Cash in/out log repository (not used for category reports)
            open_close_log_repository: Open/close log repository (not used for category reports)
        """
        self.tran_repository = tran_repository
        self.cash_in_out_log_repository = cash_in_out_log_repository
        self.open_close_log_repository = open_close_log_repository
        
        # Initialize category master repository
        settings = Settings()
        self.category_repository = CategoryMasterWebRepository(
            tenant_id=tran_repository.tenant_id,
            master_data_base_url=settings.BASE_URL_MASTER_DATA
        )

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
        Generate a category report

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
            Category report document
        """
        
        # Validate date range if provided
        if business_date_from and business_date_to:
            if business_date_from > business_date_to:
                raise ValueError(f"Invalid date range: business_date_from ({business_date_from}) is after business_date_to ({business_date_to})")

        # Create pipeline for retrieving category report data
        pipeline = self._create_pipeline_for_category_report(
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
        logger.info(f"Category report pipeline: {pipeline}")

        # Retrieve data from transaction log collection using the pipeline
        category_results = await self.tran_repository.execute_pipeline(pipeline)
        logger.info(f"Category report results: {category_results}")

        # Fetch category names from master data
        try:
            logger.info(f"Fetching category names from master data service...")
            category_names = await self.category_repository.get_categories()
            logger.info(f"Successfully fetched {len(category_names)} categories: {category_names}")
        except Exception as e:
            logger.error(f"Failed to fetch category names: {e}", exc_info=True)
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Will use category codes as names (fallback)")
            category_names = {}
        
        # Create category report items
        logger.debug("Creating category items...")
        categories = self._create_category_items(category_results, category_names)
        logger.debug(f"Created {len(categories)} category items")
        
        # Calculate totals
        logger.debug("Calculating totals...")
        total_gross_amount = sum(cat.gross_amount for cat in categories)
        total_discount_amount = sum(cat.discount_amount for cat in categories)
        total_net_amount = sum(cat.net_amount for cat in categories)
        total_quantity = sum(cat.quantity for cat in categories)
        total_discount_quantity = sum(cat.discount_quantity for cat in categories)
        total_transaction_count = sum(cat.transaction_count for cat in categories)
        logger.debug("Totals calculated successfully")

        # Create category report document
        logger.debug("Creating CategoryReportDocument...")
        logger.debug(f"report_scope type: {type(report_scope)}, value: {report_scope}")
        logger.debug(f"report_type type: {type(report_type)}, value: {report_type}")
        try:
            return_doc = CategoryReportDocument(
                tenant_id=self.tran_repository.tenant_id,
                store_code=store_code,
                store_name=store_code,  # HACK: Store name is not included in data model
                terminal_no=terminal_no,
                business_date=business_date if not business_date_from else None,
                business_date_from=business_date_from,
                business_date_to=business_date_to,
                open_counter=open_counter,
                business_counter=business_counter,
                report_scope=report_scope,
                report_type=report_type,
                categories=categories,
                total_gross_amount=total_gross_amount,
                total_discount_amount=total_discount_amount,
                total_net_amount=total_net_amount,
                total_quantity=total_quantity,
                total_discount_quantity=total_discount_quantity,
                total_transaction_count=total_transaction_count,
                generate_date_time=get_app_time_str(),
                staff=None,  # HACK: Staff information is not included in data model
            )
            logger.debug("CategoryReportDocument created successfully")
        except Exception as e:
            logger.error(f"Error creating CategoryReportDocument: {e}", exc_info=True)
            raise

        # Create receipt data
        try:
            logger.debug("Creating CategoryReportReceiptData generator...")
            receipt_data_generator = CategoryReportReceiptData("Category Report", 32)
            logger.debug("Calling make_receipt_data...")
            logger.debug(f"return_doc type: {type(return_doc)}")
            logger.debug(f"return_doc.report_scope: {return_doc.report_scope}")
            logger.debug(f"return_doc.report_type: {return_doc.report_type}")
            receipt_data = receipt_data_generator.make_receipt_data(return_doc)
            logger.debug("make_receipt_data completed")
            return_doc.receipt_text = receipt_data.receipt_text
            return_doc.journal_text = receipt_data.journal_text
            logger.debug("Receipt data assigned to document")
        except Exception as e:
            logger.error(f"Error creating receipt data: {e}", exc_info=True)
            raise

        logger.info(f"Category report document created successfully")
        return return_doc

    def _create_pipeline_for_category_report(
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
        Create MongoDB pipeline for retrieving category report data

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
            # Date range filter
            match_dict["business_date"] = {
                "$gte": business_date_from,
                "$lte": business_date_to
            }
        elif business_date:
            # Single date filter
            match_dict["business_date"] = business_date

        # Add optional filters
        if terminal_no is not None:
            match_dict["terminal_no"] = terminal_no
        if open_counter is not None:
            match_dict["open_counter"] = open_counter

        # Create pipeline
        pipeline = [
            {"$match": match_dict},
            # Unwind line items to process each item separately
            {"$unwind": "$line_items"},
            # Project necessary fields
            {
                "$project": {
                    "transaction_type": 1,
                    "category_code": "$line_items.category_code",
                    "quantity": "$line_items.quantity",
                    "amount": "$line_items.amount",
                    "line_item_discounts": {
                        "$ifNull": [
                            {"$sum": "$line_items.discounts.discount_amount"},
                            0
                        ]
                    },
                    "allocated_discounts": {
                        "$ifNull": [
                            {"$sum": "$line_items.discounts_allocated.discount_amount"},
                            0
                        ]
                    },
                    "has_discount": {
                        "$cond": [
                            {
                                "$or": [
                                    {"$gt": [{"$sum": "$line_items.discounts.discount_amount"}, 0]},
                                    {"$gt": [{"$sum": "$line_items.discounts_allocated.discount_amount"}, 0]}
                                ]
                            },
                            1,
                            0
                        ]
                    }
                }
            },
            # Group by category
            {
                "$group": {
                    "_id": "$category_code",
                    "transactions": {
                        "$push": {
                            "transaction_type": "$transaction_type",
                            "quantity": "$quantity",
                            "amount": "$amount",
                            "line_item_discounts": "$line_item_discounts",
                            "allocated_discounts": "$allocated_discounts",
                            "has_discount": "$has_discount"
                        }
                    }
                }
            },
            # Calculate aggregates
            {
                "$project": {
                    "category_code": "$_id",
                    "gross_amount": {
                        "$sum": {
                            "$map": {
                                "input": "$transactions",
                                "as": "t",
                                "in": {
                                    "$multiply": [
                                        "$$t.amount",
                                        {"$cond": [
                                            {"$in": ["$$t.transaction_type", [TransactionType.NormalSales.value, TransactionType.VoidReturn.value]]},
                                            1,
                                            -1
                                        ]}
                                    ]
                                }
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
                                        {"$add": ["$$t.line_item_discounts", "$$t.allocated_discounts"]},
                                        {"$cond": [
                                            {"$in": ["$$t.transaction_type", [TransactionType.NormalSales.value, TransactionType.VoidReturn.value]]},
                                            1,
                                            -1
                                        ]}
                                    ]
                                }
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
                                        {"$cond": [
                                            {"$in": ["$$t.transaction_type", [TransactionType.NormalSales.value, TransactionType.VoidReturn.value]]},
                                            1,
                                            -1
                                        ]}
                                    ]
                                }
                            }
                        }
                    },
                    "discount_quantity": {
                        "$sum": {
                            "$map": {
                                "input": "$transactions",
                                "as": "t",
                                "in": {
                                    "$multiply": [
                                        {"$multiply": ["$$t.quantity", "$$t.has_discount"]},
                                        {"$cond": [
                                            {"$in": ["$$t.transaction_type", [TransactionType.NormalSales.value, TransactionType.VoidReturn.value]]},
                                            1,
                                            -1
                                        ]}
                                    ]
                                }
                            }
                        }
                    },
                    "transaction_count": {"$size": "$transactions"}
                }
            },
            # Calculate net amount
            {
                "$project": {
                    "category_code": 1,
                    "gross_amount": 1,
                    "discount_amount": 1,
                    "net_amount": {"$subtract": ["$gross_amount", "$discount_amount"]},
                    "quantity": 1,
                    "discount_quantity": 1,
                    "transaction_count": 1
                }
            }
        ]

        # Add sort stage (if sort is specified)
        if sort:
            sort_dict = {field: direction for field, direction in sort}
            pipeline.append({"$sort": sort_dict})
        else:
            # Default sort by category code
            pipeline.append({"$sort": {"category_code": 1}})

        # Add pagination stage
        if page > 1:
            pipeline.append({"$skip": (page - 1) * limit})
        pipeline.append({"$limit": limit})

        return pipeline

    def _create_category_items(self, results: list[dict], category_names: dict[str, str]) -> list[CategoryReportDocument.CategoryReportItem]:
        """
        Create category report items from aggregation results

        Args:
            results: Aggregation pipeline results
            category_names: Mapping of category codes to names

        Returns:
            List of CategoryReportItem objects
        """
        categories = []
        
        try:
            for result in results:
                category_code = result.get("category_code", "")
                # Use category name from master data, or code if not found
                category_name = category_names.get(category_code, category_code)
                
                logger.debug(f"Creating CategoryReportItem: code={category_code}, name={category_name}")
                category_item = CategoryReportDocument.CategoryReportItem(
                    category_code=category_code,
                    category_name=category_name,
                    gross_amount=result.get("gross_amount", 0.0),
                    discount_amount=result.get("discount_amount", 0.0),
                    net_amount=result.get("net_amount", 0.0),
                    quantity=result.get("quantity", 0),
                    discount_quantity=result.get("discount_quantity", 0),
                    transaction_count=result.get("transaction_count", 0)
                )
                categories.append(category_item)
        except Exception as e:
            logger.error(f"Error creating CategoryReportItem: {e}", exc_info=True)
            raise
        
        return categories