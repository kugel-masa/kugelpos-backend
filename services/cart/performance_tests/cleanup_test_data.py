# Copyright 2025 masa@kugel
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Performance Test Data Cleanup Script

This script cleans up test data created by setup_test_data.py
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv


class PerformanceTestDataCleanup:
    """Cleanup test data for performance testing"""

    def __init__(self):
        # Load environment variables
        load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env.test"))

        self.mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/?replicaSet=rs0&directConnection=true")
        self.tenant_id = os.getenv("TENANT_ID")

        if not self.tenant_id:
            raise ValueError("TENANT_ID not found in .env.test")

    async def cleanup_all(self):
        """Cleanup all test data"""
        print("=" * 80)
        print("Performance Test Data Cleanup")
        print("=" * 80)
        print(f"Tenant ID: {self.tenant_id}")
        print("=" * 80)

        try:
            client = AsyncIOMotorClient(self.mongodb_uri)

            # List of databases to drop
            databases_to_drop = [
                f"db_account_{self.tenant_id}",
                f"db_terminal_{self.tenant_id}",
                f"db_master_{self.tenant_id}",
                f"db_cart_{self.tenant_id}",
                f"db_report_{self.tenant_id}",
                f"db_journal_{self.tenant_id}",
                f"db_stock_{self.tenant_id}",
            ]

            # Drop tenant from commons databases
            print("\n[1/2] Removing tenant from commons databases...")
            commons_db = client["db_account_commons"]
            result = await commons_db.tenants.delete_many({"tenant_id": self.tenant_id})
            print(f"  ✓ Removed {result.deleted_count} tenant record(s) from db_account_commons")

            # Drop tenant-specific databases
            print("\n[2/2] Dropping tenant-specific databases...")
            for db_name in databases_to_drop:
                db_list = await client.list_database_names()
                if db_name in db_list:
                    await client.drop_database(db_name)
                    print(f"  ✓ Dropped database: {db_name}")
                else:
                    print(f"  - Database not found: {db_name}")

            client.close()

            print("\n" + "=" * 80)
            print("✓ All test data cleaned up successfully!")
            print("=" * 80)

        except Exception as e:
            print(f"\n✗ Error during cleanup: {str(e)}")
            raise


async def main():
    """Main entry point"""
    cleanup = PerformanceTestDataCleanup()
    await cleanup.cleanup_all()


if __name__ == "__main__":
    asyncio.run(main())
