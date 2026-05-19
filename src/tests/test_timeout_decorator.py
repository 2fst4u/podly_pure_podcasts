import time

import pytest

from src.app.timeout_decorator import TimeoutException, timeout_decorator


def test_timeout_decorator_success() -> None:
    @timeout_decorator(timeout=1)
    def my_func() -> str:
        return "success"

    assert my_func() == "success"


def test_timeout_decorator_exceeds() -> None:
    @timeout_decorator(timeout=1)
    def my_func() -> None:
        time.sleep(2)

    with pytest.raises(TimeoutException, match="exceeded timeout"):
        my_func()


def test_timeout_decorator_arguments() -> None:
    @timeout_decorator(timeout=1)
    def my_func(a: int, b: int = 0) -> int:
        return a + b

    assert my_func(5, b=10) == 15


def test_timeout_decorator_exception(capsys: pytest.CaptureFixture[str]) -> None:
    @timeout_decorator(timeout=1)
    def my_func() -> str:
        raise ValueError("test exception")
        return "never"

    result = my_func()
    assert result is None

    captured = capsys.readouterr()
    assert "Exception in thread: test exception" in captured.out
