import pytest


def add(a, b):
    return a + b


def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b


class TestMath:
    def test_add(self):
        assert add(2, 3) == 5

    def test_divide(self):
        assert divide(10, 2) == 5.0

    def test_divide_by_zero(self):
        with pytest.raises(ValueError):
            divide(10, 0)
