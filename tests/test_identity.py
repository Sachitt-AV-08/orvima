"""Tests for orvima.identity module."""

from orvima.identity import ElementIdentity, RefRegistry, RefResolution, _norm


def test_norm():
    result = _norm("Hello World")
    assert isinstance(result, str)


def test_element_identity_dataclass():
    ei = ElementIdentity(ref="r1", role="button", label="Submit", text="Submit", tag="button", ordinal=1, raw_label="Submit", raw_text="Submit")
    assert ei.tag == "button"
    assert ei.text == "submit"


def test_ref_registry_class():
    rr = RefRegistry()
    assert rr is not None


def test_ref_resolution_class():
    rr = RefResolution(ref="r1", safe=True, reason="", replacement=None)
    assert rr.safe is True