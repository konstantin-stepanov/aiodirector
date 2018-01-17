#!/usr/bin/env python
import os
import io
import re
from setuptools import setup


def read(*path):
    return io.open(
        os.path.join(*([os.path.dirname(__file__)] + list(path))),
        encoding="UTF8"
    ).read()


VERSION = re.compile(r".*__version__ = '(.*?)'", re.S)\
    .match(read('aiodirector', '__init__.py')).group(1)

readme = read('README.md')

requirements = read('requirements.txt')

test_requirements = read('requirements_dev.txt').replace('-r requirements.txt',
                                                         requirements)

setup(
    name='aiodirector',
    version=VERSION,
    description="Micro framework based on asyncio",
    long_description=readme,
    author="Konstantin Stepanov",
    url='https://github.com/konstantin-stepanov/aiodirector',
    packages=[
        'aiodirector',
    ],
    package_dir={'aiodirector': 'aiodirector'},
    include_package_data=True,
    install_requires=requirements,
    zip_safe=False,
    keywords='aiodirector',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Framework :: AsyncIO',
        'Operating System :: POSIX',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
    ],
    test_suite='tests',
    tests_require=test_requirements
)
