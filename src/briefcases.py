"""
This module contains the BriefCases class, which is used for turning legal opinions into casebriefs. 

The BriefCases class takes in legal cases and a section, and provides methods to process and 
condense these cases into briefs. It also provides methods to save and load these briefs, as 
well as their attributes, from JSON files and vector databases.

This module relies on several utility modules for file handling (`utils_file`), 
llm calls (`utils_llm`), and string manipulation (`utils_string`).

## Attributes

- `cases`: A list of cases to be converted into briefs.
- `section`: The section of the law that the cases belong to.
- `briefs`: A list of briefs generated from the cases.
- `briefs_token_list`: A list of content from briefs, condensed so each item in list approaches 
token length.
- `briefs_db`: A vector database of briefs.
- `prompt_lst`: A list of prompts used to generate the briefs.
- `prompts_str`: A string of prompts used to generate the briefs.

## Methods

- `__init__(self, loadcases, section)`: Initializes the `BriefCases` class with a list of cases 
and a section.
- `remove_synopsis(self)`: Removes the synopsis from each case.
- `llm_condense_case(self, case)`: Condenses a case to fit within the context window.
- `create_brief(self, case)`: Creates a brief from a case.
- `create_briefs(self, start_index=0)`: Creates briefs for all of the cases.
- `set_briefs_token_list(self)`: Sets `briefs_token_list` from `briefs`.
- `set_briefs_db(self)`: Stores `briefs` in a vector database.
- `load_briefs_db(self, path=None)`: Loads `briefs` from a vector database.
- `get_outputs(self)`: Returns the outputs from this class.
- `save_attributes(self)`: Saves attributes to a JSON file.
- `load_attributes(self, filename=None)`: Loads attributes from a JSON file.
- `save_to_md(self)`: Saves prompts and outputs to a markdown file.
"""
import logging
import re
import os
import textwrap
from src.baseclass import BaseClass
from src.utils_file import (
    get_root_dir
)
from src.utils_llm import (
    llm_call,
    llm_call_long,
    num_tokens,
    sleep_for_tokens,
    string_to_token_list,
    list_to_token_list,
    list_to_db,
    load_db
)

from src.utils_string import (
    set_full_prompt,
    get_timestamp
)

# Set up logger
logger = logging.getLogger('restatement')


