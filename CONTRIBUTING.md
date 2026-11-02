# Contributing

Thanks for helping out.

## Setup

```bash
make venv
make check
```

`make help` lists every command. `make check` runs what CI runs: ruff, mypy (strict) and pytest.

## Ground rules

- **Never copy silently.** Construction, indexing and slicing must not copy the buffer. Anything that copies is
  explicit and named for it (like `to_bytes()`), and documented.
- **Prove it with a test.** Changes that touch memory behavior need a test in `tests/test_zero_copy.py` checking
  that the original buffer sees the write or that `view.memory.obj` is the original object.
- **Measure before optimizing.** Include `make bench` numbers in the PR for performance changes.
- **No new runtime dependencies.** Dev and benchmark extras are fine.
- Keep public API small. Anything not exported from `pyzerocopy/__init__.py` is private.

## Pull requests

1. Branch from `main`, keep the change focused.
2. Add or update tests and the README if behavior changes.
3. Add a line under "Unreleased" in `CHANGELOG.md`.
4. Run `make check`.

## Releasing (maintainers)

1. Move "Unreleased" entries in `CHANGELOG.md` under the new version and bump `version` in `pyproject.toml`.
2. Commit, then tag: `git tag v0.1.0 && git push --tags`.
3. The `Release` workflow builds and publishes to PyPI via trusted publishing (configure the project on PyPI first).
