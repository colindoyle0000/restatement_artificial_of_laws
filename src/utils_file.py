"""
Utility functions for loading, saving, and exporting within the 'restatement' project.

Functions
get_root_dir() -> str
    Returns the root directory for the package.
    Returns:
        A string representing the root directory of the package.
"""
import logging
import json
import os

from src.utils_string import get_timestamp

# Set up logger
logger = logging.getLogger('restatement')


def get_root_dir():
    """Returns the root directory for the package."""
    # get the current directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # get the root directory
    while os.path.basename(current_dir) != 'restatement_artificial_of_laws':
        current_dir = os.path.dirname(current_dir)
    return current_dir