class BriefCases(BaseClass):
    """Class for turning legal opinions into briefs.
    """

    def __init__(
        self,
        loadcases,
        section
    ):
        super().__init__(section)

        self.cases = loadcases.cases

        # Initialize attributes
        # List of briefs
        self.briefs = []
        # List of content from briefs, condensed so each item in list approaches token length.
        self.briefs_token_list = []
        # Vector database of briefs
        self.briefs_db = []

    def remove_synopsis(self):
        """Remove the synopsis from each case.
        Some case files may have a short synopsis paragraph at the beginning.
        We don't want our LLM to have access to this when building the brief.
        This function loops through the list of cases and removes the synopsis,
        if one is present.
        """
        for i, case in enumerate(self.cases):
            # Check for 'synopsis' within the first 1500 characters
            if 'synopsis' in case[:1500].lower():
                # If 'synopsis' is found, then remove 'synopsis' and any material after it
                # until it hits the '*'.
                # The rest of the string after the first 1500 characters is kept intact.
                self.cases[i] = re.sub(
                    r'Synopsis.*?\*', '', case[:1500], flags=re.DOTALL) + case[1500:]

    def llm_condense_case(
        self,
        case
    ):
        """ Condense a case to fit within the context window.
        This is similar to llm_utils' llm_condense_string function except that the first LLM call
        includes instructions to preserve case information that is usually at the beginning of 
        a legal opinion.
        """
        case_condensed = ""
        prompts_str = ""

        # Split up strings into token-sized list
        texts = string_to_token_list(
            case,
            chunk_size=self.section.llm_settings.chunk_size_long,
            chunk_overlap=self.section.llm_settings.chunk_overlap)
        logger.debug(
            "llm_condense_case: Number of strings to condense: %s", len(texts))

        # Set prompts for LLM.
        # Set brief condense prompt with contents from txt file
        prompt_brief_condense = set_full_prompt(
            os.path.join(get_root_dir(), "data", "prompts",
                         "brief", "prompt_brief_condense.txt"),
            self.section
        )
        # Set brief condense0 prompt
        # The reason for two condense prompts is that condense0 preserves case information
        # from the top of legal opinion.
        prompt_brief_condense0 = textwrap.dedent(
            f"""
        At the top of your notes please list the following information:
        Case Name:
        Citation:
        Jurisdiction:
        Year:
        {prompt_brief_condense}
        """
        )
        # Set human prompt. Note that {query} is required for LLMChain to work.
        prompt_human = "Please write a shorter version of this: {query}"

        # Call on LLM to condense each string in the list. Then add each output to case_condensed.
        logger.debug(
            "llm_condense_case: Condensing case. %s strings to condense.", len(texts))
        for count, text in enumerate(texts):
            if count == 0:
                prompt_system = prompt_brief_condense0
            else:
                prompt_system = prompt_brief_condense
            logger.debug(
                "llm_condense_case: Condensing string %s of %s.", count, len(texts))
            output, total_tokens, model, chat_prompt_str = llm_call_long(
                prompt_system,
                prompt_human,
                query=text,
                model=self.section.llm_settings.model_long
            )

            case_condensed += output["text"] + "\n \n"
            prompts_str += chat_prompt_str + "\n \n"
            logger.debug(
                "llm_condense_case: String str(%s+1) of %s condensed.", count, len(texts))

            # Sleep for tokens
            sleep_for_tokens(total_tokens, model)

        return case_condensed, prompts_str

    def create_brief(self, case):
        """Create a brief from a case.
        Returns a tuple of the output, tokens used, and model used. Tokens and model are
        used to calculate the amount of time to sleep between API calls.
        This is a modified version of the llm_router function. The loops are modified to make
        sure that case specific information is not lost.
        """
        # Initialize variable that will store the prompts used in this method.
        brief_prompts = ""

        # Set prompts for LLM.
        # Set system prompt with contents from txt file
        prompt_system = set_full_prompt(
            os.path.join(get_root_dir(), "data", "prompts",
                         "brief", "prompt_brief.txt"),
            self.section
        )
        # Set human prompt. Note that {query} is required for LLMChain to work.
        prompt_human = textwrap.dedent(
            """
            Please write a casebrief based on the following legal opinion:
            {query}
            """
        )
        query = case
        total_tokens = num_tokens(prompt_system + prompt_human + query)

        # Initialize attempts
        attempts = 0

        # If the token length of the case is too long, then condense it.
        while (total_tokens > self.section.llm_settings.max_tokens_long and
               attempts < self.section.llm_settings.max_attempts):
            logger.debug("create_brief: Case is too long. Condensing. Attempt %s of %s.",
                         attempts, self.section.llm_settings.max_attempts)
            query, prompts_str = self.llm_condense_case(query)
            attempts += 1
            brief_prompts += "##Condense prompt \n \n" + prompts_str + "\n \n \n"
            total_tokens = num_tokens(prompt_system + prompt_human + query)

        # If token length is under max tokens, then use the regular llm_call function.
        if total_tokens <= self.section.llm_settings.max_tokens:
            logger.debug(
                "create_brief: Case is under max tokens. Using regular llm_call.")
            brief, total_tokens, model, chat_prompt_str = llm_call(
                prompt_system,
                prompt_human,
                query,
                model=self.section.llm_settings.model
            )
        # If token length is under max_tokens_long, then use the llm_call_long function.
        elif total_tokens <= self.section.llm_settings.max_tokens_long:
            logger.debug(
                "create_brief: Case is under max tokens long. Using llm_call_long.")
            brief, total_tokens, model, chat_prompt_str = llm_call_long(
                prompt_system,
                prompt_human,
                query,
                model=self.section.llm_settings.model_long
            )
        # If token length can't be condensed under max_tokens_long after max attempts,
        # then raise an error.
        else:
            raise ValueError("After "+str(self.section.llm_settings.max_attempts) +
                             " attempts, the input is still too long.")
        brief_prompts += "## Brief prompt \n \n" + chat_prompt_str + "\n \n \n"

        return (brief, total_tokens, model, brief_prompts)

    def create_briefs(self, start_index=0):
        """Create briefs for all of the cases.
        start_index can be specified if a previous run was interrupted.
        """
        # If starting from beginning, then clear the briefs list and prompts list.
        if start_index == 0:
            self.briefs = []
            self.prompt_lst = []
        # Loop through each case and create a brief.
        for i, case in enumerate(self.cases[start_index:]):
            try:
                logger.info("create_briefs: Creating brief %s of %s.",
                            i + start_index, len(self.cases))
                # Create brief for case
                brief, total_tokens, model, brief_prompts = self.create_brief(
                    case)
                # Append brief to list of briefs
                self.briefs.append(brief['text'])
                # Append brief prompts to list of prompts
                self.prompt_lst.append(brief_prompts)
                # Sleep function to prevent hitting API limit.
                sleep_for_tokens(total_tokens, model)
            except Exception as e:
                logger.critical(
                    "Exception occurred at index %s: %s", i + start_index, e)
                logger.critical(
                    "Please run create_briefs(%s) to resume from this index.", i + start_index)
                break
        # Create a list of token-sized text from the briefs.
        self.briefs_token_list = list_to_token_list(
            self.briefs,
            self.section.llm_settings.chunk_size,
            self.section.llm_settings.chunk_overlap
        )

    def set_briefs_token_list(self):
        """Set briefs_token_list from briefs.
        """
        self.briefs_token_list = list_to_token_list(
            self.briefs,
            self.section.llm_settings.chunk_size,
            self.section.llm_settings.chunk_overlap
        )

    def set_briefs_db(self):
        """Store briefs in a vector database.
        """
        self.briefs_db = list_to_db(
            lst=self.briefs,
            name=self.section.section_title_short,
            path=self.section.path_db,
            settings=self.section.llm_settings
        )

    def load_briefs_db(self, path=None):
        """Load briefs from a vector database.
        """
        # If path is not specified, then set path to the section path_db, plus the section name.
        if path is None:
            path = os.path.join(self.section.path_db,
                                f"{self.section.section_title_short}.db")
        self.briefs_db = load_db(path)

    def get_outputs(self):
        """Get outputs from this class.
        """
        return self.__dict__

    def save_attributes(self):
        """Save attributes to JSON file
        """
        filename = os.path.join(self.section.path_json, "briefcases.json")
        self.save_to_json(filename)

    def load_attributes(self, filename=None):
        """Load attributes from JSON file.
        """
        if filename is None:
            filename = os.path.join(self.section.path_json, "briefcases.json")
        self.load_from_json(filename)

    def save_to_md(self):
        """Save prompts and outputs to markdown file.
        """
        # Save prompts to markdown file
        self.save_prompts_to_md("brief_prompts")
        # Save outputs to markdown file
        # Set path for markdown file.
        timestamp = get_timestamp()
        name = f"brief_cases_{timestamp}.md"
        # Open markdown file.
        with open(
            os.path.join(self.section.path_md, name),
            'w',
            encoding="utf-8"
        ) as f:
            # Write Case Briefs to markdown file.
            f.write("# Case Briefs \n \n")
            for brief in self.briefs:
                f.write(f"{brief} \n \n")
