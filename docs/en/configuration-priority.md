# Configuration Priority Guide

This document explains the priority order of configuration settings in Kugelpos, particularly for database connection strings and other environment variables.

## Overview

Kugelpos uses a hierarchical configuration system that allows settings to be defined in multiple places. When the same setting is defined in multiple locations, the system follows a specific priority order to determine which value to use.

## Configuration Priority Order (Highest to Lowest)

### 1. Environment Variables (Highest Priority)
Environment variables set at runtime always take the highest priority. These can be set in multiple ways:

#### a. Docker Compose Override (docker-compose.override.yaml)
```yaml
services:
  cart:
    environment:
      - MONGODB_URI=mongodb://mongodb:27017/?replicaSet=rs0
      - DB_NAME_PREFIX=db_cart
```

#### b. Docker Compose Base (docker-compose.yaml)
```yaml
services:
  cart:
    environment:
      - BASE_URL_MASTER_DATA=http://localhost:3500/v1.0/invoke/master-data/method/api/v1
```

#### c. System Environment Variables
```bash
export MONGODB_URI=mongodb://localhost:27017/?replicaSet=rs0
./start.sh
```

### 2. .env Files (Medium Priority)
Each service can have its own `.env` file in its directory:
```bash
services/cart/.env
services/account/.env
services/terminal/.env
# etc.
```

Example `.env` file content:
```env
MONGODB_URI=mongodb://localhost:27017/?replicaSet=rs0
DB_NAME_PREFIX=db_cart
TOKEN_URL=http://localhost:8000/api/v1/accounts/token
```

**Note**: As of version 0.0.206, `.env` files are optional. The `env_file` configuration in docker-compose.yaml includes `required: false`.

### 3. Service-Specific Settings (Low Priority)
Each service defines its own settings with default values in `app/config/settings.py`:

```python
class Settings(
    AppSettings,
    DBSettings, 
    DBCollectionCommonSettings,
    # ... other settings
):
    # Override required fields with defaults
    MONGODB_URI: str = Field(default="mongodb://localhost:27017/?replicaSet=rs0")
    DB_NAME_PREFIX: str = Field(default="db_cart")
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,  # Ignore empty values from .env file
        extra="allow",
    )
```

### 4. Common Settings Defaults (Lowest Priority)
The shared `kugel_common` library provides base default values:

```python
# kugel_common/config/settings_database.py
class DBSettings(BaseSettings):
    MONGODB_URI: str = "mongodb://localhost:27017/?replicaSet=rs0"
    DB_NAME_PREFIX: str = "db_common"
    # ... other defaults
```

## Practical Examples

### Example 1: MongoDB URI Resolution
For the cart service, the `MONGODB_URI` could be defined in:

1. **docker-compose.override.yaml**: `mongodb://mongodb:27017/?replicaSet=rs0` ✅ (Used)
2. **services/cart/.env**: `mongodb://localhost:27017/?replicaSet=rs0` (Ignored)
3. **services/cart/app/config/settings.py**: `mongodb://localhost:27017/?replicaSet=rs0` (Ignored)
4. **kugel_common/config/settings_database.py**: `mongodb://localhost:27017/?replicaSet=rs0` (Ignored)

### Example 2: Custom Configuration
If you need a custom MongoDB URI for testing:

```bash
# Method 1: Environment variable (highest priority)
MONGODB_URI=mongodb://test-server:27017/?replicaSet=rs0 docker-compose up cart

# Method 2: Create .env file (medium priority)
echo "MONGODB_URI=mongodb://test-server:27017/?replicaSet=rs0" > services/cart/.env
docker-compose up cart
```

## Configuration Locations Summary

| Setting Type | Location | Priority | Required |
|-------------|----------|----------|----------|
| Runtime Environment | OS environment variables | Highest | No |
| Docker Override | docker-compose.override.yaml | High | No |
| Docker Base | docker-compose.yaml | High | No |
| Service .env | services/{service}/.env | Medium | No |
| Service Defaults | services/{service}/app/config/settings.py | Low | Yes |
| Common Defaults | kugel_common/config/settings_database.py | Lowest | Yes |

## Key Settings

### Database Settings
- `MONGODB_URI`: MongoDB connection string
- `DB_NAME_PREFIX`: Database name prefix (e.g., "db_cart", "db_account")
- `DB_MAX_POOL_SIZE`: Maximum connection pool size (default: 100)
- `DB_MIN_POOL_SIZE`: Minimum connection pool size (default: 10)

### Service URLs
- `BASE_URL_MASTER_DATA`: Master data service URL
- `BASE_URL_TERMINAL`: Terminal service URL
- `BASE_URL_CART`: Cart service URL
- `BASE_URL_REPORT`: Report service URL
- `BASE_URL_JOURNAL`: Journal service URL
- `TOKEN_URL`: Authentication token endpoint URL

### Authentication Settings
- `SECRET_KEY`: JWT secret key (default: "1234567890" - change in production!)
- `ALGORITHM`: JWT algorithm (default: "HS256")
- `TOKEN_EXPIRE_MINUTES`: Token expiration time (default: 30)

## Best Practices

1. **Production Environment**: Use environment variables or Docker secrets for sensitive data
2. **Development Environment**: Use `.env` files for convenience
3. **Testing**: Use docker-compose.override.yaml for consistent test environments
4. **Defaults**: Ensure service defaults are safe and functional for development

## Troubleshooting

### How to check which configuration is being used:

1. **Check environment variables in running container:**
```bash
docker-compose exec cart env | grep MONGODB_URI
```

2. **View logs during startup:**
```bash
docker-compose logs cart | grep "Connected to MongoDB"
```

3. **Debug configuration loading:**
```python
# Add to your service code temporarily
from app.config.settings import settings
print(f"MONGODB_URI: {settings.MONGODB_URI}")
print(f"DB_NAME_PREFIX: {settings.DB_NAME_PREFIX}")
```

## Version History

- **v0.0.206**: Made `.env` files optional, added `env_ignore_empty=True` to all services
- **v0.0.205**: Added default values to kugel_common DBSettings
- **Earlier versions**: Required `.env` files for each service