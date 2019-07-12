from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import sys

from codecs import open
from os import path
from setuptools import setup

__author__ = "Sean Robertson"
__email__ = "sdrobert@cs.toronto.edu"
__license__ = "Apache 2.0"
__copyright__ = "Copyright 2018 Sean Robertson"

PWD = path.abspath(path.dirname(__file__))
with open(path.join(PWD, 'README.md'), encoding='utf-8') as readme_file:
    LONG_DESCRIPTION = readme_file.read()

SETUP_REQUIRES = ['setuptools_scm']
if {'pytest', 'test', 'ptr'}.intersection(sys.argv):
    SETUP_REQUIRES += ['pytest-runner']


def main():
    setup(
        name='pydrobert-param',
        description="Utilities for the python package 'param'",
        long_description=LONG_DESCRIPTION,
        long_description_content_type='text/markdown',
        use_scm_version=True,
        zip_safe=False,
        url='https://github.com/sdrobert/pydrobert-param',
        author=__author__,
        author_email=__email__,
        license=__license__,
        packages=['pydrobert', 'pydrobert.param'],
        classifiers=[
            'Development Status :: 3 - Alpha',
            'License :: OSI Approved :: Apache Software License',
            'Programming Language :: Python :: 2',
            'Programming Language :: Python :: 2.7',
            'Programming Language :: Python :: 3',
            'Programming Language :: Python :: 3.4',
            'Programming Language :: Python :: 3.5',
            'Programming Language :: Python :: 3.6',
            'Programming Language :: Python :: 3.7',
        ],
        install_requires=['param>=1.9', 'future', 'configparser'],
        setup_requires=SETUP_REQUIRES,
        tests_require=[
            'pytest', 'ruamel.yaml >= 0.15', 'pyyaml >= 4.2',
            'pandas', 'numpy'],
        entry_points={
            'console_scripts': [
                'combine-ini-files = pydrobert.param.command_line:'
                'combine_ini_files',
                'combine-json-files = pydrobert.param.command_line:'
                'combine_json_files',
                'combine-yaml-files = pydrobert.param.command_line:'
                'combine_yaml_files',
            ],
        }
    )


if __name__ == '__main__':
    main()
