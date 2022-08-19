Command-Line Interface
======================

combine_ini_files
-----------------

::

  usage: combine_ini_files [-h] sources [sources ...] dest
  
  Combine INI files
  
  This command provides a content-agnostic way of combining INI files
  (https://en.wikipedia.org/wiki/INI_file).
  
  All but the last positional argument consist of input files. Earlier values are
  clobbered by later values.
  
  Comments (anything after a '#' or ';') are ignored
  
  positional arguments:
    sources     Paths to read from
    dest        Path to write to
  
  optional arguments:
    -h, --help  show this help message and exit

combine_json_files
------------------

::

  usage: combine_json_files [-h] [--quiet] [--compact] [--nested]
                            sources [sources ...] dest
  
  Combine JSON files
  
  This command provides a content-agnostic way of combining JSON files
  (https://en.wikipedia.org/wiki/JSON).
  
  If all source files are lists, we merely append the lists together.
  
  If all documents' root data types are dictionaries, the default behaviour, given a
  collision of keys, is to clobber the old value with the new one. If the "--nested" flag
  is set, and both values are dictionaries, the values of the old dictionary will be
  updated with the values of the new one, but old keys not present in the new dictionary
  will persist. For example, without the "--nested" flag
  
      {"a": {"b": {"c": null}, "d": true}} +
      {"a": {"b": {"e": 1}}, "f": "g"} =
      {"a": {"b": {"e": 1}}, "f": "g"}
  
  but with the nested flag
  
      {"a": {"b": {"c": null}, "d": true}} +
      {"a": {"b": {"e": 1}}, "f": "g"} =
      {"a": {"b": {"c": null, "e": 1}, "d": true}, "f": "g"}
  
  Mixing root data types of sources or specifying more than one source for a root type
  that is not a dict or list will result in an error.
  
  positional arguments:
    sources     Paths to read from
    dest        Path to write to
  
  optional arguments:
    -h, --help  show this help message and exit
    --quiet
    --compact   By default, JSON dicts will have newlines and 2-space
                indentation. If set, will encode structures in the most compact
                way possible
    --nested    Resolve dict collisions by descending into children. See command
                documentation for more info

combine_yaml_files
------------------

::

  usage: combine_yaml_files [-h] [--quiet] [--nested] sources [sources ...] dest
  
  Combine YAML files
  
  This command provides a content-agnostic way of combining YAML files
  (https://en.wikipedia.org/wiki/YAML).
  
  All but the last positional argument consist of input files. Earlier values are
  clobbered by later values.
  
  If all source files are lists, we merely append the lists together.
  
  If all documents' root data types are dictionaries, the default behaviour, given a
  collision of keys, is to clobber the old value with the new one. If the "--nested" flag
  is set, and both values are dictionaries, the values of the old dictionary will be
  updated with the values of the new one, but old keys not present in the new dictionary
  will persist. See the "combine-json-files" command for an example
  
  Whether comments are ignored depends on the parsing backend.
  
  positional arguments:
    sources     Paths to read from
    dest        Path to write to
  
  optional arguments:
    -h, --help  show this help message and exit
    --quiet
    --nested    Resolve dict collisions by descending into children. See command
                documentation for more info

