# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from abc import ABC, abstractmethod
from typing import Any


class IReportPlugin(ABC):
    """
    Abstract interface for report generation plugins.

    This interface defines the contract that all report plugins must implement.
    Each plugin is responsible for generating specific types of reports based on
    transaction data, cash operations, and other business activities.
    """

    @abstractmethod
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
        **kwargs,
    ) -> dict[str, any]:
        """
        Generate a report based on the provided parameters.

        Callers may pass keyword arguments beyond these parameters. Implementations
        must accept them and may ignore the ones they do not support.

        Args:
            store_code: Identifier for the store
            terminal_no: Terminal number
            business_counter: Business counter for the day
            business_date: Date for which the report is generated
            open_counter: Counter for terminal open/close cycles
            report_scope: Scope of the report (e.g., 'flash', 'daily')
            report_type: Type of report to generate (e.g., 'sales', 'inventory')
            limit: Maximum number of records to include
            page: Page number for pagination
            sort: List of tuples containing field name and sort direction (1 for ascending, -1 for descending)
            business_date_from: Start of a business-date range (optional)
            business_date_to: End of a business-date range (optional)
            **kwargs: Further keyword arguments from the caller

        Returns:
            A dictionary containing the report data
        """
        pass

    def merge(self, reports: list[dict]) -> Any:
        """
        Optional capability: build one report out of several terminals' daily reports.

        A plugin that can aggregate overrides this; by default it is refused.

        Args:
            reports: Daily reports of this plugin's type, as stored (dicts
                produced by model_dump())

        Returns:
            The aggregated report document

        Raises:
            NotImplementedError: If this plugin does not aggregate
        """
        raise NotImplementedError(f"{self.__class__.__name__}: aggregating daily reports is not supported")

    def from_saved(self, report: dict) -> Any:
        """
        Optional capability: turn a stored daily report back into this plugin's report document.

        Args:
            report: A stored daily report (a dict produced by model_dump())

        Returns:
            The report document

        Raises:
            NotImplementedError: If this plugin does not load stored reports
        """
        raise NotImplementedError(f"{self.__class__.__name__}: loading a stored daily report is not supported")
