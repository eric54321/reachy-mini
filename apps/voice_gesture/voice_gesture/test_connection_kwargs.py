"""Tests for the physical/sim connection toggle. Run with:
pytest test_connection_kwargs.py
"""

import os

import pytest

from voice_gesture.main import _connection_kwargs

ENV_KEYS = [
    "REACHY_MINI_MODE",
    "REACHY_MINI_HOST",
    "REACHY_MINI_SIM_HOST",
    "REACHY_MINI_SIM_PORT",
]


@pytest.fixture(autouse=True)
def clean_env():
    """Each test starts with none of these vars set, and cleans up after."""
    saved = {k: os.environ.pop(k, None) for k in ENV_KEYS}
    yield
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v
        else:
            os.environ.pop(k, None)


def test_defaults_to_physical_with_the_known_robot_ip():
    assert _connection_kwargs() == {"host": "192.168.50.216"}


def test_physical_mode_honors_custom_host():
    os.environ["REACHY_MINI_MODE"] = "physical"
    os.environ["REACHY_MINI_HOST"] = "10.0.0.5"
    assert _connection_kwargs() == {"host": "10.0.0.5"}


def test_sim_mode_uses_localhost_and_default_port():
    os.environ["REACHY_MINI_MODE"] = "sim"
    assert _connection_kwargs() == {"host": "localhost", "port": 8090}


def test_sim_mode_honors_custom_host_and_port():
    os.environ["REACHY_MINI_MODE"] = "sim"
    os.environ["REACHY_MINI_SIM_HOST"] = "127.0.0.1"
    os.environ["REACHY_MINI_SIM_PORT"] = "9999"
    assert _connection_kwargs() == {"host": "127.0.0.1", "port": 9999}
