"""
This module contains utility functions for string manipulation and formatting in the context of 
the 'restatement' project.

Functions

shorten_title(title: str) -> str
    Shortens a given string to the first line, removes section information, and limits it to 
    15 characters.
    Parameters:
        title (str): The title to be shortened.
    Returns:
        A shortened version of the input title.

get_timestamp() -> str
    Returns a timestamp in the format YYYY_MM_DD_HH_MM_SS.
    Returns:
        A string representing the current timestamp.

get_date() -> str
    Returns a date in the format YYYY_MM_DD.
    Returns:
        A string representing the current date.

set_prompt(prompt: str, prompt_path: str) -> str
    Updates the prompt to match any changes to txt files.
    Parameters:
        prompt (str): The initial prompt.
        prompt_path (str): The path to the txt file containing the updated prompt.
    Returns:
        The updated prompt.

replace_prompt_variables(
    prompt: str, 
    section_title: str, 
    restatement_title: str, 
    area_of_law: str, 
    description: str
) -> str
    Inserts content from title, area of law, and description into the prompts.
    Parameters:
        prompt (str): The initial prompt.
        section_title (str): The section title to be inserted.
        restatement_title (str): The restatement title to be inserted.
        area_of_law (str): The area of law to be inserted.
        description (str): The description to be inserted.
    Returns:
        The prompt with inserted variables.

set_full_prompt(prompt_path: str, section: object) -> str
    Sets the prompt string to text from a .txt file and inserts variables from a section object.
    Parameters:
        prompt_path (str): The path to the txt file containing the prompt.
        section (object): The section object containing variables to be inserted.
    Returns:
        The full prompt with inserted variables.

save_used_prompts(title: str, prompt_lst: list) -> str
    Saves the prompts used within a method to a string.
    Parameters:
        title (str): The title of the method.
        prompt_lst (list): The list of prompts used.
    Returns:
        A string containing the title and the used prompts.
"""
import logging
import re
from datetime import datetime

# Set up logger
logger = logging.getLogger('restatement')

def shorten_title(title):
    """Shorten a string to the first line, remove section information, limit to 15 characters."""
    # Split at "\n" and take the first part
    title_short = title.split("\n", 1)[0]
    # Remove leading "§" and digits
    title_short = re.sub(r"^[§.\d\s]*", "", title_short).strip()
    # Take just first fifteen characters
    title_short = title_short[:15]
    return title_short

def get_timestamp():
    """Return a timestamp in the format YYYY_MM_DD_HH_MM_SS."""
    now = datetime.now()
    yearmonthdaytime = now.strftime("%Y_%m_%d_%H_%M_%S")
    return yearmonthdaytime

def get_date():
    """Return a date in the format YYYY_MM_DD."""
    now = datetime.now()
    yearmonthday = now.strftime("%Y_%m_%d")
    return yearmonthday

def set_prompt(prompt, prompt_path):
    """Update prompt to match any changes to txt files"""
    with open(prompt_path, 'r', encoding="utf-8") as f:
        prompt = f.read()
    return prompt

def replace_prompt_variables(prompt, section_title, restatement_title, area_of_law, description):
    """Insert content from title, area of law, and description to the prompts."""
    prompt = prompt.replace('{self.section_title}', section_title)\
                    .replace('{self.restatement_title}', restatement_title)\
                        .replace('{self.area_of_law}', area_of_law)\
                            .replace('{self.description}', description)
    return prompt

def set_full_prompt(prompt_path, section):
    """Set prompt string to text from .txt file and insert variables from section.
    """
    output = ""
    with open(prompt_path, 'r', encoding="utf-8") as f:
        output = f.read()
        output = output.replace('{section_title}', section.section_title)\
                        .replace('{restatement_title}', section.restatement_title)\
                            .replace('{area_of_law}', section.area_of_law)\
                                .replace('{description}', section.description)
    return output

def save_used_prompts(title, prompt_lst):
    """Save the prompts used within a method to a string.
    """
    prompt_str = title
    prompts = '\n'.join(prompt_lst)
    prompt_str += '\n \n' + prompts + '\n \n'
    return prompt_str
