# Contributing to FocusWith

Thank you for helping improve FocusWith. Keep changes small, explain the user-facing behavior, and use synthetic data in tests and screenshots.

## Development setup

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -q
./macos/FocusFloat/build.sh
```

Before opening a pull request:

- Run the tests, Python compilation, shell syntax checks, and the relevant manual flow.
- Add or update tests for behavior changes, especially authorization, timer state, and data mutations.
- Do not commit `.env`, databases, logs, generated apps, tokens, private URLs, screenshots containing personal plans, or real provider responses.
- Preserve private-by-default local behavior. Any new public endpoint needs authentication, explicit documentation, and a threat-model review.
- Update `VERSION` and `CHANGELOG.md` only when preparing a release, not for every pull request.

By contributing, you agree that your contribution is licensed under the repository's MIT License.
