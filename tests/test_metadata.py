"""Test package metadata"""

import pydrobert.param


def test_version():
    assert pydrobert.param.__version__ != "inplace"
