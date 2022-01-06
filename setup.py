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
        'django>=1.8, <2',
        'django-hordak>=1.4.0',
        'django-model-utils>=2.5.0',
        'gunicorn',
        'django-bootstrap3 >=9, <10',
        'dj-database-url',
        'dj-static',
        'psycopg2==2.7.3.2',
        'django-extensions',
        'kombu==4.0.2',
        'celery==5.2.2',
        'django-celery-beat==1.0.1',
        'redis==2.10.5',
        'six',
        'python-dateutil',
        'django-adminlte2>=0.1.5',
        'schedule==0.5.0',
    ],
)



