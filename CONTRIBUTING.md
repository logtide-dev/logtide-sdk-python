# Contributing to LogTide Python SDK

Thank you for your interest in contributing!

## Development Setup

1. Clone the repository:
```bash
git clone https://github.com/logtide-dev/logtide-python.git
cd logtide-sdk-python
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dev dependencies:
```bash
pip install -e ".[dev]"
```

## Code Style

- Follow [PEP 8](https://peps.python.org/pep-0008/) style guide
- Use type hints for all public APIs
- Format code with [Black](https://black.readthedocs.io/)
- Lint with [Ruff](https://docs.astral.sh/ruff/)
- Use meaningful variable and function names
- Add docstrings for public functions and classes

## Testing

```bash
# Run tests
pytest tests/

# Run with coverage
pytest --cov=logtide_sdk tests/

# Type checking
mypy logtide_sdk/

# Code formatting
black logtide_sdk/ tests/ examples/

# Linting
ruff check logtide_sdk/
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Ensure tests pass (`pytest tests/`)
5. Format code (`black .`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## Reporting Issues

- Use the GitHub issue tracker
- Provide clear description and reproduction steps
- Include Python version and OS information
- Include relevant logs and error messages

## Questions?

Feel free to open an issue for any questions or discussions!
