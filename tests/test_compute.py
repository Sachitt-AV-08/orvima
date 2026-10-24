"""Pins orvima.compute math/unit/conversion tools."""

from __future__ import annotations

from orvima import compute


def test_math_solve_polynomial():
    res = compute.math_solve("x**2 - 4")
    assert res["ok"] is True
    assert set(res["solutions"]) == {"-2", "2"}


def test_math_solve_equation():
    res = compute.math_solve("2*x + 3 = 7", variable="x")
    assert res["ok"] is True
    assert res["solutions"] == ["2"]


def test_math_solve_error():
    res = compute.math_solve("not an expr")
    assert res["ok"] is False
    assert "error" in res


def test_math_simplify():
    res = compute.math_simplify("x + x")
    assert res["ok"] is True
    assert res["simplified"] == "2*x"


def test_math_derivative():
    res = compute.math_derivative("x**3", order=2)
    assert res["ok"] is True
    assert res["derivative"] == "6*x"


def test_math_integral():
    res = compute.math_integral("2*x")
    assert res["ok"] is True
    assert res["integral"] == "x**2"


def test_math_plot_data():
    res = compute.math_plot_data("x", points=5)
    assert res["ok"] is True
    assert len(res["x"]) == 5
    assert len(res["y"]) == 5


def test_math_plot_data_error():
    res = compute.math_plot_data("not_a_valid_expr !!!")
    assert res["ok"] is False


def test_unit_convert_length():
    res = compute.unit_convert(2, "m", "cm")
    assert res["ok"] is True
    assert res["result"] == 200.0


def test_unit_convert_temperature():
    res = compute.unit_convert(0, "c", "f")
    assert res["ok"] is True
    assert res["result"] == 32.0
    res = compute.unit_convert(100, "c", "k")
    assert res["result"] == 373.15


def test_unit_convert_identity():
    res = compute.unit_convert(5, "m", "m")
    assert res["ok"] is True
    assert res["result"] == 5


def test_unit_convert_unknown():
    res = compute.unit_convert(1, "foo", "bar")
    assert res["ok"] is False
    assert "unknown conversion" in res["error"]
    assert "supported_units" in res


def test_science_constants_all_and_one():
    res = compute.science_constants()
    assert res["ok"] is True
    assert "constants" in res

    res = compute.science_constants("pi")
    assert res["ok"] is True
    assert res["name"] == "pi"
    assert "value" in res

    res = compute.science_constants("nope_xyz")
    assert res["ok"] is False
    assert "unknown constant" in res["error"]


def test_compute_tools_tuple():
    assert len(compute.COMPUTE_TOOLS) == 7
