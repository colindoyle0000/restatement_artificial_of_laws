"""Base class for all classes in the project.

Contains methods for saving and loading data.

save_to_json(self, filename: str) -> None
    Saves the serializable instance attributes to a JSON file.
    Parameters:
        filename (str): The name of the file to save the attributes to.

load_from_json(self, filename: str) -> None
    Loads the serializable instance attributes from a JSON file.
    Parameters:
        filename (str): The name of the file to load the attributes from.

save_prompts_to_md(self, name: str) -> None
    Saves prompts to a markdown file.
    Parameters:
        name (str): The name of the markdown file.
"""

import os
import json
import logging

from src.utils_string import get_timestamp


# Set up logger
logger = logging.getLogger('restatement')


class BaseClass:
    """Base class for all classes in the project.
    """

    def __init__(self, section):
        # List of prompts
        self.prompt_lst = []
        # String of prompts
        self.prompt_str = ""
        # Section object
        self.section = section

    def save_to_json(self, filename):
        """Saves the serializable instance attributes to a JSON file."""
        serializable_dict = {}
        for key, value in self.__dict__.items():
            try:
                json.dumps(value)
                serializable_dict[key] = value
            except TypeError:
                logger.warning("Attribute not serializable: %s. Skipped.", key)

        with open(filename, 'w', encoding="utf-8") as f:
            json.dump(serializable_dict, f)

    def load_from_json(self, filename):
        """Loads the serializable instance attributes from a JSON file."""
        try:
            with open(filename, 'r', encoding="utf-8") as f:
                data = json.load(f)
            for key, value in data.items():
                setattr(self, key, value)
        except FileNotFoundError:
            logger.warning("File not found: %s", filename)

    def save_prompts_to_md(self, name):
        """Save prompts to markdown file.
        """
        # Join the list of prompts into a single string.
        self.prompt_str = '\n'.join(self.prompt_lst)
        # Set path for markdown file.
        timestamp = get_timestamp()
        name = f"{name}_{timestamp}.md"
        # Open markdown file.
        with open(
            os.path.join(self.section.path_md, name),
            'w',
            encoding="utf-8"
        ) as f:
            # Write prompts
            f.write(f"# {name}\n\n")
            f.write(self.prompt_str)
            f.write("\n\n")
