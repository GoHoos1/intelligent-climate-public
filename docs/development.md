# Development

## Supported Environment Assumptions

The current authoritative project documents are:

- `README.md`
- `docs/product-specification.md`
- `docs/phase-1-technical-design.md`

Official Home Assistant developer documentation checked during this foundation
task states that current Home Assistant development requires Python 3.14.2 or
higher. This repository therefore declares `requires-python = ">=3.14.2"`.

The local machine used for the foundation task had only Python 3.12.10
available, so Home Assistant-backed validation could not be completed locally.
Use Python 3.14.2 or newer before treating local validation as authoritative.

The exact minimum supported Home Assistant Core release remains unresolved for
this repository. The Phase 1 design mentions Home Assistant 2026.7, but this
foundation task did not verify that as the correct minimum. Do not add a
minimum Home Assistant version claim until it is verified from official sources.

## Windows, WSL2, and Dev Containers

Native Windows PowerShell is acceptable for lightweight foundation checks when
the installed interpreter is compatible with the selected tools.

For future Home Assistant integration work, WSL2 or a dev container is
recommended. Home Assistant dependencies may need Linux system libraries, and
native Windows can be slower or blocked by unavailable wheels for Python 3.14.

Do not install repository dependencies into the global or per-user Python
environment. Use a virtual environment, WSL2, or a dev container.

## Create a Virtual Environment

PowerShell:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

If `py -3.14` is unavailable, install Python 3.14.2 or newer first.

## Install Dependencies

```powershell
python -m pip install -r requirements_test.txt
```

`requirements_test.txt` delegates to the `dev` optional dependency group in
`pyproject.toml`, which is the source of truth for test, lint, format, type, and
Home Assistant custom-component test tooling.

## Test Commands

Run lightweight tests with the current interpreter when compatible:

```powershell
python -m pytest
```

Run tests with coverage:

```powershell
python -m pytest --cov=custom_components.intelligent_climate --cov-report=term-missing
```

The genuine Home Assistant lifecycle tests use the real `hass` fixture and
`MockConfigEntry` from `pytest-homeassistant-custom-component`. They are skipped
locally when those dependencies are unavailable. CI installs the complete
development dependencies under Python 3.14 and must run those tests.

Do not describe Home Assistant setup/unload compatibility as locally validated
unless those genuine tests actually ran.

## Lint Commands

```powershell
python -m ruff check .
```

## Formatting Commands

Check formatting:

```powershell
python -m ruff format --check .
```

Apply formatting:

```powershell
python -m ruff format .
```

## Type-Check Commands

```powershell
python -m mypy custom_components/intelligent_climate tests
```

## Run All Local Checks

```powershell
python -m pytest --cov=custom_components.intelligent_climate --cov-report=term-missing
python -m ruff check .
python -m ruff format --check .
python -m mypy custom_components/intelligent_climate tests
git diff --check
```

## Hassfest and HACS Validation

GitHub Actions run:

- `home-assistant/actions/hassfest@master`
- `hacs/action@main` with `category: integration`

Run equivalent local validation only when the required tools are available for
the active Python version. If they cannot be installed or executed locally,
record the exact blocker in the implementation notes for the change.

GitHub Actions are the authoritative validation path for Home Assistant-backed
tests, HACS validation, and hassfest until a supported local Python 3.14
environment is available.

## Native Windows Limitations

- Python 3.14 may not be installed by default.
- Some Home Assistant dependencies may lack native Windows wheels.
- WSL2 or a dev container is recommended once tests require real Home Assistant
  fixtures, hassfest internals, or compiled dependencies.
- Do not work around dependency problems by lowering the documented Home
  Assistant Python requirement.
