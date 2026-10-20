"""compute_* tools: math, science, and unit conversion.

Uses sympy for symbolic math, scipy for numerical computation,
and a built-in unit converter. All local, no API keys.
"""

from __future__ import annotations


def math_solve(expression: str, variable: str = "x") -> dict:
    """Solve a symbolic equation or expression.

    Examples: "x**2 - 4", "sin(x) - 0.5", "2*x + 3 = 7"
    """
    try:
        import sympy as sp
        var = sp.Symbol(variable)
        expr = expression.strip()

        # Handle equations with =
        if "=" in expr:
            lhs, rhs = expr.split("=", 1)
            eq = sp.Eq(sp.sympify(lhs.strip()), sp.sympify(rhs.strip()))
            solutions = sp.solve(eq, var)
        else:
            solutions = sp.solve(sp.sympify(expr), var)

        return {
            "ok": True,
            "expression": expression,
            "variable": variable,
            "solutions": [str(s) for s in solutions],
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def math_simplify(expression: str) -> dict:
    """Simplify a mathematical expression."""
    try:
        import sympy as sp
        simplified = sp.simplify(sp.sympify(expression))
        return {"ok": True, "original": expression, "simplified": str(simplified)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def math_derivative(expression: str, variable: str = "x", order: int = 1) -> dict:
    """Compute the derivative of an expression."""
    try:
        import sympy as sp
        var = sp.Symbol(variable)
        deriv = sp.diff(sp.sympify(expression), var, order)
        return {"ok": True, "expression": expression, "derivative": str(deriv)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def math_integral(expression: str, variable: str = "x") -> dict:
    """Compute the indefinite integral of an expression."""
    try:
        import sympy as sp
        var = sp.Symbol(variable)
        integral = sp.integrate(sp.sympify(expression), var)
        return {"ok": True, "expression": expression, "integral": str(integral)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def math_plot_data(expression: str, x_min: float = -10, x_max: float = 10, points: int = 100) -> dict:
    """Generate (x, y) data points for plotting an expression."""
    try:
        import numpy as np
        import sympy as sp
        var = sp.Symbol("x")
        f = sp.lambdify(var, sp.sympify(expression), "numpy")
        xs = np.linspace(x_min, x_max, points)
        ys = f(xs)
        if not hasattr(ys, "__len__"):
            ys = [float(ys)] * points
        return {
            "ok": True,
            "expression": expression,
            "x": [round(float(v), 4) for v in xs],
            "y": [round(float(v), 4) for v in ys],
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def unit_convert(value: float, from_unit: str, to_unit: str) -> dict:
    """Convert between common units (length, mass, temperature, etc.)."""
    conversions = {
        # Length (to meters)
        ("m", "cm"): 100, ("cm", "m"): 0.01, ("m", "km"): 0.001, ("km", "m"): 1000,
        ("m", "ft"): 3.28084, ("ft", "m"): 0.3048, ("m", "in"): 39.3701, ("in", "m"): 0.0254,
        ("km", "mi"): 0.621371, ("mi", "km"): 1.60934, ("ft", "in"): 12, ("in", "ft"): 1/12,
        # Mass (to kg)
        ("kg", "g"): 1000, ("g", "kg"): 0.001, ("kg", "lb"): 2.20462, ("lb", "kg"): 0.453592,
        ("g", "mg"): 1000, ("mg", "g"): 0.001, ("lb", "oz"): 16, ("oz", "lb"): 1/16,
        # Volume (to liters)
        ("l", "ml"): 1000, ("ml", "l"): 0.001, ("l", "gal"): 0.264172, ("gal", "l"): 3.78541,
        # Time (to seconds)
        ("s", "min"): 1/60, ("min", "s"): 60, ("min", "hr"): 1/60, ("hr", "min"): 60,
        ("hr", "s"): 3600, ("s", "hr"): 1/3600, ("day", "hr"): 24, ("hr", "day"): 1/24,
    }

    from_u = from_unit.lower().strip()
    to_u = to_unit.lower().strip()

    # Temperature (special)
    if from_u in ("c", "celsius") and to_u in ("f", "fahrenheit"):
        return {"ok": True, "value": value, "from": from_unit, "to": to_unit,
                "result": round(value * 9/5 + 32, 6)}
    if from_u in ("f", "fahrenheit") and to_u in ("c", "celsius"):
        return {"ok": True, "value": value, "from": from_unit, "to": to_unit,
                "result": round((value - 32) * 5/9, 6)}
    if from_u in ("c", "celsius") and to_u in ("k", "kelvin"):
        return {"ok": True, "value": value, "from": from_unit, "to": to_unit,
                "result": round(value + 273.15, 6)}
    if from_u in ("k", "kelvin") and to_u in ("c", "celsius"):
        return {"ok": True, "value": value, "from": from_unit, "to": to_unit,
                "result": round(value - 273.15, 6)}

    key = (from_u, to_u)
    if key in conversions:
        return {"ok": True, "value": value, "from": from_unit, "to": to_unit,
                "result": round(value * conversions[key], 6)}

    return {"ok": False, "error": f"unknown conversion {from_unit} -> {to_unit}"}


def science_constants(name: str = "") -> dict:
    """Look up physical/scientific constants."""
    constants = {
        "speed_of_light": {"value": 299792458, "unit": "m/s", "symbol": "c"},
        "gravitational_constant": {"value": 6.67430e-11, "unit": "m^3 kg^-1 s^-2", "symbol": "G"},
        "planck_constant": {"value": 6.62607015e-34, "unit": "J·s", "symbol": "h"},
        "avogadro_number": {"value": 6.02214076e23, "unit": "mol^-1", "symbol": "N_A"},
        "boltzmann_constant": {"value": 1.380649e-23, "unit": "J/K", "symbol": "k_B"},
        "electron_mass": {"value": 9.10938356e-31, "unit": "kg", "symbol": "m_e"},
        "proton_mass": {"value": 1.67262192e-27, "unit": "kg", "symbol": "m_p"},
        "elementary_charge": {"value": 1.602176634e-19, "unit": "C", "symbol": "e"},
        "gas_constant": {"value": 8.314462618, "unit": "J/(mol·K)", "symbol": "R"},
        "pi": {"value": 3.141592653589793, "unit": "dimensionless", "symbol": "π"},
        "golden_ratio": {"value": 1.618033988749895, "unit": "dimensionless", "symbol": "φ"},
        "earth_gravity": {"value": 9.80665, "unit": "m/s^2", "symbol": "g"},
        "atmospheric_pressure": {"value": 101325, "unit": "Pa", "symbol": "atm"},
    }

    if not name:
        return {"ok": True, "constants": constants}

    name_lower = name.lower().replace(" ", "_")
    for key, val in constants.items():
        if name_lower in key or key in name_lower:
            return {"ok": True, "name": key, **val}

    return {"ok": False, "error": f"unknown constant {name!r}", "available": list(constants.keys())}


COMPUTE_TOOLS = (
    math_solve,
    math_simplify,
    math_derivative,
    math_integral,
    math_plot_data,
    unit_convert,
    science_constants,
)
