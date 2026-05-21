- Bypassing beartype during tests required monkey patching `__wrapped__` function due to decorator issue.
- Updated  to use timezone-aware datetime per pytest warnings.
- Updated ProcessingStatusManager to use timezone-aware datetime per pytest warnings.
- Verified full test suite including formatting and static typing passes.
## 2026-05-21 - Mocking Missing CI Dependencies
**Learning:** Some test modules (like transcription transcribers) are skipped because dependencies (like `torch` or `whisper`) are missing in CI. Removing `@pytest.mark.skip` will cause test crashes due to `import` statements evaluating before tests run.
**Action:** When unskipping these tests, use `mocker.patch.dict("sys.modules", {"torch": MagicMock(), "whisper": MagicMock()})` *before* the internal local imports of the testing module to safely fake the libraries being installed.
