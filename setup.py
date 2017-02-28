#!/usr/bin/env python

from os.path import exists
from setuptools import setup, find_packages

setup(
    name='swiftwind',
    version=open('VERSION').read().strip(),
    author='Adam Charnock',
    author_email='adam@adamcharnock.com',
    packages=find_packages(),
    scripts=[],
    url='https://github.com/adamcharnock/swiftwind',
    license='MIT',
    description='User-friendly billing for communal households',
    long_description=open('README.rst').read() if exists("README.rst") else "",
    include_package_data=True,
    install_requires=[
        'django>=1.8',
        'django-hordak>=1.4.0',
        'path.py',
        'django-model-utils>=2.5.0',
        'gunicorn',
        'django-bootstrap3 >=7, <8',
        'dj-database-url',
        'dj-static',
        'psycopg2',
        'django-extensions',
        'kombu==4.0.2',
        'celery==4.0.2',
        'django-celery-beat==1.0.1',
        'redis==2.10.5',
        'six',
        'python-dateutil',
        'django-adminlte2>=0.1.5',
    ],
)



