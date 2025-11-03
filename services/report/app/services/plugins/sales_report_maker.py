# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Any, Dict, List
from abc import ABC, abstractmethod
import logging

from kugel_common.utils.misc import get_app_time_str

from app.models.repositories.tranlog_repository import TranlogRepository
from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository
from app.models.repositories.open_close_log_repository import OpenCloseLogRepository
from app.models.documents.sales_report_document import SalesReportDocument
from app.models.documents.cash_in_out_log import CashInOutLog
from app.models.documents.open_close_log import OpenCloseLog
from app.enums.transaction_type import TransactionType
from app.services.report_plugin_interface import IReportPlugin
from app.services.plugins.sales_report_receipt_data import SalesReportReceiptData

logger = logging.getLogger(__name__)


class SalesReportMaker(IReportPlugin):
    """
    Plugin class that generates sales reports.
    Aggregates data from transaction logs, cash in/out logs, and open/close logs to create sales reports.
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
            cash_in_out_log_repository: Cash in/out log repository
            open_close_log_repository: Open/close log repository
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
    ) -> dict[str, Any]:
        """
        Generate a sales report

        Args:
            store_code: Store code
            business_date: Business date
            open_counter: Open counter
            terminal_no: Terminal number
            business_counter: Business counter
            report_scope: Report scope ("flash"=preliminary, "daily"=settlement)
            report_type: Report type
            limit: Data retrieval limit
            page: Page number
            sort: Sort conditions

        Returns:
            Sales report document
        """

        # Create pipeline for retrieving sales report data
        pipeline = self._create_pipeline_for_sales_report(
            store_code=store_code,
            terminal_no=terminal_no,
            business_date=business_date,
            open_counter=open_counter,
            limit=limit,
            page=page,
            sort=sort,
        )
        logger.info(f"Sales report pipeline: {pipeline}")

        # Retrieve data from transaction log collection using the pipeline
        tran_results = await self.tran_repository.execute_pipeline(pipeline)
        logger.info(f"Sales report results: {tran_results}")

        # Aggregate sales report data
        summarized_tran_result = self._summarize_sales_report(tran_results)
        logger.info(f"Summarized sales report: {summarized_tran_result}")

        # Create filter for retrieving data from cash in/out log collection
        filter = {
            "tenant_id": self.cash_in_out_log_repository.tenant_id,
            "store_code": store_code,
            "business_date": business_date,
        }
        if terminal_no is not None:
            filter["terminal_no"] = terminal_no
        if open_counter is not None:
            filter["open_counter"] = open_counter

        # Retrieve cash in/out logs
        cash_results = await self.cash_in_out_log_repository.get_cash_in_out_logs(
            filter=filter, limit=limit, page=page, sort=sort
        )
        logger.info(f"Cash in/out log filter: {filter}")
        logger.info(f"Cash in/out log repository tenant_id: {self.cash_in_out_log_repository.tenant_id}")
        logger.info(f"Cash in/out log repository db name: {self.cash_in_out_log_repository.db.name}")
        logger.info(f"Cash in/out log results count: {len(cash_results.data)}")
        logger.info(
            f"Cash in/out log results: {[{'amount': c.amount, 'description': c.description, 'tenant_id': c.tenant_id} for c in cash_results.data]}"
        )
        cash_summary = self._summarize_cash_in_out_logs(cash_results.data)
        logger.info(f"Cash in/out log summary: {cash_summary}")

        # Retrieve open/close logs
        open_close_results = await self.open_close_log_repository.get_open_close_logs(
            store_code=store_code,
            business_date=business_date,
            terminal_no=terminal_no,
            open_counter=open_counter,
            limit=limit,
            page=page,
            sort=sort,
        )
        logger.debug(f"Open close log results: {open_close_results}")
        open_close_summary = self._summarize_open_close_logs(open_close_results.data)
        logger.info(f"Open close log summary: {open_close_summary}")

        # Aggregate payment amounts by cash
        cash_payments = self._summarize_payment(summarized_tran_result["payments"])
        logger.info(f"Payment amount summary by cash: {cash_payments}")

        # Create sales report document
        return_doc = SalesReportDocument(
            tenant_id=self.tran_repository.tenant_id,
            store_code=store_code,
            store_name=store_code,  # HACK: Store name is not included in data model
            terminal_no=terminal_no,
            business_date=business_date,
            open_counter=open_counter,
            business_counter=business_counter,
            report_scope=report_scope,
            report_type=report_type,
            sales_gross=self._make_sales_gross(tran_results),
            sales_net=self._make_sales_net(summarized_tran_result),
            discount_for_lineitems=self._make_discount_for_lineitem(summarized_tran_result),
            discount_for_subtotal=self._make_discount_for_subtotal(summarized_tran_result),
            returns=self._make_returns(tran_results),
            taxes=self._make_taxes(summarized_tran_result),
            payments=self._make_payments(summarized_tran_result),
            cash=self._make_cash(cash_summary, open_close_summary, cash_payments),
            generate_date_time=get_app_time_str(),
            staff=None,  # HACK: Staff information is not included in data model
        )

        # Create receipt data
        receipt_data = SalesReportReceiptData("Sales Report", 32).make_receipt_data(return_doc)
        return_doc.receipt_text = receipt_data.receipt_text
        return_doc.journal_text = receipt_data.journal_text

        logger.info(f"Sales report document: {return_doc}")
        return return_doc

    def _summarize_cash_in_out_logs(self, results: list[CashInOutLog]) -> dict[str, Any]:
        """
        Aggregate cash in/out logs

        Args:
            results: List of cash in/out logs

        Returns:
            Aggregated results of cash in/out logs
        """
        cash_in_count = sum([1 for cash in results if cash.amount > 0])
        cash_in_amount = sum([cash.amount for cash in results if cash.amount > 0])
        cash_out_count = sum([1 for cash in results if cash.amount < 0])
        cash_out_amount = sum([cash.amount for cash in results if cash.amount < 0])
        return {
            "cash_in_count": cash_in_count,
            "cash_in_amount": cash_in_amount,
            "cash_out_count": cash_out_count,
            "cash_out_amount": cash_out_amount,
        }

    def _summarize_open_close_logs(self, results: list[OpenCloseLog]) -> dict[str, Any]:
        """
        Aggregate open/close logs

        Args:
            results: List of open/close logs

        Returns:
            Aggregated results of open/close logs
        """
        initial_amount = sum(
            [open_close.terminal_info.initial_amount for open_close in results if open_close.operation == "open"]
        )
        physical_amount = sum(
            [open_close.terminal_info.physical_amount for open_close in results if open_close.operation == "close"]
        )

        return {"initial_amount": initial_amount, "physical_amount": physical_amount}

    def _summarize_payment(self, payments: list[dict[str, Any]]) -> dict[str, float]:
        """
        Aggregate payment information

        Args:
            payments: List of payment information

        Returns:
            Aggregated results of payment information (cash and cashless)
        """
        cash_payments = {"cash": 0, "cashless": 0}
        for payment in payments:
            if payment["payment_code"] == "01":  # Cash payment code
                cash_payments["cash"] += payment["amount"]
            else:
                cash_payments["cashless"] += payment["amount"]
        return cash_payments

    def _create_pipeline_for_sales_report(
        self,
        store_code: str,
        terminal_no: int,
        business_date: str,
        open_counter: int,
        limit: int,
        page: int,
        sort: list[tuple[str, int]],
    ) -> List[Dict[str, Any]]:
        """
        Create MongoDB pipeline for retrieving sales report data

        Args:
            store_code: Store code
            terminal_no: Terminal number
            business_date: Business date
            open_counter: Open counter
            limit: Data retrieval limit
            page: Page number
            sort: Sort conditions

        Returns:
            MongoDB pipeline
        """
        # Create match stage conditions
        match_dict = {
            "tenant_id": self.tran_repository.tenant_id,
            "store_code": store_code,
            "business_date": business_date,
            "sales.is_cancelled": False,
        }

        # Create project stage conditions
        project_dict = {
            "tenant_id": 1,
            "store_code": 1,
            "terminal_no": 1,
            "business_date": 1,
            "transaction_no": 1,  # CRITICAL: Required for intermediate grouping to prevent transaction merge
            "transaction_type": 1,
            "sales.total_amount": 1,
            "sales.total_amount_with_tax": 1,
            "sales.tax_amount": 1,
            "sales.total_quantity": 1,
            "sales.change_amount": 1,
            "sales.total_discount_amount": 1,
            "line_items_discount_amount": {
                "$sum": {
                    "$map": {
                        "input": "$line_items",
                        "as": "item",
                        "in": {
                            "$sum": {
                                "$map": {
                                    "input": "$$item.discounts",
                                    "as": "discount",
                                    "in": "$$discount.discount_amount",
                                }
                            }
                        },
                    }
                }
            },
            "line_items_discount_count": {
                "$sum": {
                    "$map": {
                        "input": "$line_items",
                        "as": "item",
                        "in": {"$size": {"$ifNull": ["$$item.discounts", []]}},
                    }
                }
            },
            "line_items_discount_quantity": {
                "$sum": {
                    "$map": {
                        "input": "$line_items",
                        "as": "item",
                        "in": {
                            "$cond": {
                                "if": {"$gt": [{"$size": {"$ifNull": ["$$item.discounts", []]}}, 0]},
                                "then": {"$ifNull": ["$$item.quantity", 0]},
                                "else": 0,
                            }
                        },
                    }
                }
            },
            "sub_total_discount_amount": {
                "$sum": {"$map": {"input": "$subtotal_discounts", "as": "discount", "in": "$$discount.discount_amount"}}
            },
            "sub_total_discount_count": {"$size": {"$ifNull": ["$subtotal_discounts", []]}},
            "sub_total_discount_quantity": {
                "$sum": {
                    "$map": {
                        "input": "$line_items",
                        "as": "item",
                        "in": {
                            "$cond": {
                                "if": {"$gt": [{"$size": {"$ifNull": ["$$item.discounts_allocated", []]}}, 0]},
                                "then": {"$ifNull": ["$$item.quantity", 0]},
                                "else": 0,
                            }
                        },
                    }
                }
            },
            "taxes": {
                "$map": {
                    "input": "$taxes",
                    "as": "tax",
                    "in": {
                        "tax_no": "$$tax.tax_no",
                        "tax_code": "$$tax.tax_code",
                        "tax_type": "$$tax.tax_type",
                        "tax_name": "$$tax.tax_name",
                        "tax_amount": "$$tax.tax_amount",
                        "target_amount": "$$tax.target_amount",
                        "target_quantity": "$$tax.target_quantity",
                    },
                }
            },
            "payments": {
                "$map": {
                    "input": "$payments",
                    "as": "payment",
                    "in": {
                        "payment_no": "$$payment.payment_no",
                        "payment_code": "$$payment.payment_code",
                        "amount": "$$payment.amount",
                        "description": "$$payment.description",
                    },
                }
            },
        }

        # Add optional keys
        if terminal_no is not None:
            match_dict["terminal_no"] = terminal_no

        if open_counter is not None:
            match_dict["open_counter"] = open_counter

        # CRITICAL FIX for Cartesian product issue (Issue #78)
        # Add intermediate grouping by transaction_no to deduplicate parent fields
        # before final aggregation by business criteria
        # Note: transaction_no is only unique within tenant_id + store_code + terminal_no

        intermediate_group_id = {
            "tenant_id": "$tenant_id",
            "store_code": "$store_code",
            "terminal_no": "$terminal_no",  # Always include terminal_no for unique identification
            "business_date": "$business_date",
            "transaction_no": "$transaction_no",
            "transaction_type": "$transaction_type",
        }

        intermediate_group_dict = {
            "_id": intermediate_group_id,
            # Use $first to get parent-level fields only once per transaction
            "total_amount": {"$first": "$sales.total_amount"},
            "total_amount_with_tax": {"$first": "$sales.total_amount_with_tax"},
            "total_tax_amount": {"$first": "$sales.tax_amount"},
            "total_quantity": {"$first": "$sales.total_quantity"},
            "total_change_amount": {"$first": "$sales.change_amount"},
            "total_discount_amount": {"$first": "$sales.total_discount_amount"},
            "line_items_discount_amount": {"$first": "$line_items_discount_amount"},
            "line_items_discount_count": {"$first": "$line_items_discount_count"},
            "line_items_discount_quantity": {"$first": "$line_items_discount_quantity"},
            "sub_total_discount_amount": {"$first": "$sub_total_discount_amount"},
            "sub_total_discount_count": {"$first": "$sub_total_discount_count"},
            "sub_total_discount_quantity": {"$first": "$sub_total_discount_quantity"},
            # CRITICAL FIX: Use $addToSet instead of $push to eliminate Cartesian product duplicates
            # After $unwind taxes and $unwind payments, we get 4 docs (2 taxes × 2 payments)
            # Using $push would collect: taxes=[tax1, tax1, tax2, tax2], payments=[pay1, pay2, pay1, pay2]
            # Using $addToSet collects only unique values: taxes=[tax1, tax2], payments=[pay1, pay2]
            "taxes": {"$addToSet": "$taxes"},
            "payments": {"$addToSet": "$payments"},
        }

        # Create final group dict for business criteria aggregation
        final_group_id = {
            "tenant_id": "$_id.tenant_id",
            "store_code": "$_id.store_code",
            "business_date": "$_id.business_date",
            "transaction_type": "$_id.transaction_type",
        }
        # Include terminal_no in final grouping only if filtering by specific terminal
        if terminal_no is not None:
            final_group_id["terminal_no"] = "$_id.terminal_no"

        final_group_dict = {
            "_id": final_group_id,
            # Sum parent fields (now each transaction counted once)
            "total_amount": {"$sum": "$total_amount"},
            "total_amount_with_tax": {"$sum": "$total_amount_with_tax"},
            "total_tax_amount": {"$sum": "$total_tax_amount"},
            "total_quantity": {"$sum": "$total_quantity"},
            "total_change_amount": {"$sum": "$total_change_amount"},
            "total_discount_amount": {"$sum": "$total_discount_amount"},
            "total_line_items_discount_amount": {"$sum": "$line_items_discount_amount"},
            "total_line_items_discount_count": {"$sum": "$line_items_discount_count"},
            "total_line_items_discount_quantity": {"$sum": "$line_items_discount_quantity"},
            "total_sub_total_discount_amount": {"$sum": "$sub_total_discount_amount"},
            "total_sub_total_discount_count": {"$sum": "$sub_total_discount_count"},
            "total_sub_total_discount_quantity": {"$sum": "$sub_total_discount_quantity"},
            "total_transaction_count": {"$sum": 1},
            # Flatten and collect taxes and payments arrays
            "all_taxes": {"$push": "$taxes"},
            "all_payments": {"$push": "$payments"},
        }

        # Create pipeline with intermediate grouping to fix Cartesian product issue
        pipeline = [
            {"$match": match_dict},
            {"$project": project_dict},
            # IMPORTANT: preserveNullAndEmptyArrays handles empty taxes/payments arrays (e.g., non-taxable items)
            {"$unwind": {"path": "$taxes", "preserveNullAndEmptyArrays": True}},
            {"$unwind": {"path": "$payments", "preserveNullAndEmptyArrays": True}},
            # CRITICAL FIX: Group by transaction_no first
            {"$group": intermediate_group_dict},
            # Then group by business criteria
            {"$group": final_group_dict},
            # Process taxes - unwind twice because it's array of arrays
            {"$unwind": {"path": "$all_taxes", "preserveNullAndEmptyArrays": True}},
            {"$unwind": {"path": "$all_taxes", "preserveNullAndEmptyArrays": True}},
            # Group by tax code
            {
                "$group": {
                    "_id": dict(list(final_group_id.items()) + [("tax_code", "$all_taxes.tax_code"), ("tax_name", "$all_taxes.tax_name")]),
                    "tax_amount": {"$sum": "$all_taxes.tax_amount"},
                    "target_amount": {"$sum": "$all_taxes.target_amount"},
                    "target_quantity": {"$sum": "$all_taxes.target_quantity"},
                    # Preserve aggregated fields
                    "total_amount": {"$first": "$total_amount"},
                    "total_amount_with_tax": {"$first": "$total_amount_with_tax"},
                    "total_tax_amount": {"$first": "$total_tax_amount"},
                    "total_quantity": {"$first": "$total_quantity"},
                    "total_change_amount": {"$first": "$total_change_amount"},
                    "total_discount_amount": {"$first": "$total_discount_amount"},
                    "total_line_items_discount_amount": {"$first": "$total_line_items_discount_amount"},
                    "total_line_items_discount_count": {"$first": "$total_line_items_discount_count"},
                    "total_line_items_discount_quantity": {"$first": "$total_line_items_discount_quantity"},
                    "total_sub_total_discount_amount": {"$first": "$total_sub_total_discount_amount"},
                    "total_sub_total_discount_count": {"$first": "$total_sub_total_discount_count"},
                    "total_sub_total_discount_quantity": {"$first": "$total_sub_total_discount_quantity"},
                    "total_transaction_count": {"$first": "$total_transaction_count"},
                    "all_payments": {"$first": "$all_payments"},
                }
            },
            # Regroup to collect taxes
            {
                "$group": {
                    "_id": final_group_id,
                    "total_amount": {"$first": "$total_amount"},
                    "total_amount_with_tax": {"$first": "$total_amount_with_tax"},
                    "total_tax_amount": {"$first": "$total_tax_amount"},
                    "total_quantity": {"$first": "$total_quantity"},
                    "total_change_amount": {"$first": "$total_change_amount"},
                    "total_discount_amount": {"$first": "$total_discount_amount"},
                    "total_line_items_discount_amount": {"$first": "$total_line_items_discount_amount"},
                    "total_line_items_discount_count": {"$first": "$total_line_items_discount_count"},
                    "total_line_items_discount_quantity": {"$first": "$total_line_items_discount_quantity"},
                    "total_sub_total_discount_amount": {"$first": "$total_sub_total_discount_amount"},
                    "total_sub_total_discount_count": {"$first": "$total_sub_total_discount_count"},
                    "total_sub_total_discount_quantity": {"$first": "$total_sub_total_discount_quantity"},
                    "total_transaction_count": {"$first": "$total_transaction_count"},
                    "taxes": {
                        "$push": {
                            "tax_code": "$_id.tax_code",
                            "tax_name": "$_id.tax_name",
                            "tax_amount": "$tax_amount",
                            "target_amount": "$target_amount",
                            "target_quantity": "$target_quantity",
                        }
                    },
                    "all_payments": {"$first": "$all_payments"},
                }
            },
            # Process payments - unwind twice
            {"$unwind": "$all_payments"},
            {"$unwind": "$all_payments"},
            # Group by payment code
            {
                "$group": {
                    "_id": dict(list(final_group_id.items()) + [("payment_code", "$all_payments.payment_code"), ("description", "$all_payments.description")]),
                    "payment_amount": {"$sum": "$all_payments.amount"},
                    "payment_count": {"$sum": 1},
                    # Preserve fields
                    "total_amount": {"$first": "$total_amount"},
                    "total_amount_with_tax": {"$first": "$total_amount_with_tax"},
                    "total_tax_amount": {"$first": "$total_tax_amount"},
                    "total_quantity": {"$first": "$total_quantity"},
                    "total_change_amount": {"$first": "$total_change_amount"},
                    "total_discount_amount": {"$first": "$total_discount_amount"},
                    "total_line_items_discount_amount": {"$first": "$total_line_items_discount_amount"},
                    "total_line_items_discount_count": {"$first": "$total_line_items_discount_count"},
                    "total_line_items_discount_quantity": {"$first": "$total_line_items_discount_quantity"},
                    "total_sub_total_discount_amount": {"$first": "$total_sub_total_discount_amount"},
                    "total_sub_total_discount_count": {"$first": "$total_sub_total_discount_count"},
                    "total_sub_total_discount_quantity": {"$first": "$total_sub_total_discount_quantity"},
                    "total_transaction_count": {"$first": "$total_transaction_count"},
                    "taxes": {"$first": "$taxes"},
                }
            },
            # Final regroup to collect payments
            {
                "$group": {
                    "_id": final_group_id,
                    "total_amount": {"$first": "$total_amount"},
                    "total_amount_with_tax": {"$first": "$total_amount_with_tax"},
                    "total_tax_amount": {"$first": "$total_tax_amount"},
                    "total_quantity": {"$first": "$total_quantity"},
                    "total_change_amount": {"$first": "$total_change_amount"},
                    "total_discount_amount": {"$first": "$total_discount_amount"},
                    "total_line_items_discount_amount": {"$first": "$total_line_items_discount_amount"},
                    "total_line_items_discount_count": {"$first": "$total_line_items_discount_count"},
                    "total_line_items_discount_quantity": {"$first": "$total_line_items_discount_quantity"},
                    "total_sub_total_discount_amount": {"$first": "$total_sub_total_discount_amount"},
                    "total_sub_total_discount_count": {"$first": "$total_sub_total_discount_count"},
                    "total_sub_total_discount_quantity": {"$first": "$total_sub_total_discount_quantity"},
                    "total_transaction_count": {"$first": "$total_transaction_count"},
                    "taxes": {"$first": "$taxes"},
                    "payments": {
                        "$push": {
                            "payment_code": "$_id.payment_code",
                            "description": "$_id.description",
                            "amount": "$payment_amount",
                            "count": "$payment_count",
                        }
                    },
                }
            },
        ]

        # Add sort stage (if sort is specified)
        if sort:
            sort_dict = {field: direction for field, direction in sort}
            pipeline.append({"$sort": sort_dict})

        # Add pagination stage
        if page > 1:
            pipeline.append({"$skip": (page - 1) * limit})
        pipeline.append({"$limit": limit})

        return pipeline

    def _summarize_sales_report(self, results: list[dict]) -> dict[str, Any]:
        """
        Aggregate sales report results

        Args:
            results: Sales report retrieval results

        Returns:
            Aggregated sales report results
        """

        # Define default dictionary
        total = {
            "total_amount": 0,
            "total_amount_with_tax": 0,
            "total_tax_amount": 0,
            "total_quantity": 0,
            "total_change_amount": 0,
            "total_discount_amount": 0,
            "total_transaction_count": 0,
            "total_line_items_discount_amount": 0,
            "total_line_items_discount_count": 0,
            "total_line_items_discount_quantity": 0,
            "total_sub_total_discount_amount": 0,
            "total_sub_total_discount_count": 0,
            "total_sub_total_discount_quantity": 0,
            "taxes": [],
            "payments": [],
        }

        for result in results:
            transaction_type = result["_id"]["transaction_type"]
            logger.debug(f"Summarize sales report Transaction type: {transaction_type}")
            logger.debug(f"Summarize sales report: result -> {result}")
            factor = self._return_factor(transaction_type)
            total["total_amount"] += result["total_amount"] * factor
            total["total_amount_with_tax"] += result["total_amount_with_tax"] * factor
            total["total_tax_amount"] += result["total_tax_amount"] * factor
            total["total_quantity"] += result["total_quantity"] * factor
            total["total_change_amount"] += result["total_change_amount"] * factor
            total["total_discount_amount"] += result["total_discount_amount"] * factor
            total["total_transaction_count"] += result["total_transaction_count"] * factor
            total["total_line_items_discount_amount"] += result["total_line_items_discount_amount"] * factor
            total["total_line_items_discount_count"] += result["total_line_items_discount_count"] * factor
            total["total_line_items_discount_quantity"] += result["total_line_items_discount_quantity"] * factor
            total["total_sub_total_discount_amount"] += result["total_sub_total_discount_amount"] * factor
            total["total_sub_total_discount_count"] += result["total_sub_total_discount_count"] * factor
            total["total_sub_total_discount_quantity"] += result["total_sub_total_discount_quantity"] * factor

            # Aggregate tax amounts
            for tax in result["taxes"]:
                tax_code = tax.get("tax_code")
                tax_name = tax.get("tax_name")
                # Skip if tax_code is None (e.g., empty taxes array)
                if tax_code is None:
                    continue
                tax_amount = tax.get("tax_amount", 0) * factor
                target_amount = tax.get("target_amount", 0) * factor
                target_quantity = tax.get("target_quantity", 0) * factor
                tax_dict = next((tax for tax in total["taxes"] if tax.get("tax_code") == tax_code), None)
                if tax_dict is None:
                    total["taxes"].append(
                        {
                            "tax_code": tax_code,
                            "tax_name": tax_name,
                            "tax_amount": tax_amount,
                            "target_amount": target_amount,
                            "target_quantity": target_quantity,
                        }
                    )
                else:
                    tax_dict["tax_amount"] += tax_amount
                    tax_dict["target_amount"] += target_amount
                    tax_dict["target_quantity"] += target_quantity

            # Aggregate payment methods
            for payment in result["payments"]:
                payment_code = payment.get("payment_code")
                description = payment.get("description")
                # Skip if payment_code is None (e.g., empty payments array)
                if payment_code is None:
                    continue
                amount = payment.get("amount", 0) * factor
                count = payment.get("count", 0) * factor
                payment_dict = next((payment for payment in total["payments"] if payment.get("payment_code") == payment_code), None)
                if payment_dict is None:
                    total["payments"].append(
                        {"payment_code": payment_code, "description": description, "amount": amount, "count": count}
                    )
                else:
                    payment_dict["amount"] += amount
                    payment_dict["count"] += count
            logger.debug(f"Summarize sales report: total -> {total}")
        return total

    def _make_sales_gross(self, results: list[dict]) -> dict[str, Any]:
        """
        Create gross sales information (before discounts)

        Args:
            results: Sales report retrieval results

        Returns:
            Gross sales information (amount before discounts)
        """

        normal_sales = self._get_result_by_transaction_type(results, TransactionType.NormalSales.value)
        void_sales = self._get_result_by_transaction_type(results, TransactionType.VoidSales.value)

        if normal_sales is None:
            normal_sales = {"total_amount": 0, "total_discount_amount": 0, "total_quantity": 0, "total_transaction_count": 0}

        if void_sales is None:
            void_sales = {"total_amount": 0, "total_discount_amount": 0, "total_quantity": 0, "total_transaction_count": 0}

        # Sales Gross = Net Amount + Discounts (to get amount before discounts)
        normal_gross = normal_sales["total_amount"] + normal_sales.get("total_discount_amount", 0)
        void_gross = void_sales["total_amount"] + void_sales.get("total_discount_amount", 0)

        return_dict = {
            "amount": normal_gross - void_gross,
            "quantity": normal_sales["total_quantity"] - void_sales["total_quantity"],
            "count": normal_sales["total_transaction_count"] - void_sales["total_transaction_count"],
        }
        logger.debug(f"Sales gross: {return_dict}")
        return return_dict

    def _make_sales_net(self, summarized_result: dict[str, Any]) -> dict[str, Any]:
        """
        Create net sales information

        Args:
            summarized_result: Aggregated sales report results

        Returns:
            Net sales information
        """

        return_dict = {
            "amount": summarized_result["total_amount"],
            "quantity": summarized_result["total_quantity"],
            "count": summarized_result["total_transaction_count"],
        }
        logger.debug(f"Sales net: {return_dict}")
        return return_dict

    def _make_discount_for_lineitem(self, summarized_result: dict[str, Any]) -> dict[str, Any]:
        """
        Create line item discount information

        Args:
            summarized_result: Aggregated sales report results

        Returns:
            Line item discount information
        """

        return_dict = {
            "amount": summarized_result["total_line_items_discount_amount"],
            "quantity": summarized_result["total_line_items_discount_quantity"],
            "count": summarized_result["total_line_items_discount_count"],
        }
        logger.debug(f"Discount for line item: {return_dict}")
        return return_dict

    def _make_discount_for_subtotal(self, summarized_result: dict[str, Any]) -> dict[str, Any]:
        """
        Create subtotal discount information

        Args:
            summarized_result: Aggregated sales report results

        Returns:
            Subtotal discount information
        """

        return_dict = {
            "amount": summarized_result["total_sub_total_discount_amount"],
            "quantity": summarized_result["total_sub_total_discount_quantity"],
            "count": summarized_result["total_sub_total_discount_count"],
        }
        logger.debug(f"Discount for subtotal: {return_dict}")
        return return_dict

    def _make_returns(self, results: list[dict]) -> dict[str, Any]:
        """
        Create return information

        Args:
            results: Sales report retrieval results

        Returns:
            Return information
        """

        return_sales = self._get_result_by_transaction_type(results, TransactionType.ReturnSales.value)
        void_return = self._get_result_by_transaction_type(results, TransactionType.VoidReturn.value)

        if return_sales is None:
            return_sales = {"total_amount": 0, "total_quantity": 0, "total_transaction_count": 0}

        if void_return is None:
            void_return = {"total_amount": 0, "total_quantity": 0, "total_transaction_count": 0}

        return_dict = {
            "amount": return_sales["total_amount"] - void_return["total_amount"],
            "quantity": return_sales["total_quantity"] - void_return["total_quantity"],
            "count": return_sales["total_transaction_count"] - void_return["total_transaction_count"],
        }
        logger.debug(f"Returns: {return_dict}")
        return return_dict

    def _make_taxes(self, summarized_result: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Create tax information

        Args:
            summarized_result: Aggregated sales report results

        Returns:
            List of tax information
        """

        taxes = summarized_result.get("taxes", [])
        return_list = [
            {
                "tax_code": tax.get("tax_code"),
                "tax_type": tax.get("tax_type"),
                "tax_name": tax.get("tax_name"),
                "tax_amount": tax.get("tax_amount", 0),
                "target_amount": tax.get("target_amount", 0),
                "target_quantity": tax.get("target_quantity", 0),
            }
            for tax in taxes
            if tax.get("tax_code") is not None  # Filter out null tax_code (e.g., empty taxes array)
        ]
        logger.debug(f"Taxes: {return_list}")
        return return_list

    def _make_payments(self, summarized_result: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Create payment method information

        Args:
            summarized_result: Aggregated sales report results

        Returns:
            List of payment method information
        """

        payments = summarized_result.get("payments", [])
        return_list = [
            {
                "payment_code": payment.get("payment_code"),
                "payment_name": payment.get("description"),
                "amount": payment.get("amount", 0),
                "count": payment.get("count", 0),
            }
            for payment in payments
            if payment.get("payment_code") is not None  # Filter out null payment_code (e.g., empty payments array)
        ]
        logger.debug(f"Payments: {return_list}")
        return return_list

    def _make_cash(
        self, cash_summary: dict[str, Any], open_close_summary: dict[str, Any], payment_summary: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Create cash information

        Args:
            cash_summary: Aggregated results of cash in/out logs
            open_close_summary: Aggregated results of open/close logs
            payment_summary: Aggregated results of payment methods

        Returns:
            Cash information
        """

        initial_amount = open_close_summary["initial_amount"]
        payment_amount_by_cash = payment_summary["cash"]
        cash_in_amount = cash_summary["cash_in_amount"]
        cash_out_amount = cash_summary["cash_out_amount"]
        logical_amount = payment_amount_by_cash + cash_in_amount + cash_out_amount  # cash_out_amount is negative
        pyisical_amount = open_close_summary["physical_amount"]
        difference_amount = pyisical_amount - logical_amount

        return {
            "logical_amount": logical_amount,
            "physical_amount": pyisical_amount,
            "difference_amount": difference_amount,
            "cash_in": {"amount": cash_in_amount, "count": cash_summary["cash_in_count"]},
            "cash_out": {"amount": cash_out_amount, "count": cash_summary["cash_out_count"]},
        }

    def _get_result_by_transaction_type(self, results: list[dict], transaction_type: int) -> dict[str, Any]:
        """
        Retrieve results based on transaction type

        Args:
            results: Sales report retrieval results
            transaction_type: Transaction type

        Returns:
            Results matching the transaction type, or None if not found
        """
        return next((result for result in results if result["_id"]["transaction_type"] == transaction_type), None)

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
