"""Tests for `apitit` package."""
import base64

import pytest

from apitit import Apitit


def get_locations():
    """Get all locations supported by Apitit."""
    return set((*Apitit.BASE_URLS.keys(), *Apitit.SPECIAL_URLS.keys()))


@pytest.fixture(scope="module", params=get_locations())
def apt(request):
    apt = Apitit(request.param)
    return apt


def test_credentials(apt):
    """Test for meaningful credentials by calculating auth header."""
    header_calc = f"{apt.api_credentials.user}:{apt.api_credentials.password}"
    header_calc = base64.b64encode(bytes(header_calc, 'utf-8'))
    header_calc = header_calc.decode('utf-8')
    header_calc = f"Basic {header_calc}"
    assert header_calc == apt.api_credentials.header
