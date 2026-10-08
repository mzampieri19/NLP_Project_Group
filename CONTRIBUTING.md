# Contributing

## One-time setup

```bash
make setup
```

This installs git hooks that run automatically:
- **pre-commit**: lints/formats Python (`ruff`) and notebooks (`nbqa`), strips notebook outputs (`nbstripout`), and checks for basic hygiene issues (trailing whitespace, large files, merge conflict markers, etc.)
- **commit-msg**: rejects commits whose message isn't a valid [Conventional Commit](https://www.conventionalcommits.org/)

## Commit message format

```
<type>(<optional scope>): <short description>

[optional body]
```

Common types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Examples:
```
feat: add BPE tokenizer for preprocessing pipeline
fix(eval): correct F1 calculation for multi-class labels
docs: update README with dataset download instructions
```

Tip: run `cz commit` instead of `git commit` to get an interactive prompt that builds the message for you.

## Before pushing

Hooks run automatically on `git commit`, but you can run everything manually at any time:

```bash
make check
```

CI re-runs the same checks (plus a commit-message check across the whole PR) on every push and pull request against `main`, so make sure this passes locally first.