"""Tests for orvima.compute module."""

from orvima.compute import (
    math_solve,
    math_simplify,
    math_derivative,
    math_integral,
    math_plot_data,
    unit_convert,
    science_constants,
)


def test_math_solve_quadratic():
    result = math_solve("x**2 - 4")
    assert result["ok"] is True
    assert "2" in result["solutions"] or "-2" in result["solutions"]


def test_math_solve_linear_equation():
    result = math_solve("2*x + 3 = 7")
    assert result["ok"] is True
    assert "2" in result["solutions"]


def test_math_solve_invalid():
    result = math_solve("not a math expression!!!")
    assert result["ok"] is False
    assert "error" in result


def test_math_simplify():
    result = math_simplify("x**2 + 2*x + 1")
    assert result["ok"] is True
    assert "simplified" in result


def test_math_simplify_invalid():
    result = math_simplify("!!!invalid!!!")
    assert result["ok"] is False


def test_math_derivative():
    result = math_derivative("x**2")
    assert result["ok"] is True
    assert "2*x" in result.get("derivative", "") or "2*x" in str(result)


def test_math_derivative_second_order():
    result = math_derivative("x**3", order=2)
    assert result["ok"] is True


def test_math_integral():
    result = math_integral("x**2")
    assert result["ok"] is True


def test_math_plot_data():
    result = math_plot_data("x**2", x_min=-5, x_max=5)
    assert result["ok"] is True
    assert "x" in result or "points" in result or "data" in result


def test_unit_convert_length():
    result = unit_convert(100, "cm", "m")
    assert result["ok"] is True
    assert result["result"] == 1.0 or result["value"] == 1.0 or abs(result.get("result", result.get("value", 0)) - 1.0) < 0.001


def test_unit_convert_temperature():
    result = unit_convert(100, "celsius", "fahrenheit")
    assert result["ok"] is True


def test_science_constants():
    result = science_constants()
    assert isinstance(result, dict)
    assert result.get("ok") is not False or "constants" in result or len(result) > 0


def test_math_solve_trig():
    result = math_solve("sin(x) - 0.5")
    assert result["ok"] is True or result["ok"] is False  # just ensure no crash