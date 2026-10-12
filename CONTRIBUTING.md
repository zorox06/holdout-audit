# Contributing

Holdout Audit favors small checks with transparent evidence over broad claims about model safety.

## Run locally

Python 3.10+ is sufficient; no runtime or test dependencies are required.

```bash
python -m unittest discover -s tests -v
python -m holdout_audit demo --output report.html
python -m holdout_audit demo --clean --output clean-report.html
```

## A useful pull request includes

1. The problem and evaluation goal your change addresses.
2. A minimal synthetic fixture that fails before the change and passes after it.
3. A counterexample where similar-looking data is legitimate.
4. Evidence that missing or unparseable data cannot silently pass.
5. Updated documentation for any changed CLI, JSON, or comparison behavior.

Keep real customer data, personal information, credentials, and proprietary datasets out of issues and fixtures. Use synthetic values. Reports must continue to omit raw cell values and escape metadata in HTML.

## Good first contributions

- Add adversarial CSV, timestamp, and CLI fixtures.
- Improve explanations for group-aware versus known-entity evaluation.
- Propose a configurable minimum time gap with boundary tests.
- Design a streaming comparison mode with an explicit correctness and memory contract.

Discuss new dependencies and approximate matching before implementing them. Exact string equality is an intentional v0.1 behavior.
