#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import setup, find_packages

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
    name='aiodirector',
    version='0.0.1b1',
    description="Micro framework based on asyncio",
    long_description=readme + '\n\n' + history,
    author="Konstantin Stepanov",
    url='https://github.com/konstantin-stepanov/aiodirector',
    packages=find_packages(include=['aiodirector']),
    include_package_data=True,
    install_requires=requirements.split('\n'),
    license="MIT license",
    zip_safe=False,
    keywords='aiodirector',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    test_suite='tests',
    tests_require=list(filter(lambda a: a, test_requirements.split('\n'))),
)
