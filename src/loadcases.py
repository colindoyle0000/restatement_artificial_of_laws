"""This module contains the `LoadCases` class which is responsible for ingesting cases. 

Currently, it only supports cases in .rtf format. Other methods can be introduced here.
So long as the cases are stored as a list of strings in self.cases, the rest of the process should
function.

## Class: LoadCases

The `LoadCases` class has methods for ingesting cases. It stores the cases as a list of strings.

### Attributes

- `section`: The section object.
- `cases`: A list of strings, where each string is a case.

### Methods

__init__(self, section)
    The constructor for the `LoadCases` class. It initializes the `section` object and an empty 
    list of `cases`.

rtf_to_list(self)
    This method loads .rtf files from a folder into a list of strings. Each string in the list 
    represents a case.
"""
import logging
import os
from striprtf.striprtf import rtf_to_text

# Set up logger
logger = logging.getLogger('restatement')


class LoadCases:
    """Methods for ingesting cases.
    """

    def __init__(self, section):

        # Section object.
        self.section = section
        # List of strings, each string is a case.
        self.cases = []

    def rtf_to_list(self):
        """Load .rtf files from a folder into a list of strings."""
        self.cases = []
        try:
            for filename in os.listdir(self.section.cases_path):
                if filename.endswith(".rtf"):
                    with open(
                        os.path.join(self.section.cases_path, filename),
                        'r',
                        encoding="utf-8"
                    ) as f:
                        name = str(filename.replace(".rtf", ""))
                        content = f.read()
                        text = name + rtf_to_text(content)
                        self.cases += [text]
        except IOError as e:
            logger.error("Failed to load .rtf files: %s", e)
