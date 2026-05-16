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
    """Test for meaningful credentials by calculating auth header.

    Internally, Apitit sends a request to the homepage URL. Thus the test also
    indicates if the homepage URL is reachable.
    """
    header_calc = f"{apt.api_credentials.user}:{apt.api_credentials.password}"
    header_calc = base64.b64encode(bytes(header_calc, 'utf-8'))
    header_calc = header_calc.decode('utf-8')
    header_calc = f"Basic {header_calc}"
    assert header_calc == apt.api_credentials.header


def test_get_texts(apt):
    """Test return value of get_texts.

    get_texts should return a list of dictionaries with each dict containing
    the keys "id" and "text".
    Internally, Apitit sends a request to the kasvc URL. Thus the test also
    indicates if the kasvc URL is reachable.
    """
    res = apt.get_texts()
    assert isinstance(res, list)
    assert isinstance(res[0], dict)
    assert "id" in res[0]
    assert "text" in res[0]
