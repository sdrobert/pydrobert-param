[![Build Status](https://travis-ci.com/sdrobert/pydrobert-param.svg?branch=master)](https://travis-ci.com/sdrobert/pydrobert-param)
[![Documentation Status](https://readthedocs.org/projects/pydrobert-param/badge/?version=latest)](https://pydrobert-param.readthedocs.io/en/latest/?badge=latest)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

# pydrobert-param

Utilities for the python package [param](http://param.pyviz.org/)

**This is student-driven code, so don't expect a stable API. I'll try to use
semantic versioning, but the best way to keep functionality stable is by
pinning the version in the requirements or by forking.**

While _param_ is a great tool for keeping track of parameters, currently
serialization is restricted to pickling and unpickling objects.
_pydrobert-param_ takes the stance that parameter (de)serialization has an
intuitive and obvious representation in most cases. The developer can modify
how _pydrobert-param_ (de)serializes `param.Parameterized` instances according
to her needs.

A teaser:
``` python
import param
import pydrobert.param.serialization as serial

class Foo(param.Parameterized):
    my_int = param.Integer(10)

first, second = Foo(), Foo()
first.my_int = 30
serial.serialize_to_json('foo.json', first)
serial.deserialize_from_json('foo.json', second)
assert first.my_int == second.my_int
```

More complicated examples can be found in the documentation.

## Documentation

- [Latest](https://pydrobert-param.readthedocs.io/en/latest/)
- [Stable](https://pydrobert-param.readthedocs.io/en/stable/)

# Installation

_pydrobert-param_ is available via both PyPI and Conda.

``` sh
conda install -c sdrobert pydrobert-param
pip install pydrobert-param
pip install https://github.com/sdrobert/pydrobert-param # bleeding edge
```
