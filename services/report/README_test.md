# Report Service Test Guide

## Test Environment Setup

### Local Testing (Host Machine)

1. Start MongoDB locally:
   ```bash
   docker-compose up -d mongodb redis
   
   # Initialize MongoDB replica set (first time only)
   ./scripts/init-mongodb-replica.sh
   ```

2. Run tests:
   ```bash
   cd report
   pipenv run pytest tests/ -v
   ```

   The tests will automatically use `mongodb://localhost:27017/` for local testing.

### Docker Testing

1. Start all services with Docker Compose:
   ```bash
   docker-compose up -d
   ```

2. Run tests inside the report container:
   ```bash
   docker-compose exec report pipenv run pytest tests/ -v
   ```

   In Docker environment, tests will use `mongodb://mongodb:27017/` automatically.

### Environment Variables

The following environment variables are configured automatically:

- **MONGODB_URI**: MongoDB connection string
  - Local: `mongodb://localhost:27017/`
  - Docker: `mongodb://mongodb:27017/`
- **TENANT_ID**: Test tenant ID (from .env.test)
- **DB_NAME_PREFIX**: `db_report`

### Troubleshooting

If MONGODB_URI is not being set correctly:

1. Check `.env.test` file exists and contains MONGODB_URI
2. For Docker testing, ensure docker-compose.override.yaml is being used
3. Check the test output for MongoDB URI being used