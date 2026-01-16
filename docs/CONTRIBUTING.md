# Contributing

## Development Setup

```bash
git clone https://github.com/terje/python-reverb.git
cd python-reverb
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

## Code Style

- Format with ruff (configured in pyproject.toml)
- Type hints required for all public APIs
- Docstrings for public classes and methods

Run checks:

```bash
ruff check src/ tests/
ruff format src/ tests/
mypy src/
```

## Testing

Run the test suite:

```bash
pytest
pytest -v                    # verbose
pytest --cov=src/reverb      # with coverage
pytest tests/test_auth.py    # single file
```

### Writing Tests

- Place tests in `tests/` directory
- Name test files `test_*.py`
- Use pytest fixtures from `conftest.py`
- Mock WebSocket connections for unit tests

Example:

```python
import pytest
from reverb.auth import Authenticator

def test_private_channel_auth(config, socket_id):
    auth = Authenticator(config.app_key, config.app_secret.get_secret_value())
    result = auth.authenticate(socket_id, "private-test")

    assert "auth" in result
    assert result["auth"].startswith(config.app_key)
```

## Pull Requests

1. Fork the repository
2. Create a feature branch from `main`
3. Make changes with tests
4. Ensure all checks pass
5. Submit PR with clear description

### Commit Messages

Use conventional commits:

```
feat: add presence channel member count property
fix: handle reconnection when socket_id changes
docs: add webhook relay example
test: add coverage for edge cases in message parsing
```

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for internal design documentation.

## Release Process

1. Update version in `pyproject.toml` and `src/reverb/__init__.py`
2. Update CHANGELOG.md
3. Create git tag: `git tag v0.2.0`
4. Push tag: `git push origin v0.2.0`
5. GitHub Actions builds and publishes to PyPI
