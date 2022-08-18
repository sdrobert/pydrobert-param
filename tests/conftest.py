from shutil import rmtree
from tempfile import mkdtemp
from io import StringIO

import pytest
import param
import pydrobert.param.serialization as serial


param.parameterized.warnings_as_exceptions = True


@pytest.fixture(params=["ruamel_yaml", "pyyaml"])
def yaml_loader(request):
    if request.param == "ruamel_yaml":
        YAML = None
        try:
            from ruamel_yaml import YAML  # type: ignore
        except ImportError:
            pass
        if YAML is None:
            try:
                from ruamel.yaml import YAML  # type: ignore
            except ImportError:
                pytest.skip("No yaml parser found")
        yaml_loader = YAML().load
        module_names = ("ruamel_yaml", "ruamel.yaml")
    else:
        yaml = pytest.importorskip("yaml")

        def yaml_loader(x):
            return yaml.load(x, Loader=yaml.FullLoader)

        module_names = ("pyyaml",)
    old_props = serial.YAML_MODULE_PRIORITIES
    serial.YAML_MODULE_PRIORITIES = module_names
    yield yaml_loader
    serial.YAML_MODULE_PRIORITIES = old_props


@pytest.fixture(params=[True, False])
def with_yaml(request):
    if request.param:
        try:
            with StringIO() as fp:
                serial._serialize_to_yaml(fp, {"foo": 1})
        except ImportError:
            pytest.skip("No yaml serializer")
        yield True
    else:
        old_props = serial.YAML_MODULE_PRIORITIES
        serial.YAML_MODULE_PRIORITIES = tuple()
        yield False
        serial.YAML_MODULE_PRIORITIES = old_props


@pytest.fixture
def temp_dir():
    dir_name = mkdtemp()
    yield dir_name
    rmtree(dir_name, ignore_errors=True)
