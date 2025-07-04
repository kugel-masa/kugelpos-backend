# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional
from functools import lru_cache

from app.services.multi_tenant_snapshot_scheduler import MultiTenantSnapshotScheduler


# Global scheduler instance (set by main.py)
_scheduler_instance: Optional[MultiTenantSnapshotScheduler] = None


def set_scheduler(scheduler: Optional[MultiTenantSnapshotScheduler]) -> None:
    """Set the global scheduler instance."""
    global _scheduler_instance
    _scheduler_instance = scheduler


@lru_cache()
def get_scheduler() -> Optional[MultiTenantSnapshotScheduler]:
    """Get the scheduler instance for dependency injection."""
    return _scheduler_instance
