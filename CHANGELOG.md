# Changelog

## v0.4.0

- Added extras.
- Bug fix for YAML backends when only one backend is installed.
- New serialization protocols based on `param`'s built-in serialization are in
  beta. Added code, tests, and documentation.
- Refactored code to separate serialization from/to file from the dict stuff.
  Extended file serialization to handle non-dict stuff and avoid some bugs.
- `DEFAULT_*` globals are no longer exposed in `pydrobert.serialization`. A
  breaking change, but since functions already have a means of updating the
  default dictionary temporarily, one unlikely to cause many issues.
- Moved to `pydrobert.config` and redefined an element in
  `YAML_MODULE_PRIORITIES`. Technically a breaking change, but one unlikely to
  cause many issues.

## v0.3.1

- Handle ABC issues with MRO instead of redefining base class.
- No more `setup.py`.
- Removed `recipe`.
- Bumped minimum version to 3.7.
- Updated documentation.

## v0.3.0

A considerable amount of refactoring occurred for this build, chiefly to get
rid of Python 2.7 support. While the functionality did not change much for this
version, we have switched from a `pkgutil`-style `pydrobert` namespace to
PEP-420-style namespaces. As a result, *this package is not
backwards-compatible with previous `pydrobert` packages!* Make sure that if any
of the following are installed, they exceed the following version thresholds:

- `pydrobert-kaldi >0.5.3`
- `pydrobert-pytorch >0.2.1`
- `pydrobert-speech >0.1.0`

Miscellaneous other stuff:

- Type hints everywhere
- Shifted python source to `src/`
- Black-formatted remaining source
- Removed `future`, `six`, `configparser` dependencies
- Shifted most of the configuration to `setup.cfg`, leaving only a shell
  in `setup.py` to remain compatible with Conda builds
- Added `pyproject.toml` for [PEP
  517](https://www.python.org/dev/peps/pep-0517/).
- `tox.ini` for TOX testing
- Switched to AppVeyor for CI
- Added changelog :D
