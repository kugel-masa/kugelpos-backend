# Task Completion Checklist

## Before Committing Code

### 1. Code Quality
- [ ] Run linting: `pipenv run ruff check app/`
- [ ] Run formatting: `pipenv run ruff format app/`
- [ ] Fix all linting errors

### 2. Testing
- [ ] Run tests for affected service: `pipenv run pytest tests/ -v`
- [ ] Ensure all tests pass
- [ ] Add tests for new functionality

### 3. Code Review Self-Check
- [ ] Type hints added for new functions
- [ ] No commented-out code
- [ ] Comments in English
- [ ] No hardcoded secrets or credentials
- [ ] Proper error handling

### 4. MongoDB Aggregation Pipelines (if applicable)
- [ ] Check for multiple `$unwind` operations
- [ ] Use `$addToSet` (not `$push`) after Cartesian products
- [ ] Test with multiple payments AND multiple taxes
- [ ] Verify amounts are not multiplied

## Git Conventions
- Commit messages in English
- Branch naming: `feature/*`, `bugfix/*`, `hotfix/*`
- PR descriptions explain "why" not just "what"

## After Completing Feature
- [ ] Update documentation if needed
- [ ] Update CLAUDE.md if new patterns/commands added
- [ ] Consider if commons library needs updates
