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
Performance Test Data Setup Script

This script sets up all necessary test data for performance testing:
1. Create account superuser with auto-generated tenant_id
2. Create terminal tenant, store, and terminal masters with auto-generated API key
3. Open terminal
4. Register 1000 items in master-data (item_common and item_store)
"""

import asyncio
import os
import random
import string
from datetime import datetime
from httpx import AsyncClient
from dotenv import load_dotenv


class PerformanceTestDataSetup:
    """Setup test data for performance testing"""

    def __init__(self):
        # Load environment variables
        load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env.test"))

        self.base_url_account = os.getenv("BASE_URL_ACCOUNT", "http://localhost:8000")
        self.base_url_terminal = os.getenv("BASE_URL_TERMINAL", "http://localhost:8001/api/v1")
        self.base_url_master_data = os.getenv("BASE_URL_MASTER_DATA", "http://localhost:8002/api/v1")

        # Generate random tenant_id
        self.tenant_id = self._generate_tenant_id()
        self.store_code = "5678"
        self.terminal_no = 9
        self.terminal_id = f"{self.tenant_id}-{self.store_code}-{self.terminal_no}"

        self.api_key = None
        self.token = None

    def _generate_tenant_id(self) -> str:
        """Generate random tenant ID (T + 4 digits)"""
        return f"T{random.randint(1000, 9999)}"

    async def setup_all(self):
        """Setup all test data"""
        print("=" * 80)
        print("Performance Test Data Setup")
        print("=" * 80)
        print(f"Tenant ID: {self.tenant_id}")
        print(f"Store Code: {self.store_code}")
        print(f"Terminal ID: {self.terminal_id}")
        print("=" * 80)

        try:
            # Step 1: Create account superuser
            await self._create_superuser()

            # Step 2: Get authentication token
            await self._get_auth_token()

            # Step 3: Create terminal masters
            await self._create_terminal_masters()

            # Step 3.5: Register staff
            await self._register_staff()

            # Step 4: Sign in and open terminal
            await self._open_terminal()

            # Step 5: Register items
            await self._register_items()

            print("\n" + "=" * 80)
            print("✓ All test data setup completed successfully!")
            print("=" * 80)
            print(f"Tenant ID: {self.tenant_id}")
            print(f"Terminal ID: {self.terminal_id}")
            print(f"API Key: {self.api_key}")
            print("=" * 80)

            # Save to .env.test
            self._save_to_env()

        except Exception as e:
            print(f"\n✗ Error during setup: {str(e)}")
            raise

    async def _create_superuser(self):
        """Step 1: Create account superuser"""
        print("\n[1/5] Creating account superuser...")

        async with AsyncClient() as client:
            response = await client.post(
                f"{self.base_url_account}/api/v1/accounts/register",
                json={
                    "username": "admin",
                    "password": "admin",
                    "tenant_id": self.tenant_id,
                    "is_superuser": True
                }
            )

            if response.status_code == 201:
                result = response.json()
                print(f"  ✓ Superuser created: {result['data']['username']}")
            else:
                raise Exception(f"Failed to create superuser: {response.status_code} - {response.text}")

    async def _get_auth_token(self):
        """Step 2: Get authentication token"""
        print("\n[2/5] Getting authentication token...")

        async with AsyncClient() as client:
            response = await client.post(
                f"{self.base_url_account}/api/v1/accounts/token",
                data={
                    "username": "admin",
                    "password": "admin",
                    "client_id": self.tenant_id
                }
            )

            if response.status_code == 200:
                result = response.json()
                self.token = result["access_token"]
                print(f"  ✓ Token obtained")
            else:
                raise Exception(f"Failed to get token: {response.status_code} - {response.text}")

    async def _create_terminal_masters(self):
        """Step 3: Create terminal tenant, store, and terminal masters"""
        print("\n[3/5] Creating terminal masters...")

        headers = {"Authorization": f"Bearer {self.token}"}

        async with AsyncClient() as client:
            # Create tenant master
            response = await client.post(
                f"{self.base_url_terminal}/tenants",
                headers=headers,
                json={
                    "tenant_id": self.tenant_id,
                    "tenant_name": f"Performance Test Tenant {self.tenant_id}",
                    "stores": [],
                    "tags": ["PerformanceTest"]
                }
            )

            if response.status_code in [201, 200]:
                print(f"  ✓ Tenant master created: {self.tenant_id}")
            else:
                print(f"  ! Tenant creation response: {response.status_code} - {response.text}")
                raise Exception(f"Failed to create tenant: {response.status_code} - {response.text}")

            # Create store master
            response = await client.post(
                f"{self.base_url_terminal}/tenants/{self.tenant_id}/stores",
                headers=headers,
                json={
                    "store_code": self.store_code,
                    "store_name": f"Performance Test Store {self.store_code}",
                    "tags": ["PerformanceTest"]
                }
            )

            if response.status_code in [201, 200]:
                print(f"  ✓ Store master created: {self.store_code}")
            else:
                print(f"  ! Store creation response: {response.status_code} - {response.text}")
                raise Exception(f"Failed to create store: {response.status_code} - {response.text}")

            # Create terminal master
            response = await client.post(
                f"{self.base_url_terminal}/terminals",
                headers=headers,
                json={
                    "store_code": self.store_code,
                    "terminal_no": self.terminal_no,
                    "description": f"Performance Test Terminal {self.terminal_no}"
                }
            )

            if response.status_code in [201, 200]:
                result = response.json()
                if result.get("success"):
                    self.api_key = result["data"].get("apiKey")
                    print(f"  ✓ Terminal master created: {self.terminal_id}")
                    print(f"  ✓ API Key generated: {self.api_key}")
                else:
                    raise Exception(f"Terminal creation failed: {result}")
            else:
                raise Exception(f"Failed to create terminal: {response.status_code} - {response.text}")

    async def _register_staff(self):
        """Step 3.5: Register staff in master-data"""
        print("\n[3.5/5] Registering staff...")

        headers = {"Authorization": f"Bearer {self.token}"}

        async with AsyncClient() as client:
            # Register staff
            response = await client.post(
                f"{self.base_url_master_data}/tenants/{self.tenant_id}/staff",
                headers=headers,
                json={
                    "id": "staff001",
                    "name": "Test Staff",
                    "pin": "1234",
                    "roles": ["staff"]
                }
            )

            if response.status_code in [201, 200]:
                print(f"  ✓ Staff registered: staff001")
            else:
                print(f"  ! Staff registration response: {response.status_code} - {response.text}")
                raise Exception(f"Failed to register staff: {response.status_code} - {response.text}")

    async def _open_terminal(self):
        """Step 4: Sign in and open terminal"""
        print("\n[4/5] Signing in and opening terminal...")

        headers = {"X-API-KEY": self.api_key}

        async with AsyncClient() as client:
            # Sign in
            response = await client.post(
                f"{self.base_url_terminal}/terminals/{self.terminal_id}/sign-in",
                headers=headers,
                json={
                    "staff_id": "staff001"
                }
            )

            if response.status_code in [201, 200]:
                print(f"  ✓ Staff signed in: {self.terminal_id}")
            else:
                raise Exception(f"Failed to sign in: {response.status_code} - {response.text}")

            # Open terminal
            response = await client.post(
                f"{self.base_url_terminal}/terminals/{self.terminal_id}/open",
                headers=headers,
                json={
                    "initial_amount": 500000
                }
            )

            if response.status_code in [201, 200]:
                print(f"  ✓ Terminal opened: {self.terminal_id}")
            else:
                raise Exception(f"Failed to open terminal: {response.status_code} - {response.text}")

    async def _register_items(self):
        """Step 5: Register 100 items for performance testing"""
        print("\n[5/5] Registering items (100 items for testing)...")

        headers = {"Authorization": f"Bearer {self.token}"}

        async with AsyncClient(timeout=300.0) as client:
            total_items = 100
            success_count = 0

            for i in range(total_items):
                # Register item_common
                item_common = {
                    "itemCode": f"ITEM{i:03d}",
                    "description": f"Performance Test Item {i:03d}",
                    "unitPrice": 100.0 + (i % 100),
                    "unitCost": 50.0 + (i % 50),
                    "itemDetails": [],
                    "imageUrls": [],
                    "categoryCode": f"CAT{(i % 10):02d}",
                    "taxCode": "01",
                    "isDiscountRestricted": False
                }

                response = await client.post(
                    f"{self.base_url_master_data}/tenants/{self.tenant_id}/items",
                    headers=headers,
                    json=item_common
                )

                if response.status_code in [201, 200]:
                    success_count += 1
                else:
                    print(f"  ! Item {i:03d} registration failed: {response.status_code} - {response.text[:100]}")

            print(f"  ✓ Registered {success_count}/{total_items} items successfully")

    def _save_to_env(self):
        """Save configuration to .env.test"""
        env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env.test")

        with open(env_path, "w") as f:
            f.write("# Test environment variables\n")
            f.write('LOCAL_TEST="True"\n')
            f.write('MONGODB_URI=mongodb://localhost:27017/?replicaSet=rs0&directConnection=true\n')
            f.write(f'TENANT_ID="{self.tenant_id}"\n')
            f.write(f'API_KEY="{self.api_key}"\n')

        print(f"\n✓ Configuration saved to {env_path}")


async def main():
    """Main entry point"""
    setup = PerformanceTestDataSetup()
    await setup.setup_all()


if __name__ == "__main__":
    asyncio.run(main())
