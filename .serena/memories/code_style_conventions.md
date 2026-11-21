# Code Style and Conventions

## Language Usage
- **Code comments and log messages**: English only
- **Documentation**: Primary in English, supplementary in Japanese
- **Variable/function names**: English only
- **Error messages**: Support both English and Japanese

## Python Code Style
- Follow **PEP 8**
- Use **type hints** for function parameters and return values
- Use **async/await** patterns for all database operations
- No commented-out code in production
- Linting tool: **ruff**

## Naming Conventions
- Files: `snake_case.py`
- Classes: `PascalCase`
- Functions/methods: `snake_case`
- Variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Test files: `test_*.py`

## Project Patterns
- **Repository Pattern**: Database access via `AbstractRepository`
- **Document Models**: Inherit from `BaseDocumentModel`
- **API Schemas**: Pydantic models for request/response
- **Transformers**: Convert between internal models and API schemas

## Error Codes
Format: `XXYYZZ`
- XX: Error category (10=general, 20=auth, 30=validation, 40=business rule, 50=database, 60=external, 90=system)
- YY: Subcategory; business-rule services own ranges (cart 401-404, master-data 405, terminal 406-407, account 408-409, journal 410-411, report 412-413, stock 414-415)
- ZZ: Specific error number

## Security Guidelines
- Never commit secrets or API keys
- Use environment variables for configuration
- Hash API keys before storage
- Validate all inputs at endpoints

## MongoDB Aggregation Critical Rule
**NEVER use `$push` after multiple `$unwind` operations** - Use `$addToSet` to avoid Cartesian product bugs (see Issue #78).
