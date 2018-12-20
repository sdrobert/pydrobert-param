import pytest
import pydrobert.param.serialization as serial


@pytest.fixture(params=["ruamel_yaml", "pyyaml"])
def myyaml(request):
    if request.param == 'ruamel_yaml':
        try:
            from ruamel_yaml import YAML
            yaml = YAML()
            module_name = 'ruamel_yaml'
        except ImportError:
            from ruamel.yaml import YAML
            yaml = YAML()
            module_name = 'ruamel.yaml'
    else:
        import yaml
        module_name = 'pyyaml'
    old_props = serial.YAML_MODULE_PRIORITIES
    serial.YAML_MODULE_PRIORITIES = (module_name,)
    yield yaml
    serial.YAML_MODULE_PRIORITIES = old_props
