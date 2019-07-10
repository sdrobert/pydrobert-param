from shutil import rmtree
from tempfile import mkdtemp

import pytest
import pydrobert.param.serialization as serial


@pytest.fixture(params=["ruamel_yaml", "pyyaml"])
def yaml_loader(request):
    if request.param == 'ruamel_yaml':
        try:
            from ruamel_yaml import YAML
            yaml_loader = YAML().load
            module_name = 'ruamel_yaml'
        except ImportError:
            from ruamel.yaml import YAML
            yaml_loader = YAML().load
            module_name = 'ruamel.yaml'
    else:
        import yaml

        def yaml_loader(x):
            return yaml.load(x, Loader=yaml.FullLoader)
        module_name = 'pyyaml'
    old_props = serial.YAML_MODULE_PRIORITIES
    serial.YAML_MODULE_PRIORITIES = (module_name,)
    yield yaml_loader
    serial.YAML_MODULE_PRIORITIES = old_props


@pytest.fixture
def temp_dir():
    dir_name = mkdtemp()
    yield dir_name
    rmtree(dir_name, ignore_errors=True)
