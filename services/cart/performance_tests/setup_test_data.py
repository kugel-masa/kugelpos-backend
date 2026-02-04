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
Performance Test Data Setup Script - Multi Terminal Version

This script sets up all necessary test data for performance testing with multiple terminals:
1. Create account superuser with auto-generated tenant_id
2. Create terminal tenant and store masters
3. Create MULTIPLE terminals (default: 50) with unique API keys
4. Open all terminals
5. Register 100 items in master-data
"""

import asyncio
import os
import random
import json
from datetime import datetime
from httpx import AsyncClient
from dotenv import load_dotenv


class MultiTerminalPerformanceTestDataSetup:
    """Setup test data for performance testing with multiple terminals"""

    def __init__(self, num_terminals: int = 50):
        # Load environment variables
        load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env.test"))

        self.base_url_account = os.getenv("BASE_URL_ACCOUNT", "http://localhost:8000")
        self.base_url_terminal = os.getenv("BASE_URL_TERMINAL", "http://localhost:8001/api/v1")
        self.base_url_master_data = os.getenv("BASE_URL_MASTER_DATA", "http://localhost:8002/api/v1")

        # Generate random tenant_id
        self.tenant_id = self._generate_tenant_id()
        self.store_code = "5678"

        # Multiple terminals configuration
        self.num_terminals = num_terminals
        self.terminals = []  # List of {terminal_no, terminal_id, api_key}

        self.token = None

    def _generate_tenant_id(self) -> str:
        """Generate random tenant ID (T + 4 digits)"""
        return f"T{random.randint(1000, 9999)}"

    async def setup_all(self):
        """Setup all test data"""
        print("=" * 80)
        print("Performance Test Data Setup - Multi Terminal Version")
        print("=" * 80)
        print(f"Tenant ID: {self.tenant_id}")
        print(f"Store Code: {self.store_code}")
        print(f"Number of Terminals: {self.num_terminals}")
        print("=" * 80)

        try:
            # Step 1: Create account superuser
            await self._create_superuser()

            # Step 2: Get authentication token
            await self._get_auth_token()

            # Step 3: Create terminal tenant and store masters
            await self._create_tenant_and_store_masters()

            # Step 4: Create multiple terminals
            await self._create_multiple_terminals()

            # Step 5: Register staff
            await self._register_staff()

            # Step 6: Open all terminals
            await self._open_all_terminals()

            # Step 7: Register items
            await self._register_items()

            print("\n" + "=" * 80)
            print("✓ All test data setup completed successfully!")
            print("=" * 80)
            print(f"Tenant ID: {self.tenant_id}")
            print(f"Store Code: {self.store_code}")
            print(f"Terminals Created: {len(self.terminals)}")
            print("=" * 80)

            # Save to configuration files
            self._save_to_env()
            self._save_terminal_config()

        except Exception as e:
            print(f"\n✗ Error during setup: {str(e)}")
            raise

    async def _create_superuser(self):
        """Step 1: Create account superuser"""
        print("\n[1/7] Creating account superuser...")

        async with AsyncClient(timeout=60.0) as client:
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
        print("\n[2/7] Getting authentication token...")

        async with AsyncClient(timeout=60.0) as client:
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

    async def _create_tenant_and_store_masters(self):
        """Step 3: Create terminal tenant and store masters"""
        print("\n[3/7] Creating tenant and store masters...")

        headers = {"Authorization": f"Bearer {self.token}"}

        async with AsyncClient(timeout=60.0) as client:  # Increased timeout to 60 seconds
            # Create tenant master
            response = await client.post(
                f"{self.base_url_terminal}/tenants",
                headers=headers,
                json={
                    "tenant_id": self.tenant_id,
                    "tenant_name": f"Performance Test Tenant {self.tenant_id}",
                    "stores": [],
                    "tags": ["PerformanceTest", "MultiTerminal"]
                }
            )

            if response.status_code in [201, 200]:
                print(f"  ✓ Tenant master created: {self.tenant_id}")
            else:
                raise Exception(f"Failed to create tenant: {response.status_code} - {response.text}")

            # Create store master
            response = await client.post(
                f"{self.base_url_terminal}/tenants/{self.tenant_id}/stores",
                headers=headers,
                json={
                    "store_code": self.store_code,
                    "store_name": f"Performance Test Store {self.store_code}",
                    "tags": ["PerformanceTest", "MultiTerminal"]
                }
            )

            if response.status_code in [201, 200]:
                print(f"  ✓ Store master created: {self.store_code}")
            else:
                raise Exception(f"Failed to create store: {response.status_code} - {response.text}")

    async def _create_multiple_terminals(self):
        """Step 4: Create multiple terminals"""
        print(f"\n[4/7] Creating {self.num_terminals} terminals...")

        headers = {"Authorization": f"Bearer {self.token}"}

        async with AsyncClient(timeout=300.0) as client:
            for i in range(1, self.num_terminals + 1):
                terminal_no = i
                terminal_id = f"{self.tenant_id}-{self.store_code}-{terminal_no}"

                response = await client.post(
                    f"{self.base_url_terminal}/terminals",
                    headers=headers,
                    json={
                        "store_code": self.store_code,
                        "terminal_no": terminal_no,
                        "description": f"Performance Test Terminal {terminal_no}"
                    }
                )

                if response.status_code in [201, 200]:
                    result = response.json()
                    if result.get("success"):
                        api_key = result["data"].get("apiKey")
                        self.terminals.append({
                            "terminal_no": terminal_no,
                            "terminal_id": terminal_id,
                            "api_key": api_key
                        })

                        if (i % 10 == 0) or (i == self.num_terminals):
                            print(f"  ✓ Created {i}/{self.num_terminals} terminals")
                    else:
                        print(f"  ! Terminal {terminal_no} creation failed: {result}")
                else:
                    print(f"  ! Terminal {terminal_no} creation failed: {response.status_code}")

            print(f"  ✓ Total terminals created: {len(self.terminals)}")

    async def _register_staff(self):
        """Step 5: Register staff in master-data"""
        print("\n[5/7] Registering staff...")

        headers = {"Authorization": f"Bearer {self.token}"}

        async with AsyncClient(timeout=60.0) as client:
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
                raise Exception(f"Failed to register staff: {response.status_code} - {response.text}")

    async def _open_all_terminals(self):
        """Step 6: Sign in and open all terminals"""
        print(f"\n[6/7] Opening {len(self.terminals)} terminals...")

        async with AsyncClient(timeout=300.0) as client:
            opened_count = 0

            for i, terminal_info in enumerate(self.terminals, 1):
                headers = {"X-API-KEY": terminal_info["api_key"]}
                terminal_id = terminal_info["terminal_id"]

                # Sign in
                response = await client.post(
                    f"{self.base_url_terminal}/terminals/{terminal_id}/sign-in",
                    headers=headers,
                    json={"staff_id": "staff001"}
                )

                if response.status_code not in [201, 200]:
                    print(f"  ! Sign in failed for terminal {terminal_id}")
                    continue

                # Open terminal
                response = await client.post(
                    f"{self.base_url_terminal}/terminals/{terminal_id}/open",
                    headers=headers,
                    json={"initial_amount": 500000}
                )

                if response.status_code in [201, 200]:
                    opened_count += 1
                    if (i % 10 == 0) or (i == len(self.terminals)):
                        print(f"  ✓ Opened {i}/{len(self.terminals)} terminals")
                else:
                    print(f"  ! Open failed for terminal {terminal_id}")

            print(f"  ✓ Total terminals opened: {opened_count}")

    async def _register_items(self):
        """Step 7: Register 100 items for performance testing"""
        print("\n[7/7] Registering items (100 items for testing)...")

        headers = {"Authorization": f"Bearer {self.token}"}

        async with AsyncClient(timeout=300.0) as client:
            total_items = 100
            success_count = 0

            for i in range(total_items):
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

            print(f"  ✓ Registered {success_count}/{total_items} items successfully")

    def _save_to_env(self):
        """Save configuration to .env.test"""
        env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env.test")

        # Use first terminal's API key as default
        default_api_key = self.terminals[0]["api_key"] if self.terminals else ""

        with open(env_path, "w") as f:
            f.write("# Test environment variables - Multi Terminal Setup\n")
            f.write('LOCAL_TEST="True"\n')
            f.write('MONGODB_URI=mongodb://localhost:27017/?replicaSet=rs0&directConnection=true\n')
            f.write(f'TENANT_ID="{self.tenant_id}"\n')
            f.write(f'API_KEY="{default_api_key}"\n')
            f.write(f'# Total terminals created: {len(self.terminals)}\n')

        print(f"\n✓ Configuration saved to {env_path}")

    def _save_terminal_config(self):
        """Save terminal configuration to JSON file for Locust to use"""
        config_path = os.path.join(os.path.dirname(__file__), "terminals_config.json")

        config = {
            "tenant_id": self.tenant_id,
            "store_code": self.store_code,
            "terminals": self.terminals,
            "created_at": datetime.now().isoformat()
        }

        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

        print(f"✓ Terminal configuration saved to {config_path}")


async def main():
    """Main entry point"""
    import sys

    # Allow specifying number of terminals via command line
    num_terminals = 50
    if len(sys.argv) > 1:
        try:
            num_terminals = int(sys.argv[1])
        except ValueError:
            print(f"Invalid number of terminals: {sys.argv[1]}, using default: 50")

    print(f"Creating {num_terminals} terminals...")
    setup = MultiTerminalPerformanceTestDataSetup(num_terminals=num_terminals)
    await setup.setup_all()


if __name__ == "__main__":
    asyncio.run(main())
