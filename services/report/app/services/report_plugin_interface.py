# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from abc import ABC, abstractmethod


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
    ) -> dict[str, any]:
        """
        Generate a report based on the provided parameters.

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

        Returns:
            A dictionary containing the report data
        """
        pass
