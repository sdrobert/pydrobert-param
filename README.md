# pydrobert-param

[![Documentation Status](https://readthedocs.org/projects/pydrobert-param/badge/?version=latest)](https://pydrobert-param.readthedocs.io/en/latest/?badge=latest)
[![Build status](https://ci.appveyor.com/api/projects/status/67r8qy78u6bkf2qn/branch/master?svg=true)](https://ci.appveyor.com/project/sdrobert/pydrobert-param/branch/master)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

Utilities for the python package [param](http://param.pyviz.org/).

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

While the primary purpose of _pydrobert-param_ is for parameter
(de)serialization, there is also code in `pydrobert.param.optuna` for
hyperparameter optimization via [Optuna](https://optuna.org/). Check the
documentation for more complicated examples of serialization, as well as for
hyperparameter optimization.

**This is student-driven code, so don't expect a stable API. I'll try to use
semantic versioning, but the best way to keep functionality stable is by
pinning the version in the requirements or by forking.**

## Documentation

- [Latest](https://pydrobert-param.readthedocs.io/en/latest/)
- [v0.3.1](https://pydrobert-param.readthedocs.io/en/v0.3.1/)

## Installation

_pydrobert-param_ is available via both PyPI and Conda.

``` sh
conda install -c sdrobert pydrobert-param
pip install pydrobert-param
pip install git+https://github.com/sdrobert/pydrobert-param # bleeding edge
```

There are also optional dependencies on PyPI:

``` sh
pip install 'pydrobert-param[yaml]'    # installs ruamel.yaml YAML backend
pip install 'pydrobert-param[optuna]'  # installs optuna
pip install 'pydrobert-param[types]'   # installs numpy and pandas
                                       # (to handle all types)
pip install 'pydrobert-param[all]'     # all of the above
```

## Licensing and How to Cite

Please see the [pydrobert page](https://github.com/sdrobert/pydrobert) for more
details.

The implementation of `pydrobert.param.abc._check_methods` was modified from
the CPython codebase, Copyright 2007 Google with additional notices at
<https://docs.python.org/3/copyright.html?highlight=copyright>.
