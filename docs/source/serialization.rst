Serialization Tutorial
======================

As an example, suppose we have parameterized classes and instances:

.. code-block:: python

    import param
    class TrainingHyperparameters(param.Parameterized):
        lr = param.Number(1e-5, doc='The learning rate')
        max_epochs = param.Integer(10)
        model_regex = param.String(
            "model-{epoch:05d}.pkl",
            doc='Regular exp for storing model weights after every epoch')

    t_params = TrainingHyperparameters()

    class ModelHyperparameters(param.Parameterized):
        layers = param.ListSelector(
            [], objects=['conv', 'fc', 'recurrent'],
            doc='Sequence of layers by type, bottom-first')
        activations = param.ObjectSelector('relu', objects=['tanh', 'relu'])

    m_params = ModelHyperparameters()
    m_params.layers = ['conv', 'conv', 'fc']

    param_dict = {
      'training': t_params,
      'model': m_params,
    }

We can serialize these easily into JSON, YAML, or INI using
:mod:`pydrobert.param.serialization`:

.. code-block:: python

    import pydrobert.param.serialization as serial
    serial.serialize_to_json('conf.json', param_dict)
    serial.serialize_to_yaml('conf.yaml', param_dict)  # requires ruamel.yaml or pyyaml
    serial.serialize_to_ini('conf.ini', param_dict)

where we get

.. code-block:: json

    {
      "training": {
        "lr": 1e-05,
        "max_epochs": 10,
        "model_regex": "model-{epoch:05d}.pkl"
      },
      "model": {
        "activations": "relu",
        "layers": [
          "conv",
          "conv",
          "fc"
        ]
      }
    }

or

.. currently, there's a bug in YAML syntax (issue #1528 in pygments-main)
.. that doesn't like the last line of this example. Seems like it won't throw
.. an error, though!

.. code-block:: yaml

    training:
      lr: 1e-05  # The learning rate
      max_epochs: 10
      model_regex: model-{epoch:05d}.pkl # Regular exp for storing model weights after every epoch
    model:
      activations: relu  # Choices: "tanh", "relu"
      layers:  # Sequence of layers by type, bottom-first. Element choices: "conv", "fc", "recurrent"
        - conv
        - conv
        - fc

or

.. code-block:: ini

    # == Help ==
    # [training]
    # lr: The learning rate
    # model_regex: Regular exp for storing model weights after every epoch

    # [model]
    # activations: Choices: "tanh", "relu"
    # layers: Sequence of layers by type, bottom-first. A JSON string. Element choices: "conv", "fc", "recurrent"


    [training]
    lr = 1e-05
    max_epochs = 10
    model_regex = model-{epoch:05d}.pkl

    [model]
    activations = relu
    layers = ["conv", "conv", "fc"]

respectively.

Deserialization proceeds similarly. Files can be used to populate parameters in
existing parameterized instances.

.. code-block:: python

    t_params.lr = 10000.
    assert t_params.lr == 10000.
    serial.deserialize_from_yaml('conf.yaml', param_dict)
    assert t_params.lr == 1e-05

:mod:`pydrobert.param.argparse` contains convenience functions for
(de)serializing config files right from the command line.

.. code-block:: python

    import argparse, pydrobert.param.argparse as pargparse
    parser = argparse.ArgumentParser()
    pargparse.add_parameterized_read_group(parser, parameterized=param_dict)
    pargparse.add_parameterized_print_group(parser, parameterized=param_dict)


Sometimes, the default (de)serialization routines are unsuited for the data.
For example, INI files do not have a standard format for lists of values. For
this, and many other container types, values are parsed with JSON syntax. If we
wanted to parse lists differently, such as a comma-delimited list, we can
design a custom serializer and deserializer for handling our `layers`
parameter:

.. code-block:: python

    class CommaSerializer(serial.DefaultListSelectorSerializer):
        def help_string(self, name, parameterized):
            choices_help_string = super(CommaSerializer, self).help_string(name, parameterized)
            return 'Elements separated by commas. ' + choices_help_string

        def serialize(self, name, parameterized):
            val = super(CommaSerializer, self).serialize(name, parameterized)
            return ','.join(str(x) for x in val)

    class CommaDeserializer(serial.DefaultListSelectorDeserializer):
        def deserialize(self, name, block, parameterized):
            block = block.split(',')
            super(CommaDeserializer, self).deserialize(name, block, parameterized)

    serial.serialize_to_ini(
        'conf.ini', param_dict,
        # (de)serialize by type
        serializer_type_dict={param.ListSelector: CommaSerializer()},
    )
    serial.deserialize_from_ini(
        'conf.ini', param_dict,
        # or by name!
        deserializer_name_dict={'model': {'layers': CommaDeserializer()}},
    )


With ``conf.ini``:

.. code-block:: ini

    # == Help ==
    # [training]
    # lr: The learning rate
    # model_regex: Regular expression for storing model weights after every epoch

    # [model]
    # activations: Choices: "tanh", "relu"
    # layers: Sequence of layers by type, bottom-first. Elements separated by commas. Element choices: "conv", "fc", "recurrent"


    [training]
    max_epochs = 10
    model_regex = model-{epoch:05d}.pkl
    lr = 1e-05

    [model]
    activations = relu
    layers = conv,conv,fc
