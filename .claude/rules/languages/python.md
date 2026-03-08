---
paths:
  - "**/*.py"
---

# Python Standards

## Package Management

- Use uv as default package manager
- Forbid pip, poetry for new projects (prevent toolchain fragmentation)
- `uv sync` in CI (frozen lockfile equivalent)
- `uv run` to execute commands in managed environment

## Python Version

- Minimum: 3.12 (required for PEP 695 type syntax)
- Use modern syntax available in 3.12+: `type` statement, `X | Y` unions, built-in generics

## Project Structure

- `pyproject.toml` as single config file (no setup.py, setup.cfg, requirements.txt)
- Use `src/` layout to catch packaging errors early

```
project/
  pyproject.toml
  uv.lock
  src/
    package_name/
      __init__.py
      domain/
        __tests__/
          test_service.py
        service.py
```

### Dependency Groups

- Separate dev/test dependencies from production using `[dependency-groups]`
- Never ship test frameworks or linters to production

```toml
[dependency-groups]
dev = ["pytest>=8.0", "ruff>=0.9", "pyright>=1.1"]
```

## File Structure

1. Module docstring (if public API)
2. `from __future__` imports (only if needed)
3. Standard library imports
4. Third-party imports
5. Local imports
6. Constants (UPPER_SNAKE_CASE, alphabetically ordered)
7. Type aliases (`type` statement)
8. Main content

### Inside Classes

- Class-level constants
- Class variables with type annotations
- `__init__`
- `__post_init__` / validators
- Public methods (alphabetically ordered)
- Private methods (alphabetically ordered)

## Type System

### Full Type Annotations Required

Annotate all function signatures (parameters + return). Skip annotations only for local variables where type is obvious from assignment.

### Use Modern Syntax Only

- `X | None` not `Optional[X]`
- `X | Y` not `Union[X, Y]`
- `list[int]` not `List[int]`
- `type Vector = list[float]` not `TypeAlias`
- `def first[T](items: Sequence[T]) -> T` for generics (PEP 695)

### Banned Legacy Patterns

- `typing.Optional`, `typing.Union`, `typing.List`, `typing.Dict`, `typing.Tuple`, `typing.Set`
- `typing.TypeAlias` — use `type` statement

### Parameter vs Return Types

- Parameters: prefer abstract types (`Sequence`, `Mapping`, `Iterable` from `collections.abc`)
- Return values: use concrete types (`list`, `dict`)

### AI Type Safety Enforcement

AI frequently drops type annotations for brevity. Require strict adherence:

- **Every `Any` needs a comment**: `# Any: external API returns untyped response`
- **Every `type: ignore` needs a comment**: `# type: ignore[arg-type]: library types are incorrect`
- **Prefer `object` over `Any`** when the value is truly unknown but shouldn't be used arbitrarily
- **Forbid**: untyped function signatures in production code

## Code Style

### Data Modeling

- **Pydantic models**: at trust boundaries (API input/output, config, external data)
- **dataclasses**: internal domain objects where types are already validated
- **Forbid**: raw dicts for structured data — always define a model

### Immutability

- Use `tuple` over `list` for fixed-length sequences
- Use `frozenset` over `set` when mutation isn't needed
- Prefer `@dataclass(frozen=True)` for value objects
- Pydantic models: use `model_config = ConfigDict(frozen=True)` when appropriate

### String Formatting

- f-strings exclusively — forbid `.format()` and `%` formatting
- For SQL/HTML: use parameterized queries or template engines, never f-strings

### Pattern Matching

- Use `match`/`case` for multi-branch dispatch on structure (3+ branches)
- Do not use as verbose `if/elif` replacement for simple conditions

### None Handling

- Distinguish `None` semantically:
  - Function parameter default: "not provided" → use sentinel or `None`
  - Return value: "intentional absence" → `None`
- Never use mutable default arguments (`def f(items=[])`), use `None` + guard

### Walrus Operator

- Use for loop-and-filter, regex matching, file chunking
- Forbid nested walrus expressions

```python
# Good
if match := pattern.search(text):
    return match.group(1)

while chunk := file.read(8192):
    digest(chunk)
```

## Function Writing

### Arguments: Flat vs Object

- Use flat if single argument or 2 required args with clear order
- Use Pydantic model or dataclass for 3+ arguments
- Keyword-only after positional: `def fetch(url: str, *, timeout: int = 30)`

### Async

- Use `async/await` for I/O-bound operations
- Never mix sync blocking calls inside async functions
- Use `asyncio.TaskGroup` for concurrent tasks (3.11+)

## Error Handling

In addition to general.md error handling rules, apply these Python-specific constraints:

- Never use bare `except:` (catches SystemExit, KeyboardInterrupt)
- `except Exception:` — allow only at boundary layers (middleware, task runners, CLI entry points) with mandatory logging. Forbid in business logic.
- Use `raise ... from err` to preserve exception chains
- Context managers (`with`/`async with`) for resource cleanup

### AI Error Handling Enforcement

AI generates overly broad exception handlers. Apply strict constraints:

- **Forbid**: `except: pass`, `except Exception: pass`
- **Forbid**: `try/except` wrapping entire function bodies
- **Allow**: `except Exception:` at boundary layers with logging + re-raise or graceful shutdown
- **Require**: specific exception types in business logic
- **Require**: logging or re-raising in every `except` block

## Formatting and Linting

- Ruff for both linting and formatting (replaces black, isort, flake8)
- Line length: 88 (Ruff/Black default)

```toml
[tool.ruff]
target-version = "py312"
line-length = 88

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "N",    # pep8-naming
    "UP",   # pyupgrade
    "B",    # flake8-bugbear
    "SIM",  # flake8-simplify
    "TCH",  # flake8-type-checking
    "RUF",  # ruff-specific
]
```

## Testing

- pytest exclusively
- File placement: co-located `__tests__/` directory next to source (follows testing-core.md)
- Run via: `uv run pytest`

## Recommended Libraries

- HTTP: httpx
- Validation: pydantic (v2)
- Web framework: FastAPI
- ORM: SQLAlchemy 2.0, alembic (migrations)
- DB driver: asyncpg (PostgreSQL async)
- Data processing: polars
- Messaging: faststream
- Retry: tenacity
- Scheduling: apscheduler
- Async: asyncio (stdlib) + anyio (structured concurrency)
- CLI: typer
- Settings: pydantic-settings
- Logging: structlog
- Testing: pytest, pytest-asyncio, pytest-cov, pytest-httpx
- Formatting/Linting: ruff
- Type checking: pyright or mypy
