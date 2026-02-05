# Suggested Commands

## Quick Start
```bash
cd scripts
./build.sh              # Build all services
./start.sh              # Start all services
./stop.sh               # Stop all services
./stop.sh --clean       # Stop and clean all data
```

## Building
```bash
./scripts/build.sh                    # Build all services
./scripts/build.sh cart journal       # Build specific services
./scripts/build.sh --no-cache         # Build without cache
./scripts/build.sh --parallel         # Build in parallel
```

## Testing
```bash
# All services
./scripts/run_all_tests.sh
./scripts/run_all_tests_with_progress.sh

# Single service
cd services/cart
pipenv run pytest tests/ -v
pipenv run pytest tests/test_cart.py -v
pipenv run pytest tests/ -k "test_add_item" -v

# With coverage
pipenv run pytest --cov=app tests/
```

## Code Quality
```bash
cd services/<service>
pipenv run ruff check app/           # Check for issues
pipenv run ruff check --fix app/     # Auto-fix issues
pipenv run ruff format app/          # Format code
```

## Service Logs
```bash
cd services
docker-compose logs -f              # All services
docker-compose logs -f cart         # Specific service
docker-compose logs --tail=100 cart # Last 100 lines
```

## Database
```bash
docker exec -it mongodb mongosh
./scripts/reset-mongodb.sh
./scripts/init-mongodb-replica.sh
```

## Local Development
```bash
cd services/<service>
pipenv install
pipenv run python run.py
# or
pipenv run uvicorn app.main:app --reload --host 0.0.0.0 --port <PORT>
```

## Commons Library
```bash
./scripts/update_common_and_rebuild.sh  # Update commons in all services
./scripts/rebuild_pipenv.sh             # Rebuild all virtual environments
```

## Azure Deployment
```bash
./scripts/build-and-push-azure.sh -t <VERSION> --push
./scripts/update-azure-container-apps.sh -t <VERSION>
./scripts/check_service_health.sh -a <DOMAIN> -v
```
