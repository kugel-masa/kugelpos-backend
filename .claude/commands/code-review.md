---
description: Code review for PRs or specified files
---

## User Input

```text
$ARGUMENTS
```

**Usage:** `/code-review [PR_NUMBER | FILE_PATH...] [OPTIONS]`

**Examples:**
- `/code-review 42` → Review PR #42
- `/code-review services/cart/app/api/v1/cart.py` → Review specific file
- `/code-review --staged` → Review staged changes
- `/code-review --branch feature/new-api` → Review branch diff

## Review Checklist

### 1. Code Quality
- [ ] PEP 8 compliant (checked with ruff)
- [ ] Type hints used appropriately
- [ ] Functions/methods follow single responsibility principle
- [ ] Magic numbers are defined as constants
- [ ] Proper error handling in place

### 2. Security (OWASP Top 10)
- [ ] SQL/NoSQL injection prevention
- [ ] XSS prevention (user input sanitization)
- [ ] Proper authentication/authorization implementation
- [ ] No hardcoded secrets (API keys, passwords)
- [ ] Proper input validation

### 3. Performance
- [ ] No N+1 query issues
- [ ] Appropriate indexes used
- [ ] No unnecessary loops or duplicate processing
- [ ] async/await used appropriately

### 4. Architecture (Project Specific)
- [ ] Follows Repository pattern
- [ ] State Machine pattern (cart) correctly implemented
- [ ] Multi-tenancy support (proper tenant_id usage)
- [ ] Dapr pub/sub topic naming conventions followed
- [ ] Error code format (XXYYZZ) compliance

### 5. Testing
- [ ] Tests added/updated
- [ ] Edge cases covered
- [ ] Mocks used appropriately

## Commands

### PR Review
```bash
# Get PR diff
gh pr diff <PR_NUMBER>

# List PR files
gh pr view <PR_NUMBER> --json files -q '.files[].path'

# View PR comments
gh pr view <PR_NUMBER> --comments
```

### Local Changes Review
```bash
# Staged changes
git diff --staged

# Diff against specific branch
git diff main...<BRANCH_NAME>

# List changed files
git diff --name-only main
```

### Code Style Check
```bash
cd services/<service>
pipenv run ruff check app/
pipenv run ruff format --check app/
```

## Review Output Format

Output review results in the following format:

```markdown
## Code Review Summary

### Files Reviewed
- `path/to/file1.py` - Change summary
- `path/to/file2.py` - Change summary

### Findings

#### 🔴 Critical (Must Fix)
- **[Security]** `file.py:42` - Description

#### 🟡 Warning (Should Fix)
- **[Performance]** `file.py:100` - Description

#### 🔵 Suggestion (Nice to Have)
- **[Style]** `file.py:15` - Description

#### ✅ Good Practices
- Proper error handling
- Good use of type hints

### Verdict
- [ ] Approve
- [ ] Request Changes
- [ ] Comment Only
```

## Integration with GitHub

Post review comments to GitHub after completion:

```bash
# Add review comment to PR
gh pr review <PR_NUMBER> --comment --body "Review content"

# Approve PR
gh pr review <PR_NUMBER> --approve --body "LGTM"

# Request changes
gh pr review <PR_NUMBER> --request-changes --body "Change request details"
```
