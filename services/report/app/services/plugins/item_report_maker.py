# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Any, Dict, List
import logging

from kugel_common.utils.misc import get_app_time_str

from app.models.repositories.tranlog_repository import TranlogRepository
from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository
from app.models.repositories.open_close_log_repository import OpenCloseLogRepository
from app.models.repositories.category_master_web_repository import CategoryMasterWebRepository
from app.models.repositories.item_master_web_repository import ItemMasterWebRepository
from app.config.settings import Settings
from app.models.documents.item_report_document import ItemReportDocument
from app.enums.transaction_type import TransactionType
from app.services.report_plugin_interface import IReportPlugin
from app.services.plugins.item_report_receipt_data import ItemReportReceiptData

logger = logging.getLogger(__name__)


class ItemReportMaker(IReportPlugin):
    """
    Plugin class that generates item-based sales reports grouped by categories.
    Aggregates transaction data by individual items while maintaining category organization.
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
            cash_in_out_log_repository: Cash in/out log repository (not used for item reports)
            open_close_log_repository: Open/close log repository (not used for item reports)
        """
        self.tran_repository = tran_repository
        self.cash_in_out_log_repository = cash_in_out_log_repository
        self.open_close_log_repository = open_close_log_repository
        
        # Initialize master data repositories
        settings = Settings()
        self.category_repository = CategoryMasterWebRepository(
            tenant_id=tran_repository.tenant_id,
            master_data_base_url=settings.BASE_URL_MASTER_DATA
        )
        self.item_repository = ItemMasterWebRepository(
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
        Generate an item report

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
            Item report document
        """
        
        # Validate date range if provided
        if business_date_from and business_date_to:
            if business_date_from > business_date_to:
                raise ValueError(f"Invalid date range: business_date_from ({business_date_from}) is after business_date_to ({business_date_to})")

        # Create pipeline for retrieving item report data
        pipeline = self._create_pipeline_for_item_report(
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
        logger.info(f"Item report pipeline: {pipeline}")

        # Retrieve data from transaction log collection using the pipeline
        item_results = await self.tran_repository.execute_pipeline(pipeline)
        logger.info(f"Item report results count: {len(item_results)}")

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
        
        # Fetch item names from master data
        try:
            # Extract unique item codes from results
            item_codes = list(set(result.get("item_code", "") for result in item_results if result.get("item_code")))
            if item_codes:
                item_details = await self.item_repository.get_items(item_codes)
            else:
                item_details = {}
        except Exception as e:
            logger.warning(f"Failed to fetch item names: {e}")
            item_details = {}
        
        # Create category with items structure
        logger.debug("Creating category with items structure...")
        categories_with_items = self._create_categories_with_items(item_results, category_names, item_details)
        logger.debug(f"Created {len(categories_with_items)} categories with items")
        
        # Calculate totals
        logger.debug("Calculating totals...")
        total_gross_amount = sum(cat.category_total_gross_amount for cat in categories_with_items)
        total_discount_amount = sum(cat.category_total_discount_amount for cat in categories_with_items)
        total_net_amount = sum(cat.category_total_net_amount for cat in categories_with_items)
        total_quantity = sum(cat.category_total_quantity for cat in categories_with_items)
        total_discount_quantity = sum(cat.category_total_discount_quantity for cat in categories_with_items)
        total_transaction_count = sum(cat.category_total_transaction_count for cat in categories_with_items)
        logger.debug("Totals calculated successfully")

        # Create item report document
        logger.debug("Creating ItemReportDocument...")
        try:
            return_doc = ItemReportDocument(
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
                categories=categories_with_items,
                total_gross_amount=total_gross_amount,
                total_discount_amount=total_discount_amount,
                total_net_amount=total_net_amount,
                total_quantity=total_quantity,
                total_discount_quantity=total_discount_quantity,
                total_transaction_count=total_transaction_count,
                generate_date_time=get_app_time_str(),
                staff=None,  # HACK: Staff information is not included in data model
            )
            logger.debug("ItemReportDocument created successfully")
        except Exception as e:
            logger.error(f"Error creating ItemReportDocument: {e}", exc_info=True)
            raise

        # Create receipt data
        try:
            logger.debug("Creating ItemReportReceiptData generator...")
            receipt_data_generator = ItemReportReceiptData("Item Report", 32)
            logger.debug("Calling make_receipt_data...")
            receipt_data = receipt_data_generator.make_receipt_data(return_doc)
            logger.debug("make_receipt_data completed")
            return_doc.receipt_text = receipt_data.receipt_text
            return_doc.journal_text = receipt_data.journal_text
            logger.debug("Receipt data assigned to document")
        except Exception as e:
            logger.error(f"Error creating receipt data: {e}", exc_info=True)
            raise

        logger.info(f"Item report document created successfully")
        return return_doc

    def _create_pipeline_for_item_report(
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
        Create MongoDB pipeline for retrieving item report data

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
                    "item_code": "$line_items.item_code",
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
            # Group by item code and category code
            {
                "$group": {
                    "_id": {
                        "item_code": "$item_code",
                        "category_code": "$category_code"
                    },
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
            # Calculate aggregates for each item
            {
                "$project": {
                    "item_code": "$_id.item_code",
                    "category_code": "$_id.category_code",
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
                    "item_code": 1,
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

        # Add sort stage (default sort by category_code then item_code)
        if sort:
            sort_dict = {field: direction for field, direction in sort}
            pipeline.append({"$sort": sort_dict})
        else:
            pipeline.append({"$sort": {"category_code": 1, "item_code": 1}})

        # Note: Pagination is applied after grouping by category in the main method
        # to ensure we get complete categories, not partial ones

        return pipeline

    def _create_categories_with_items(
        self, 
        results: list[dict], 
        category_names: dict[str, str],
        item_details: dict[str, dict[str, str]]
    ) -> list[ItemReportDocument.CategoryWithItems]:
        """
        Create categories with items structure from aggregation results

        Args:
            results: Aggregation pipeline results
            category_names: Mapping of category codes to names
            item_details: Mapping of item codes to item details (name and category_code)

        Returns:
            List of CategoryWithItems objects
        """
        # Return empty list if no results
        if not results:
            logger.debug("No results to process, returning empty categories list")
            return []
        
        # Group items by category
        categories_dict = {}
        
        try:
            for result in results:
                item_code = result.get("item_code", "")
                category_code = result.get("category_code", "")
                
                # Get item name from master data
                item_info = item_details.get(item_code, {})
                item_name = item_info.get("name", item_code)
                
                # Create item report item
                item = ItemReportDocument.ItemReportItem(
                    item_code=item_code,
                    item_name=item_name,
                    gross_amount=result.get("gross_amount", 0.0),
                    discount_amount=result.get("discount_amount", 0.0),
                    net_amount=result.get("net_amount", 0.0),
                    quantity=result.get("quantity", 0),
                    discount_quantity=result.get("discount_quantity", 0),
                    transaction_count=result.get("transaction_count", 0)
                )
                
                # Add item to appropriate category
                if category_code not in categories_dict:
                    categories_dict[category_code] = {
                        "category_name": category_names.get(category_code, category_code),
                        "items": []
                    }
                categories_dict[category_code]["items"].append(item)
                
        except Exception as e:
            logger.error(f"Error creating item report items: {e}", exc_info=True)
            raise
        
        # Create CategoryWithItems objects
        categories_with_items = []
        for category_code, category_data in sorted(categories_dict.items()):
            # Calculate category totals
            items = category_data["items"]
            category_total_gross_amount = sum(item.gross_amount for item in items)
            category_total_discount_amount = sum(item.discount_amount for item in items)
            category_total_net_amount = sum(item.net_amount for item in items)
            category_total_quantity = sum(item.quantity for item in items)
            category_total_discount_quantity = sum(item.discount_quantity for item in items)
            category_total_transaction_count = sum(item.transaction_count for item in items)
            
            # Sort items by item code within category
            items.sort(key=lambda x: x.item_code)
            
            category_with_items = ItemReportDocument.CategoryWithItems(
                category_code=category_code,
                category_name=category_data["category_name"],
                items=items,
                category_total_gross_amount=category_total_gross_amount,
                category_total_discount_amount=category_total_discount_amount,
                category_total_net_amount=category_total_net_amount,
                category_total_quantity=category_total_quantity,
                category_total_discount_quantity=category_total_discount_quantity,
                category_total_transaction_count=category_total_transaction_count
            )
            categories_with_items.append(category_with_items)
        
        return categories_with_items