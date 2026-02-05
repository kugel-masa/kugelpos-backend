# Codebase Structure

## Root Directory
```
kugelpos-private/
├── CLAUDE.md           # AI coding assistant instructions
├── README.md           # Project documentation (English)
├── README_ja.md        # Project documentation (Japanese)
├── scripts/            # Build, test, deployment scripts
├── services/           # All microservices
├── docs/               # Additional documentation
└── .github/            # GitHub Actions workflows
```

## Services Directory
```
services/
├── account/            # Port 8000 - Authentication
├── terminal/           # Port 8001 - Terminal management
├── master-data/        # Port 8002 - Product catalog
├── cart/               # Port 8003 - Shopping cart
├── report/             # Port 8004 - Reports
├── journal/            # Port 8005 - Transaction logs
├── stock/              # Port 8006 - Inventory
├── commons/            # Shared library (kugel_common)
├── dapr/               # Dapr configuration
├── template/           # Service template
├── docker-compose.yaml
└── docker-compose.override.yaml
```

## Service Internal Structure
```
services/<service>/
├── app/
│   ├── main.py         # FastAPI application entry
│   ├── routers/        # API route handlers
│   ├── services/       # Business logic
│   ├── repositories/   # Database access
│   ├── schemas/        # Pydantic models
│   ├── models/         # Domain models
│   └── config/         # Settings
├── tests/
│   ├── conftest.py     # Pytest fixtures
│   └── test_*.py       # Test files
├── Pipfile             # Dependencies
├── Dockerfile
└── run.py              # Local run script
```

## Commons Library (kugel_common)
```
services/commons/src/kugel_common/
├── database/           # MongoDB helpers
├── utils/              # Utilities (HttpClientHelper, DaprClientHelper)
├── security/           # Authentication helpers
├── schemas/            # Shared schemas
└── exceptions/         # Custom exceptions
```
