"""Tests for orvima.bench_site module."""

from orvima.bench_site import BenchSite, BenchError, PAGES


def test_bench_site_class():
    assert BenchSite is not None


def test_bench_error_is_exception():
    assert issubclass(BenchError, Exception)


def test_pages_not_empty():
    assert isinstance(PAGES, (list, dict, tuple))
    assert len(PAGES) > 0


def test_bench_site_instantiation():
    bs = BenchSite()
    assert bs is not None