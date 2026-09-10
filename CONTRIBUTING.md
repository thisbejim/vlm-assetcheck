# Contributing

Bug reports and small, focused pull requests are welcome. Please include a minimal JSONL fixture (or a reproducible fixture generator) and the expected diagnostic code when changing discovery or validation behavior.

Before opening a pull request, run:

```bash
pytest
ruff check .
mypy src
python -m build
```

Keep the core dependency-free. New format support should be a bounded header check with a regression test; do not add a network fetch, codec invocation, or automatic data rewrite.
