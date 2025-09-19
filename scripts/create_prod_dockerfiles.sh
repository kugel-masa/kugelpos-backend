#!/bin/bash

# Create optimized production Dockerfiles for all services

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SERVICES_DIR="$PROJECT_ROOT/services"

# Service to port mapping (all services expose port 8000 internally)
declare -A SERVICE_PORTS=(
    ["account"]=8000
    ["terminal"]=8001
    ["master-data"]=8002
    ["cart"]=8003
    ["report"]=8004
    ["journal"]=8005
    ["stock"]=8006
)

echo "Creating optimized production Dockerfiles..."

for service_dir in "$SERVICES_DIR"/*; do
    if [ -d "$service_dir" ]; then
        service_name=$(basename "$service_dir")

        # Skip non-service directories
        if [[ "$service_name" == "commons" || "$service_name" == "dapr" || "$service_name" == "template" ]]; then
            continue
        fi

        # Get external port for the service
        external_port=${SERVICE_PORTS[$service_name]}
        if [ -z "$external_port" ]; then
            echo "Warning: Unknown service $service_name, skipping..."
            continue
        fi

        echo "Creating Dockerfile.prod for $service_name (external port: $external_port)..."

        # Create Dockerfile.prod
        cat > "$service_dir/Dockerfile.prod" << 'EOF'
# Multi-stage build for production
# Stage 1: Builder
FROM python:3.12.11 as builder

WORKDIR /app

# Install pipenv
RUN pip install --no-cache-dir pipenv

# Copy dependency files
COPY Pipfile Pipfile.lock ./

# Install dependencies to a virtual environment
RUN PIPENV_VENV_IN_PROJECT=1 pipenv install --deploy --ignore-pipfile

# Stage 2: Runtime
FROM python:3.12-slim

# Install only necessary runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    locales \
    && echo "ja_JP.UTF-8 UTF-8" > /etc/locale.gen \
    && locale-gen ja_JP.UTF-8 \
    && update-locale LANG=ja_JP.UTF-8 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* \
    && rm -rf /var/tmp/*

# Set locale
ENV LC_ALL=ja_JP.UTF-8
ENV LANG=ja_JP.UTF-8
ENV LANGUAGE=ja_JP.UTF-8
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Add .venv/bin to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Copy only necessary application files
COPY app/ ./app/
COPY run.py ./

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Use the virtual environment's uvicorn
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

        # Create .dockerignore if it doesn't exist or update it
        if [ ! -f "$service_dir/.dockerignore" ] || [ $(wc -l < "$service_dir/.dockerignore") -lt 50 ]; then
            echo "Creating/updating .dockerignore for $service_name..."
            cat > "$service_dir/.dockerignore" << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
.pytest_cache/
*.egg-info/
dist/
build/
*.egg

# Virtual environments
.venv/
venv/
ENV/
env/

# Testing
tests/
test_*.py
*_test.py
pytest.ini
.coverage
htmlcov/
.tox/
.hypothesis/

# Documentation
*.md
docs/
*.rst
LICENSE

# IDEs
.vscode/
.idea/
*.swp
*.swo
*.swn
.DS_Store

# Git
.git/
.gitignore
.gitattributes

# Docker
Dockerfile*
docker-compose*.yml
.dockerignore

# Logs
*.log
logs/

# Environment files
.env*
!.env.example

# CI/CD
.github/
.gitlab-ci.yml
.travis.yml

# Scripts
scripts/
*.sh
run_all_tests.sh

# Temporary files
tmp/
temp/
*.tmp
*.bak
*.backup

# Configuration files for development
.pre-commit-config.yaml
.editorconfig
.eslintrc*
.prettierrc*
pyproject.toml
setup.cfg
setup.py
tox.ini
mypy.ini
.pylintrc
.ruff.toml

# Dapr
dapr/

# Charts
charts/
EOF
        fi
    fi
done

echo "Production Dockerfiles created successfully!"
echo ""
echo "To build a production image, use:"
echo "  docker build -f services/<service>/Dockerfile.prod -t <service>:prod services/<service>/"
echo ""
echo "Or use the build script with --prod flag (after it's updated)"