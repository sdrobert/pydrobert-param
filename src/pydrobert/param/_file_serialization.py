# Copyright 2022 Sean Robertson
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json

from typing import Any, TextIO, Optional, Union

from collections import OrderedDict
from io import StringIO

from . import config


def _serialize_from_obj_to_ruamel_yaml_dict(ruamel_yaml, dict_, help_dict):
    cdict = ruamel_yaml.comments.CommentedMap()
    c_stack = [cdict]
    d_stack = [dict_]
    h_stack = [help_dict]
    while len(c_stack):
        c = c_stack.pop()
        d = d_stack.pop()
        h = h_stack.pop()
        for key, dval in list(d.items()):
            hval = h.get(key, None)
            if hval is None or isinstance(hval, str):
                c.insert(len(c), key, dval, comment=hval)
            else:
                assert len(d)
                c2 = type(cdict)()
                c.insert(len(c), key, c2)
                c_stack.append(c2)
                d_stack.append(dval)
                h_stack.append(hval)
    return cdict


def _serialize_from_obj_to_ruamel_yaml(ruamel_yaml, fp, obj, help_dict):
    # yaml has an !!omap tag for ordered dictionaries. We don't *need* an
    # ordering when deserializing, but we want an order when serializing. This
    # is a hack to ensure an OrderedDict is serialized like any other dict
    yaml = ruamel_yaml.YAML()

    class MyRepresenter(yaml.Representer):
        pass

    yaml.Representer = MyRepresenter  # don't pollute the base class
    yaml.representer.add_representer(OrderedDict, MyRepresenter.represent_dict)
    if isinstance(obj, dict) and isinstance(help_dict, dict):
        obj = _serialize_from_obj_to_ruamel_yaml_dict(ruamel_yaml, obj, help_dict)
    yaml.dump(obj, stream=fp)


def _serialize_from_obj_to_pyyaml(yaml, fp, obj, help_dict):
    if help_dict:
        help_string_io = StringIO()
        yaml.dump(help_dict, stream=help_string_io, default_flow_style=False)
        help_string = help_string_io.getvalue().replace("\n", "\n# ")
        help_string = "# == Help ==\n# " + help_string + "\n"
        fp.write(help_string)
    # https://stackoverflow.com/questions/5121931/in-python-how-can-you-load-yaml-mappings-as-ordereddicts
    # we also always serialize "None" in order to be consistent with
    # ruamel_yaml using the method from
    # https://stackoverflow.com/questions/37200150/can-i-dump-blank-instead-of-null-in-yaml-pyyaml

    class OrderedDumper(yaml.SafeDumper):
        pass

    def dict_representer(dumper, data):
        return dumper.represent_mapping(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, list(data.items())
        )

    def none_representer(dumper, data):
        return dumper.represent_scalar("tag:yaml.org,2002:null", "")

    OrderedDumper.add_representer(OrderedDict, dict_representer)
    OrderedDumper.add_representer(type(None), none_representer)
    yaml.dump(obj, Dumper=OrderedDumper, stream=fp, default_flow_style=False)


def serialize_from_obj_to_json(
    file_: Union[str, TextIO], obj: dict, indent: Optional[int] = 2
) -> None:
    """Serialize an object into a json file
    
    `JSON syntax <https://en.wikipedia.org/wiki/JSON>`__. Given a dictionary of
    parameter values, fills an JSON file with the contents of this dictionary.

    Parameters
    ----------
    file_
        The JSON file to serialize to. Can be a pointer or a path.
    dict_
        The sort of dictionary returned by :func:`serialized_to_dict`.
    indent
        The indentation level of nested keys. If :obj:`None`, the output will
        be compact.
    
    See Also
    --------
    serialize_to_json
        Composes :func:`serialize_to_dict` with this function.
    """
    if isinstance(file_, str):
        with open(file_, "w") as file_:
            json.dump(obj, file_, indent=indent)
    else:
        json.dump(obj, file_, indent=indent)


