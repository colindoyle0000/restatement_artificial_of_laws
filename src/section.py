"""Section class is a composite class that manages the classes that build a restatement.
Any individual restatement section should be created as an instance of this class.

__init__(self, llm_settings: LLMSettings = LLMSettings())
    Initializes a new instance of the Section class. 
    It sets up various properties and class instances that will be used throughout the restatement
    creation process.

set_section_title(self, title: str)
    Sets the title of the section. 
    The title should be the legal issue that the section addresses.

set_area_of_law(self, area_of_law: str)
    Sets the title of the area of law (e.g., Property, Torts, Contracts, Judgments). 
    The title will be capitalized and used to automatically create the title of the restatement.

set_restatement_title(self, title: str)
    Sets the title of the restatement. 
    This is needed only if you don't want the title to be automatically generated from area of law.

set_description(self, description: str)
    Sets the description of the section. 
    This description can give the LLM some context for what particular legal issues the section 
    should address and what legal issues will be addressed by other sections.

set_cases_path(self, path: str)
    Sets the path to the folder where the cases are stored.

set_cases_folder(self, folder)
    Sets the name of the folder within the directory where cases are stored.

set_path(self, name: str = None, date: str = None)
    Sets the path for saving data to file.

set_llm_settings(
    self, embeddings = None,
    model: str = None,
    max_tokens: int = None,
    model_long: str = None,
    max_tokens_long: int = None,
    chunk_size: int = None,
    chunk_overlap: int = None,
    chunk_size_long: int = None,
    max_attempts: int = None
)
    Sets the LLM settings. 
    With this function, only the settings that you want to change need to be passed.
    

process_load_cases()
    This method executes each necessary method of the `LoadCases` class.
    It creates an instance of `LoadCases` and loads the cases as a list.

process_brief_cases()
    This method executes each necessary method of the `BriefCases` class.
    It creates an instance of `BriefCases`, removes synopses from each case in the list of cases,
    creates briefs from the list of cases, stores briefs in a vector database, saves attributes
    to a JSON file, and saves prompts and outputs to a markdown file.

process_extract()
    This method executes each necessary method of the `Extract` class. It creates an instance of
    `Extract`, copies black letter law provisions from case briefs, extracts only the rules and 
    not the case information, groups rules, saves attributes to a JSON file, and saves prompts and
    outputs to a markdown file.

process_discern()
    This method executes each necessary method of the `Discern` class. 
    It creates an instance of `Discern`, discerns consensus rule, decides what points of 
    disagreement to include, resolves each point of disagreement, rewrites rule following 
    the resolve process, creates notes on making rule more clear and logical, creates a 
    revised final rule, sets explanation of rule for later classes to use, saves attributes 
    to JSON file, and saves prompts and outputs to markdown file.

process_comment()
    This method executes each necessary method of the `Comment` class. 
    It creates an instance of `Comment`, creates an outline of the Comment, writes the Comment 
    components for each heading in the outline, saves attributes to JSON file, and saves prompts
    and outputs to markdown file.

process_illustration()
    This method executes each necessary method of the `Illustration` class.
    It creates an instance of `Illustration`, creates plan for illustrations, creates 
    illustrations for each comment, combines illustrations and comments, saves attributes
    to JSON file, and saves prompts and outputs to markdown file.

process_reporter()
    This method executes each necessary method of the `Reporter` class. It creates an instance of 
    `Reporter`, writes the Reporters Note, saves attributes to JSON file, and saves prompts and 
    outputs to markdown file.

set_final_draft()
    This method sets the final draft of the section based on prior outputs.

save_final_draft()
    This method saves the final draft to a markdown file.

save_attributes()
    This method saves attributes to a JSON file.

load_attributes(filename: str = None)
    This method loads attributes from a JSON file. 
    If no filename is passed, it uses the default filename.

"""

import logging
import re
import textwrap
import os
import json

from pathlib import Path

from src.utils_file import (
    get_root_dir
)

from src.utils_string import (
    shorten_title,
    get_timestamp,
    get_date
)

from src.utils_llm import (
    LLMSettings
)

from src.loadcases import LoadCases
from src.briefcases import BriefCases
from src.extract import Extract
from src.discern import Discern
from src.comment import Comment
from src.illustration import Illustration
from src.reporter import Reporter

