#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""The setup script."""
import re
import sys
from setuptools import setup, find_packages


PY_VER = sys.version_info

if not PY_VER >= (3, 6):
    raise RuntimeError('aiodirector does not support Python earlier than 3.6')


with open('aiodirector/__init__.py') as ver_file:
    version = re.compile(r".*__version__ = '(.*?)'",
                         re.S).match(ver_file.read()).group(1)

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

with open('requirements.txt') as requirements_file:
    requirements = requirements_file.read()

with open('requirements_dev.txt') as requirements_dev_file:
    test_requirements = requirements_dev_file.read()
    test_requirements = test_requirements.replace('-r requirements.txt',
                                                  requirements)

setup(
    name='aioapp',
    version=version,
    description="Micro framework based on asyncio",
    long_description=readme + '\n\n' + history,
    author="Konstantin Stepanov",
    url='https://github.com/konstantin-stepanov/aiodirector',
    packages=find_packages(include=['aiodirector']),
    include_package_data=True,
    install_requires=list(filter(lambda a: a, requirements.split('\n'))),
    license="MIT license",
    zip_safe=False,
    keywords='aioapp',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
    ],
    test_suite='tests',
    tests_require=list(filter(lambda a: a, test_requirements.split('\n'))),
)
