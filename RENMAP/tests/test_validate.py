import pytest

from conftest import write_data
from validate import validate


def errors_for(tmp_path, sample, **changes):
    institutions, nodes, links = sample
    institutions[1].update(changes)
    write_data(tmp_path, institutions, nodes, links)
    return validate(tmp_path)[0].errors


def test_unverified_network_is_valid(tmp_path, sample):
    assert errors_for(tmp_path, sample) == []


def test_verified_network_is_valid(tmp_path, sample):
    assert errors_for(tmp_path, sample, verified_by="hugoromao", verified_on="2026-11-03") == []


@pytest.mark.parametrize("changes, message", [
    ({"verified_by": "hugoromao"}, '"verified_by" needs "verified_on"'),
    ({"verified_on": "2026-11-03"}, '"verified_on" needs "verified_by"'),
    ({"verified_by": " ", "verified_on": "2026-11-03"}, '"verified_on" needs "verified_by"'),
    ({"verified_by": "hugoromao", "verified_on": "03/11/2026"}, "must be a date as YYYY-MM-DD"),
    ({"verified_by": "hugoromao", "verified_on": "20261103"}, "must be a date as YYYY-MM-DD"),
    ({"verified_by": "hugoromao", "verified_on": "2999-01-01"}, "is in the future"),
    ({"verified_by": ["hugoromao"], "verified_on": "2026-11-03"}, 'field "verified_by" must be a string'),
    ({"trust": "high"}, 'unknown field "trust"'),
])
def test_invalid_verification(tmp_path, sample, changes, message):
    errors = errors_for(tmp_path, sample, **changes)
    assert any(message in error for error in errors), errors