# Set up logger
logger = logging.getLogger('restatement')


class Section:
    """Class for creating an artificial restatement section.
    This is a composite class that manages the classes that build a restatement.
    Any individual restatement section should be created
    as an instance of this class.
    """

    def __init__(self, llm_settings: LLMSettings = LLMSettings()):
        # LLM settings for the section (dataclass in utils_llm.py)
        self.llm_settings = llm_settings
        # Title of the area of law (e.g., Property, Torts, Contracts, Judgments)
        self.area_of_law = ""
        # Title of the larger restatement (e.g., Restatement of Property)
        self.restatement_title = ""
        # Title of the particular section the application will be writing
        self.section_title = ""
        # Short title is used for filenames and reference.
        self.section_title_short = ""
        # Description of the section
        self.description = ""

        # Filepath for cases
        self.cases_folder = ""
        self.cases_path = ""

        # Filepath for saving data from this section
        self.path = ""
        self.path_json = ""
        self.path_md = ""
        self.path_db = ""

        # Class instances
        self.loadcases = None
        self.briefcases = None
        self.extract = None
        self.discern = None
        self.comment = None
        self.illustration = None
        self.reporter = None

        # Groups of legal rules (passed between classes)
        self.groups_str = ""
        # Explanation of black letter law provision (passed between classes)
        self.explanation = ""
        # Final black letter law provision
        self.provision_final = ""
        # Final comment
        self.comment_final = ""
        # Final reporter's note
        self.reporter_final = ""

        # Final draft of the section
        self.final_draft = ""

    def set_section_title(self, title: str):
        """ Set the title of the section. 
        The title should be the legal issue that the section addresses.
        """
        self.section_title = title
        self.section_title_short = shorten_title(self.section_title)

    def set_area_of_law(self, area_of_law: str):
        """ Set the title of the area of law. (e.g., Property, Torts, Contracts, Judgments)
        The title will be capitalized and used to automatically create the title of the restatement.
        """
        # Capitalize first letter of each word in area_of_law
        area_of_law = area_of_law.title()
        # Use regex to exclude "of" and "in" from being capitalized
        area_of_law = re.sub(r'\b(?!of\b|in\b)\w+',
                             lambda m: m.group(0).capitalize(), area_of_law)
        self.area_of_law = area_of_law
        self.restatement_title = f"Restatement of {self.area_of_law}"

    def set_restatement_title(self, title: str):
        """ Set the title of the restatement.
        Needed only if you don't want the title to be automatically generated from the area of law.
        """
        self.restatement_title = title

    def set_description(self, description: str):
        """ Set the description of the section.
        This description can give the LLM some context for what particular legal issues the section 
        should address and what legal issues will be addressed by other sections.
        """
        self.description = description

    def set_cases_path(self, path: str):
        """ Set the path to the folder where the cases are stored.
        """
        self.cases_path = path
        path = Path(self.cases_path)
        if not path.exists():
            raise FileNotFoundError(
                f"No folder found at path: {self.cases_path}")

    def set_cases_folder(self, folder):
        """Set name of folder within directory where cases are stored."""
        self.cases_folder = folder
        # Set the case path to match any changes to the case folder name
        self.cases_path = str(get_root_dir()) + \
            f"/data/cases/{self.cases_folder}"
        path = Path(self.cases_path)
        # Check if the folder exists
        if not path.exists():
            raise FileNotFoundError(
                f"No folder found at path: {self.cases_path}")

    def set_path(self, name: str = None, date: str = None):
        """Set the path for saving data to file."""
        # If name or date are not passed, use the default directory.
        if name is None or date is None:
            date = get_date()
            self.path = os.path.join(
                get_root_dir(), "outputs", self.section_title_short, date)
        # If a directory is passed, use that directory.
        else:
            self.path = os.path.join(get_root_dir(), "outputs", name, date)
        # Create the directory if it does not exist.
        os.makedirs(self.path, exist_ok=True)
        # Set the path for saving data to json file.
        self.path_json = os.path.join(self.path, "json")
        # Create the directory if it does not exist.
        os.makedirs(self.path_json, exist_ok=True)
        # Set the path for saving data to markdown file.
        self.path_md = os.path.join(self.path, "md")
        # Create the directory if it does not exist.
        os.makedirs(self.path_md, exist_ok=True)
        # Set the path for saving vector database.
        self.path_db = os.path.join(self.path, "db")
        # Create the directory if it does not exist.
        os.makedirs(self.path_db, exist_ok=True)

    def set_llm_settings(
        self,
        embeddings=None,
        model: str = None,
        max_tokens: int = None,
        model_long: str = None,
        max_tokens_long: int = None,
        chunk_size: int = None,
        chunk_overlap: int = None,
        chunk_size_long: int = None,
        max_attempts: int = None
    ):
        """Set the LLM settings.
        With this function, only the settings that you want to change need to be passed.
        """
        if embeddings is not None:
            self.llm_settings.embeddings = embeddings
        if model is not None:
            self.llm_settings.model = model
        if max_tokens is not None:
            self.llm_settings.max_tokens = max_tokens
        if model_long is not None:
            self.llm_settings.model_long = model_long
        if max_tokens_long is not None:
            self.llm_settings.max_tokens_long = max_tokens_long
        if chunk_size is not None:
            self.llm_settings.chunk_size = chunk_size
        if chunk_overlap is not None:
            self.llm_settings.chunk_overlap = chunk_overlap
        if chunk_size_long is not None:
            self.llm_settings.chunk_size_long = chunk_size_long
        if max_attempts is not None:
            self.llm_settings.max_attempts = max_attempts

    def process_load_cases(self):
        """Execute each necessary method of LoadCases class.
        """
        # Create instance of LoadCases
        self.loadcases = LoadCases(section=self)
        # Load the cases as a list
        self.loadcases.rtf_to_list()

    def process_brief_cases(self):
        """Execute each necessary method of BriefCases class.
        """
        # Create instance of BriefCases
        self.briefcases = BriefCases(
            loadcases=self.loadcases,
            section=self
        )
        # Remove synopses from each case in list of cases
        self.briefcases.remove_synopsis()
        # Create briefs from list of cases
        self.briefcases.create_briefs()
        # Store briefs in a vector database
        self.briefcases.set_briefs_db()
        # Save attributes to JSON file
        self.briefcases.save_attributes()
        # Save prompts and outputs to markdown file.
        self.briefcases.save_to_md()

    def process_extract(self):
        """ Execute each necessary method of Extract class.
        """
        # Create instance
        self.extract = Extract(
            briefcases=self.briefcases,
            section=self
        )
        # Copy black letter law provisions from casebriefs
        self.extract.copy_rules()
        # Extract only the rules and not the case information
        self.extract.reduce_rules()
        # Group rules
        self.extract.group_process()
        # Save attributes to JSON file
        self.extract.save_attributes()
        # Save prompts and outputs to markdown file.
        self.extract.save_to_md()

    def process_discern(self):
        """Execute each necessary method of Discern class.
        """
        # Create instance of DiscernDis
        self.discern = Discern(
            extract=self.extract,
            section=self
        )
        # Discern consensus rule
        self.discern.get_consensus()
        # Decide what points of disagreement to include
        self.discern.get_disagreement()
        # Resolve each point of disagreement
        self.discern.resolve()
        # Rewrite rule following the resolve process
        self.discern.get_resolve_rule()
        # Create notes on making rule more clear and logical
        self.discern.get_clear()
        # Create a revised, final rule
        self.discern.get_edit()
        # Set explanation of rule for later classes to use
        self.discern.set_explanation()
        # Save attributes to JSON file
        self.discern.save_attributes()
        # Save prompts and outputs to markdown file.
        self.discern.save_to_md()

    def process_comment(self):
        """ Execute each necessary method of Comment class.
        """
        # Create instance of Comment
        self.comment = Comment(
            briefcases=self.briefcases,
            groups_str=self.groups_str,
            provision_final=self.provision_final,
            explanation=self.explanation,
            section=self
        )

        # Create an outline of the Comment.
        self.comment.outline()
        # Write the Comment components for each heading in the outline.
        self.comment.create_comments()
        # Save attributes to JSON file
        self.comment.save_attributes()
        # Save prompts and outputs to markdown file.
        self.comment.save_to_md()

    def process_illustration(self):
        """ Execute each necessary method of Illustration class.
        """
        # Create instance of Illustration
        self.illustration = Illustration(
            briefcases=self.briefcases,
            provision=self.provision_final,
            comment=self.comment,
            section=self
        )
        # Create plan for illustrations.
        self.illustration.create_plans()
        # Create illustrations for each comment.
        self.illustration.create_ills()
        # Combine illustrations and comments.
        self.illustration.combine_ills_comments()
        # Save attributes to JSON file
        self.illustration.save_attributes()
        # Save prompts and outputs to markdown file.
        self.illustration.save_to_md()

    def process_reporter(self):
        """ Execute each necessary method of Reporter class.
        """
        # Create instance of Reporter
        self.reporter = Reporter(
            briefcases=self.briefcases,
            comment=self.comment,
            illustration=self.illustration,
            section=self
        )
        # Write the Reporters Note
        self.reporter.report_all()
        # Save attributes to JSON file
        self.reporter.save_attributes()
        # Save prompts and outputs to markdown file.
        self.reporter.save_to_md()

    def set_final_draft(self):
        """Set the final draft of the section based on prior outputs.
        Note that if you experiment with different classes performing the same role, this will work
        if the final outputs are stored in the right attribute name in the Section instance.
        """
        # Create final draft
        self.final_draft = textwrap.dedent(
            f"""\
        **{self.restatement_title}**
        
        {self.provision_final}

        {self.comment_final}

        **Reporter's Note:**
        {self.reporter_final}
        """)

    def save_final_draft(self):
        """Save the final draft to a markdown file."""
        try:
            timestamp = get_timestamp()
            name = f"final_draft{timestamp}.md"
            with open(os.path.join(self.path_md, name), "w", encoding="utf-8") as f:
                f.write(self.final_draft)
        except IOError as e:
            logger.error("Failed to save final draft: %s", e)

    def save_attributes(self):
        """Save Section attributes attributes of each existing class to JSON file.
        """
        filename = os.path.join(self.path_json, 'section.json')
        serializable_dict = {}
        for key, value in self.__dict__.items():
            try:
                json.dumps(value)
                serializable_dict[key] = value
            except TypeError:
                logger.warning("Attribute not serializable: %s. Skipped.", key)

        with open(filename, 'w', encoding="utf-8") as f:
            json.dump(serializable_dict, f)

        # Save attributes of each class to JSON file.
        attributes = [self.briefcases,
                      self.extract,
                      self.discern,
                      self.comment,
                      self.illustration,
                      self.reporter
                      ]
        for attr in attributes:
            if attr is not None:
                attr.save_attributes()

    def load_attributes(self, filename: str = None):
        """Load attributes from JSON file.
        """
        # If no filename is passed, use the default filename.
        if filename is None:
            filename = os.path.join(self.path_json, 'section.json')
        try:
            with open(filename, 'r', encoding="utf-8") as f:
                data = json.load(f)
            for key, value in data.items():
                setattr(self, key, value)
        except FileNotFoundError:
            logger.warning("File not found: %s", filename)
        # Create instances of each class and load attributes from JSON file.

        self.loadcases = LoadCases(section=self)
        self.loadcases.rtf_to_list()

        self.briefcases = BriefCases(
            loadcases=self.loadcases,
            section=self
        )
        self.briefcases.load_attributes()
        self.briefcases.load_briefs_db()

        self.extract = Extract(
            briefcases=self.briefcases,
            section=self
        )
        self.extract.load_attributes()

        self.discern = Discern(
            extract=self.extract,
            section=self
        )
        self.discern.load_attributes()

        self.comment = Comment(
            briefcases=self.briefcases,
            groups_str=self.groups_str,
            provision_final=self.provision_final,
            explanation=self.explanation,
            section=self
        )
        self.comment.load_attributes()

        self.illustration = Illustration(
            briefcases=self.briefcases,
            provision=self.provision_final,
            comment=self.comment,
            section=self
        )
        self.illustration.load_attributes()

        self.reporter = Reporter(
            briefcases=self.briefcases,
            comment=self.comment,
            illustration=self.illustration,
            section=self
        )
        self.reporter.load_attributes()