def serialize_from_obj_to_yaml(
    file_: Union[str, TextIO], obj: Any, help: Optional[dict] = None
):
    """Serialize an object into a YAML file
    
    `YAML syntax <https://en.wikipedia.org/wiki/YAML>`__.

    Parameters
    ----------
    file_
        The YAML file to serialize to. Can be a pointer or a path.
    obj
        The thing to serialize.
    help
        An optional dictionary of help strings. If both 

    Notes
    -----
    This function tries to use the YAML (de)serialization module to load the YAML file
    in the order listed in :obj:`config.YAML_MODULE_PRIORITIES`, falling back on the
    next if there's an :class:`ImportError`
    """
    if help is None:
        help = dict()
    if isinstance(file_, str):
        with open(file_, "w") as file_:
            return serialize_from_obj_to_yaml(file_, obj, help)
    for name in config.YAML_MODULE_PRIORITIES:
        if name == "ruamel.yaml":
            try:
                import ruamel.yaml  # type: ignore

                _serialize_from_obj_to_ruamel_yaml(ruamel.yaml, file_, obj, help)
                return
            except ImportError:
                pass
        elif name == "ruamel_yaml":
            try:
                import ruamel_yaml  # type: ignore

                _serialize_from_obj_to_ruamel_yaml(ruamel_yaml, file_, obj, help)
                return
            except ImportError:
                pass
        elif name == "pyyaml":
            try:
                import yaml  # type: ignore

                _serialize_from_obj_to_pyyaml(yaml, file_, obj, help)
                return
            except ImportError:
                pass
        else:
            raise ValueError(f"Invalid value in config.YAML_MODULE_PRIORITIES: {name}")
    raise ImportError(
        f"Could not import any of {config.YAML_MODULE_PRIORITIES} for YAML "
        "serialization"
    )


def deserialize_from_yaml_to_obj(file_: Union[str, TextIO]) -> Any:
    """Deserialize a YAML file into an object
    
    `YAML syntax <https://en.wikipedia.org/wiki/YAML>`__.

    Parameters
    ----------
    file_
        A path or pointer to the YAML file.
    
    Notes
    -----
    This function tries to use the YAML (de)serialization module to load the YAML file
    in the order listed in :obj:`config.YAML_MODULE_PRIORITIES`, falling back on the
    next if there's an :class:`ImportError`.
    """
    if isinstance(file_, str):
        with open(file_) as file_:
            return deserialize_from_yaml_to_obj(file_)
    yaml_loader = None
    for name in config.YAML_MODULE_PRIORITIES:
        if name in {"ruamel.yaml", "ruamel_yaml"}:
            try:
                if name == "ruamel.yaml":
                    from ruamel.yaml import YAML  # type: ignore
                else:
                    from ruamel_yaml import YAML  # type: ignore
                yaml_loader = YAML().load
                break
            except ImportError:
                pass
        elif name == "pyyaml":
            try:
                import yaml  # type: ignore

                # https://stackoverflow.com/questions/5121931/in-python-how-can-you-load-yaml-mappings-as-ordereddicts
                class OrderedLoader(yaml.FullLoader):
                    pass

                def construct_mapping(loader, node):
                    loader.flatten_mapping(node)
                    return OrderedDict(loader.construct_pairs(node))

                OrderedLoader.add_constructor(
                    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping
                )

                def yaml_loader(x):
                    return yaml.load(x, Loader=OrderedLoader)

                break
            except ImportError:
                pass
        else:
            raise ValueError(
                f"Invalid value in config.YAML_MODULE_PRIORITIES: '{name}'"
            )
    if yaml_loader is None:
        raise ImportError(
            f"Could not import any of {config.YAML_MODULE_PRIORITIES} for YAML deserialization"
        )
    obj = yaml_loader(file_)
    return obj


def deserialize_from_json_to_obj(file_: Union[TextIO, str]) -> Any:
    """Deserialize a JSON file into an object

    `JSON syntax <https://en.wikipedia.org/wiki/JSON>`__.

    Parameters
    ----------
    file_
        A path or pointer to the JSON file.
    """
    if isinstance(file_, str):
        with open(file_) as file_:
            return json.load(file_)
    else:
        return json.load(file_)
