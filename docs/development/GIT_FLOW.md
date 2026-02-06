# Git Flow

This project follows a simplified **Trunk-Based Development** workflow. All feature, bug fix, and hotfix branches are created from and merged back into the `master` branch.

## Branch Naming Conventions

When creating a new branch, follow these naming conventions to clearly reflect the type of changes:

### Feature Branch
Use for developing new features.

```
feature/<feature-description>
```

**Examples:**
- `feature/add-giassi-scraper`
- `feature/implement-incremental-pricing`
- `feature/add-azure-blob-sync`

### Bugfix Branch
Use for resolving non-urgent bugs.

```
bugfix/<bug-description>
```

**Examples:**
- `bugfix/fix-empty-struct-serialization`
- `bugfix/correct-duckdb-connection-timeout`
- `bugfix/handle-missing-postal-codes`

### Hotfix Branch
Use for critical and urgent fixes that require immediate attention.

```
hotfix/<hotfix-description>
```

**Examples:**
- `hotfix/fix-api-rate-limit-exceeded`
- `hotfix/patch-production-scraper-crash`

---

## Pull Requests (PR)

All code changes must be integrated via Pull Requests. Follow these guidelines:

### 1. Target Branch
Always set the base branch of your Pull Request to `master`.

### 2. Assign Reviewers
Assign appropriate team members as reviewers to ensure thorough review and maintain code quality.

### 3. PR Description Template

Use this template for your PR description:

```markdown
## Description
Brief description of what this PR does and why.

## Type of Change
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Code refactoring

## Changes Made
- Bullet point list of specific changes

## Testing
- [ ] dbt tests passed (`dbt test`)
- [ ] Python tests passed (`pytest`)
- [ ] sqlfluff lint passed
- [ ] Manual validation performed

## Data Quality
- [ ] Row counts validated
- [ ] NULL values explained
- [ ] No data loss detected

## Documentation
- [ ] Updated CLAUDE.md if needed
- [ ] Added/updated dbt model descriptions
- [ ] Updated YAML metadata
- [ ] No breaking changes to contracts

## Screenshots (if applicable)
Add screenshots to help reviewers understand visual changes.

## Related Issues
Closes #<issue_number>
```

---

## Testing and Validation

Before submitting a Pull Request, ensure:

### DBT Projects
```bash
cd src/transform/dbt_project

# Parse and validate SQL
dbt parse

# Compile models
dbt compile

# Run data tests
dbt test

# Lint SQL (optional, recommended)
sqlfluff lint models/
```

### Python Code
```bash
# Run tests
pytest tests/ -v

# Check code quality
flake8 src/
black src/ --check
```

### Pre-commit Checklist
- [ ] Unit tests executed and passed
- [ ] Integration tests executed and passed
- [ ] Manual tests performed and validated
- [ ] Documentation updated
- [ ] No secrets or credentials committed

---

## Review and Approval

All Pull Requests must be reviewed and approved by at least one team member:

1. **Address Feedback**: Respond to all comments and suggestions from reviewers promptly
2. **CI Validation**: Ensure all CI/CD checks pass (tests, linting, build)
3. **Final Approval**: Only merge after receiving explicit approval
4. **Merge Strategy**: Use "Squash and Merge" for clean commit history

### Review Focus Areas
- **Code Quality**: Readability, maintainability, best practices
- **Testing**: Adequate test coverage and validation
- **Documentation**: Clear descriptions and updated docs
- **Performance**: No obvious performance regressions
- **Security**: No security vulnerabilities introduced

---

## Commit Message Guidelines

Use clear, descriptive commit messages following this format:

```
<type>: <subject>

<body>
```

### Types
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `refactor`: Code refactoring
- `test`: Adding/updating tests
- `chore`: Maintenance tasks

### Examples
```
feat: add Giassi supermarket scraper

Implemented VTEXScraper for Giassi with 17 regions support.
Includes global discovery mode and batch processing.

fix: handle empty struct fields in Parquet serialization

PyArrow cannot serialize empty dict types to Parquet.
Added _clean_empty_structs() to recursively remove empty dicts.
Fixes error: "Cannot write struct type with no child field"
```

---

## Branching Best Practices

1. **Keep Branches Short-Lived**: Merge within 2-3 days when possible
2. **Stay Up-to-Date**: Regularly rebase on `master` to minimize conflicts
3. **Small, Focused Changes**: One feature/fix per branch
4. **Delete After Merge**: Clean up merged branches to keep repository tidy

```bash
# Update your branch with latest master
git checkout master
git pull origin master
git checkout feature/your-branch
git rebase master

# After merge, delete local and remote branch
git branch -d feature/your-branch
git push origin --delete feature/your-branch
```

---

## Emergency Hotfix Procedure

For critical production issues:

1. **Create Hotfix Branch**: `hotfix/critical-issue-description`
2. **Fast-Track Review**: Tag reviewers immediately
3. **Expedited Testing**: Run critical path tests only
4. **Deploy ASAP**: Merge and deploy once validated
5. **Post-Mortem**: Document incident and prevention measures

---

This workflow ensures high-quality standards, collaborative improvement, and maintainable codebase across the project.
