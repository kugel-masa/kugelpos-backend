# Kugelpos Configuration Priority Specification

## Overview

The Kugelpos system reads values from multiple configuration sources and determines final configuration values based on clear priority to achieve flexible configuration management.

## Configuration Loading Priority (High → Low)

### 1. Environment Variables (Highest Priority)

**Docker Compose Override Settings:**
```yaml
# docker-compose.override.yaml
services:
  cart:
    environment:
      - MONGODB_URI=mongodb://localhost:27017/?replicaSet=rs0
      - DB_NAME_PREFIX=db_cart_dev
```

**System Environment Variables:**
```bash
export MONGODB_URI="mongodb://production:27017/?replicaSet=rs0"
export JWT_SECRET_KEY="production-secret-key"
```

### 2. .env Files (Medium Priority)

**Service-specific Settings:**
```bash
# /services/cart/.env
MONGODB_URI=mongodb://localhost:27017/?replicaSet=rs0
DB_NAME_PREFIX=db_cart
DAPR_HTTP_PORT=3500
JWT_SECRET_KEY=your-secret-key
```

### 3. Configuration Class Default Values (Low Priority)

**Implementation Example:**
```python
# /services/cart/app/config/settings.py
class Settings(AppSettings, DBSettings):
    MONGODB_URI: str = Field(default="mongodb://localhost:27017/?replicaSet=rs0")
    DB_NAME_PREFIX: str = Field(default="db_cart")
    DAPR_HTTP_PORT: int = Field(default=3500)
```

### 4. Common Settings (Lowest Priority)

**kugel_common Base Settings:**
```python
# /services/commons/src/kugel_common/config/base_settings.py
class BaseSettings:
    LOG_LEVEL: str = Field(default="INFO")
    HTTP_TIMEOUT: int = Field(default=30)
```

## Important Changes in v0.0.206 and Later

### Making .env Files Optional

**Before Change:** .env files were required
**After Change:** Services can start without .env files

**Fallback Order:**
1. Environment variables (docker-compose.override.yaml)
2. Environment variables (docker-compose.yaml)
3. .env files (if present)
4. Configuration class default values

## Service-specific Configuration Examples

### Cart Service Configuration

```python
class CartSettings(AppSettings, DBSettings):
    # MongoDB settings
    MONGODB_URI: str = Field(default="mongodb://localhost:27017/?replicaSet=rs0")
    DB_NAME_PREFIX: str = Field(default="db_cart")
    
    # Dapr settings
    DAPR_HTTP_PORT: int = Field(default=3500)
    
    # Service-specific settings
    CART_TTL_SECONDS: int = Field(default=36000)  # 10 hours
    MAX_ITEMS_PER_CART: int = Field(default=100)
```

**Priority Application Example:**
```bash
# Override with environment variables
export DB_NAME_PREFIX="db_cart_test"
export CART_TTL_SECONDS="7200"  # Change to 2 hours

# Result: Test environment configuration values are applied
```

### Terminal Service Configuration

```python
class TerminalSettings(AppSettings, DBSettings):
    MONGODB_URI: str = Field(default="mongodb://localhost:27017/?replicaSet=rs0")
    DB_NAME_PREFIX: str = Field(default="db_terminal")
    
    # API key settings
    API_KEY_LENGTH: int = Field(default=32)
    API_KEY_EXPIRY_DAYS: int = Field(default=365)
```

## Configuration Validation and Error Handling

### Pydantic Configuration Validation

```python
class Settings(BaseSettings):
    @validator('MONGODB_URI')
    def validate_mongodb_uri(cls, v):
        if not v.startswith('mongodb://'):
            raise ValueError('MONGODB_URI must start with mongodb://')
        return v
    
    @validator('JWT_SECRET_KEY')
    def validate_jwt_secret(cls, v):
        if len(v) < 32:
            raise ValueError('JWT_SECRET_KEY must be at least 32 characters')
        return v
```

### Configuration Loading Errors

```python
try:
    settings = Settings()
except ValidationError as e:
    logger.error(f"Configuration validation failed: {e}")
    raise ConfigurationException("Invalid configuration")
```

## Development, Test, and Production Environment Support

### Development Environment

```yaml
# docker-compose.override.yaml
services:
  cart:
    environment:
      - LOG_LEVEL=DEBUG
      - DB_NAME_PREFIX=db_cart_dev
      - ENABLE_CORS=true
```

### Test Environment

```bash
# .env.test
MONGODB_URI=mongodb://test-mongo:27017/?replicaSet=rs0
DB_NAME_PREFIX=db_cart_test
LOG_LEVEL=WARNING
```

### Production Environment

```bash
# Set sensitive information with environment variables
export MONGODB_URI="${MONGODB_CONNECTION_STRING}"
export JWT_SECRET_KEY="${JWT_SECRET_FROM_VAULT}"
export LOG_LEVEL="ERROR"
```

## Configuration Management Best Practices

### 1. Managing Sensitive Information

```python
# Sensitive information only in environment variables
JWT_SECRET_KEY: str = Field(..., env="JWT_SECRET_KEY")
DATABASE_PASSWORD: str = Field(..., env="DB_PASSWORD")

# Do not include in .env files
# Also avoid in docker-compose.override.yaml
```

### 2. Environment-specific Configuration Separation

```python
class EnvironmentSettings:
    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"
    
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"
```

### 3. Configuration Value Validation

```python
@validator('DAPR_HTTP_PORT')
def validate_port(cls, v):
    if not 1024 <= v <= 65535:
        raise ValueError('Port must be between 1024 and 65535')
    return v
```

## Troubleshooting

### Common Configuration Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Service startup fails | Missing required settings | Check environment variables |
| Wrong database connection | Misunderstanding configuration priority | Re-verify priority order |
| CORS errors | Development environment setup issue | Set ENABLE_CORS=true |

### Configuration Debugging

```python
# Display current configuration values
settings = Settings()
logger.info(f"Current settings: {settings.dict()}")

# Check configuration source
logger.info(f"MongoDB URI source: {settings.__fields__['MONGODB_URI'].field_info}")
```

## Configuration Example Templates

### Minimal .env Configuration

```bash
# Basic service configuration
MONGODB_URI=mongodb://localhost:27017/?replicaSet=rs0
DB_NAME_PREFIX=db_service_name
LOG_LEVEL=INFO
```

### Complete Development Environment Configuration

```bash
# Detailed development environment configuration
MONGODB_URI=mongodb://localhost:27017/?replicaSet=rs0
DB_NAME_PREFIX=db_cart_dev
DAPR_HTTP_PORT=3500
LOG_LEVEL=DEBUG
ENABLE_CORS=true
JWT_SECRET_KEY=development-secret-key-32chars
HTTP_TIMEOUT=30
CIRCUIT_BREAKER_THRESHOLD=3
```

Through this configuration priority system, Kugelpos achieves flexible configuration management across development, test, and production environments.