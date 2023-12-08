"""Setup file for the Restatements (Artificial) of Law project.

This Python project is a package for using large language models to generate
sections of a restatement of law based upon a set of cases and statutes that
the user provides.

The project is currently in the early stages of development. Comments and
feedback are welcome. 
Email: Colin.Doyle@lls.edu
"""
from setuptools import setup, find_packages

setup(
    name="restatement_artificial_of_laws",
    version="0.1",
    author="Colin Doyle",
    author_email="Colin.Doyle@LLS.edu",
    description="A package for using LLMs to develop legal knowledge and draft sections of restatements of law.",
    url="https://www.colin-doyle.net/",
    packages=find_packages(),
    package_data={
        'restatement_artificial_of_laws': ['data/*.txt'],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    install_requires=[
        'need to fill out',
        # Other dependencies
    ],
    )
