# Source Control Agent — Actionable Tasks

> This agent handles Git workflows, branch management, PR reviews, merge strategies, and repository hygiene.

---

## Identity & Scope

- **Name:** Source Control Agent
- **Tools:** Git, GitHub CLI (`gh`), GitHub Actions
- **Responsibilities:** Branch strategy, code review, merge management, release tagging, repo hygiene

---

## Verification Commands

```bash
# Repository status
git status
git log --oneline -20
git branch -a

# Check for uncommitted changes
git diff --stat

# Check remote status
git fetch --all
git log --oneline origin/main..HEAD

# List stale branches
git branch --merged main | grep -v main
```

---

## Priority Tasks

### P0 — Branch Cleanup

- [ ] **Audit all remote branches**
  ```bash
  git branch -r --sort=-committerdate | head -20
  ```
  - Identify branches older than 30 days
  - Identify merged branches that can be deleted
  - Document active branches and their purpose

- [ ] **Define branch naming convention**
  ```
  feature/<description>     # New features
  fix/<description>         # Bug fixes
  security/<description>    # Security patches
  docs/<description>        # Documentation
  refactor/<description>    # Code refactoring
  test/<description>        # Test additions
  ```

- [ ] **Set up branch protection on `main`**
  - Require PR reviews (1 reviewer minimum)
  - Require status checks to pass (CI)
  - Prevent force pushes
  - Require linear history (squash merges)

### P1 — Git Hygiene

- [ ] **Review and update `.gitignore`**
  Current state is good but verify:
  ```gitignore
  # Verify these are ignored:
  *.pyc
  __pycache__/
  .env
  node_modules/
  dist/
  build/
  *.db
  *.sqlite3
  .coverage
  htmlcov/
  .pytest_cache/
  .mypy_cache/
  credentials.json
  *.pem
  *.key
  ```

- [ ] **Remove sensitive data from git history**
  - The hardcoded password in `predict_props.py` may exist in git history
  - Use `git filter-branch` or `bfg-repo-cleaner` to remove
  ```bash
  # After fixing the file:
  bfg --replace-text passwords.txt
  git reflog expire --expire=now --all
  git gc --prune=now --aggressive
  ```
  - **WARNING:** This rewrites history — coordinate with all contributors

- [ ] **Add pre-commit hooks**
  ```bash
  pip install pre-commit
  ```
  Create `.pre-commit-config.yaml`:
  ```yaml
  repos:
    - repo: https://github.com/astral-sh/ruff-pre-commit
      rev: v0.1.0
      hooks:
        - id: ruff
          args: [--fix]
    - repo: https://github.com/psf/black
      rev: 23.9.1
      hooks:
        - id: black
    - repo: https://github.com/pre-commit/pre-commit-hooks
      rev: v4.5.0
      hooks:
        - id: check-added-large-files
          args: [--maxkb=500]
        - id: detect-private-key
        - id: check-merge-conflict
        - id: trailing-whitespace
        - id: end-of-file-fixer
  ```

### P2 — PR Workflow

- [ ] **Create PR template** `.github/PULL_REQUEST_TEMPLATE.md`
  ```markdown
  ## Description
  <!-- What does this PR do? -->

  ## Type of Change
  - [ ] Bug fix
  - [ ] New feature
  - [ ] Refactor
  - [ ] Documentation
  - [ ] Security fix

  ## Testing
  - [ ] Unit tests added/updated
  - [ ] Integration tests added/updated
  - [ ] Manual testing performed

  ## Checklist
  - [ ] Code follows project style guide
  - [ ] No hardcoded credentials
  - [ ] Type hints added to new functions
  - [ ] Docstrings added to new classes/methods
  - [ ] AGENTS.md updated (if applicable)
  ```

- [ ] **Create issue templates**
  - Bug report template
  - Feature request template
  - Security vulnerability template

### P3 — Release Management

- [ ] **Define versioning strategy** (Semantic Versioning)
  ```
  v1.0.0 — Initial stable release
  v1.1.0 — New features (backward compatible)
  v1.1.1 — Bug fixes
  v2.0.0 — Breaking changes
  ```

- [ ] **Create release workflow** `.github/workflows/release.yml`
  ```yaml
  name: Release
  on:
    push:
      tags:
        - 'v*'
  jobs:
    release:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4
        - name: Create Release
          uses: actions/create-release@v1
          with:
            tag_name: ${{ github.ref }}
            release_name: Release ${{ github.ref }}
            draft: false
            prerelease: false
  ```

- [ ] **Document release process**
  ```bash
  # 1. Update version
  # 2. Create tag
  git tag -a v1.0.0 -m "Release v1.0.0"
  git push origin v1.0.0
  # 3. GitHub Actions creates release automatically
  ```

### P4 — Commit Standards

- [ ] **Adopt Conventional Commits**
  ```
  feat: add Kelly criterion optimizer
  fix: correct DvP rank calculation
  docs: update API endpoint documentation
  test: add multivariate Kelly unit tests
  refactor: extract RLM detection to helper
  security: remove hardcoded credentials
  perf: batch Google Sheets format requests
  ci: add backend test workflow
  ```

- [ ] **Add commitlint** for enforcement
  ```bash
  npm install -D @commitlint/cli @commitlint/config-conventional
  ```
  Create `commitlint.config.js`:
  ```javascript
  module.exports = {
    extends: ['@commitlint/config-conventional'],
    rules: {
      'subject-max-length': [2, 'always', 100],
    },
  };
  ```

---

## Repository Audit Checklist

Run periodically:

- [ ] No secrets in source code (`git secrets --scan`)
- [ ] No large binary files (> 1MB) tracked
- [ ] All branches have clear purpose
- [ ] Merged branches are deleted
- [ ] `.gitignore` covers all generated files
- [ ] Branch protection rules enforced
- [ ] CI passing on main branch
- [ ] CODEOWNERS file defined (if team > 1)
- [ ] Release tags consistent with semantic versioning
- [ ] README.md up to date with current architecture

---

## Emergency Procedures

### Revert a Bad Merge
```bash
git revert -m 1 <merge-commit-sha>
git push origin main
```

### Fix a Broken Main Branch
```bash
git bisect start
git bisect bad HEAD
git bisect good <last-known-good-sha>
# Git will find the breaking commit
```

### Remove Accidentally Committed Secret
```bash
# 1. Fix the file immediately
# 2. Rotate the compromised credential
# 3. Clean git history (see P1 above)
# 4. Force push (coordinate with team)
git push --force-with-lease origin main
```
