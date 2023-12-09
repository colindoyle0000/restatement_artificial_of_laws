"""Extract class for extracting legal rules from casebriefs.

## Attributes

- `briefcases`: An instance of the `BriefCases` class, which contains the briefs from which the 
rules will be extracted.
- `section`: The section of the law that the cases and briefs belong to.
- `rules`: A list of rules extracted from the briefs.
- `rules_token_list`: A list of content from rules, condensed so each item in list approaches 
token length.
- `groups`: A list of groups of rules.
- `groups_token_list`: A list of content from groups, condensed so each item in list approaches 
token length.
- `prompt_lst`: A list of prompts used to generate the rules and groups.
- `prompts_str`: A string of prompts used to generate the rules and groups.

## Methods

- __init__: Initializes an instance of the Extract class with briefcases and a section. 
It also initializes several attributes related to the extraction process.
- copy_rules: Copies legal rules from case briefs.
- reduce_rules: Extracts only the text of the rules from the copied string, removing any case 
information.
- group: Groups rules together using the LLM.
- group_all: Groups rules through multiple LLM calls when necessary.
- group_synthesize: Synthesizes separate notes on legal rules when the group_all method produces 
multiple outputs.
- group_condense: Condenses notes on legal rules if the notes are too long for the context window 
for subsequent LLM calls.
- group_organize: Converts the string of grouped law provisions to a list and token-list of groups.
- group_process: Executes methods for grouping as one composite process.
- get_outputs: Returns the outputs from this class.
- save_attributes: Saves the attributes to a JSON file.
- load_attributes: Loads the attributes from a JSON file.
- save_to_md: Saves the prompts and outputs to a markdown file.
"""
import logging
import re
import os
import textwrap

from src.baseclass import (BaseClass)
from src.utils_file import (
    get_root_dir
)
from src.utils_llm import (
    num_tokens,
    sleep_for_tokens,
    string_to_token_list,
    llm_loop_gpt4,
    llm_condense_string,
    llm_router_gpt4
)
from src.utils_string import (
    set_full_prompt,
    get_timestamp,
    save_used_prompts
)

# Set up logger
logger = logging.getLogger('restatement')


class Extract(BaseClass):
    """Class for extracting legal rules from casebriefs.
    """

    def __init__(
        self,
        briefcases,
        section
    ):
        super().__init__(section)
        self.briefcases = briefcases

        # Initialize attributes for this instance.
        # String of legal rules copied from casebriefs.
        self.copy_str = ""
        # List of content from copy_str, condensed so each item in list approaches token length.
        self.copy_token_list = []
        # String of rules extracted from copy_str
        self.rules_str = ""
        # List of content from rules_str, condensed so each item in list approaches token length.
        self.rules_token_list = []
        # String of grouped rules.
        self.groups_str = ""
        # List of content from groups_str, condensed so each item in list approaches token length.
        self.groups_token_list = []
        # List of content from groups_str, broken up by group
        self.groups_list = []

    def copy_rules(self):
        """Copy legal rules from casebriefs.
        Loops through the list of briefs and calls on LLM to copy black letter law 
        provisions.
        """

        # Set prompts for LLM.
        # Set system prompt with contents from txt file
        prompt_system = set_full_prompt(
            os.path.join(get_root_dir(), "data", "prompts",
                         "extract", "prompt_copy.txt"),
            self.section
        )
        # Set human prompt. Note that {query} is required for LLMChain to work.
        prompt_human = textwrap.dedent(
            """
        Casebriefs:
        {query}
        """)
        # Set condense prompt
        prompt_condense = textwrap.dedent(
            """Condense the following material:
        {query}
        """
        )

        # Loop through the list of briefs and call LLMChain to copy black letter law
        # provisions.
        logger.info("copy_rules: Copying rules from casebriefs.")
        lst, prompt_lst = llm_loop_gpt4(
            prompt_system,
            prompt_human,
            self.briefcases.briefs_token_list,
            prompt_condense,
            self.section.llm_settings
        )
        # Turn the list of copied provisions into one string.
        self.copy_str = '\n'.join(lst)
        # Break that string down into a list of strings, each of which is less than
        # the token limit.
        self.copy_token_list = string_to_token_list(self.copy_str)

        # Save the prompts used in this method
        self.prompt_lst.append(save_used_prompts(
            "## Copy prompts", prompt_lst))

    def reduce_rules(self):
        """Extract only the text of the rules from copy_str, removing any case information.
        This method does not use an LLM call but is done in Python.
        """
        # Use a regular expression to find all rules in self.copy_str
        rules = re.findall(r'Rule: (.*?)\n', self.copy_str, re.DOTALL)
        # Join the rules with a carriage return and assign to self.rules_str
        self.rules_str = '\n'.join(rules).strip()
        # Break that string down into a list of strings, each of which is less than
        # the token limit.
        self.rules_token_list = string_to_token_list(self.rules_str)

    def group(self, copy):
        """Group rules together.
        Take a string of copied legal rules and call LLMChain to discern the consensus rule,
        points of disagreement, and unique rules and exceptions.
        """
        # Set prompts for LLM.
        # Set system prompt with contents from txt file
        prompt_system = set_full_prompt(
            os.path.join(get_root_dir(), "data", "prompts",
                         'extract', "prompt_group.txt"),
            self.section
        )
        # Set human prompt. Note that {query} is required for LLMChain to work.
        prompt_human = textwrap.dedent(
            """\
        Notes:
        {query}
        """)
        # Set condense prompt
        prompt_condense = textwrap.dedent(
            """Condense the following material:
        {query}
        """
        )

        # Call LLMChain to group black letter law provisions from copy.
        logger.info("group: Grouping rule.")
        output, total_tokens, model, prompt_lst = llm_router_gpt4(
            prompt_system,
            prompt_human,
            copy,
            prompt_condense,
            self.section.llm_settings
        )

        sleep_for_tokens(total_tokens, model)
        return output['text'], prompt_lst

    def group_all(self):
        """Group rules through multiple LLM calls when necessary.
        Sometimes, the string of copied rules is too long for one LLM call to group the rules.
        This method loops through the token list of rules, runs the group method on each item,
        and then adds the results to the groups_str.
        """
        # Reset groups_str to empty string.
        self.groups_str = ""
        all_prompts_lst = []
        for i, copy in enumerate(self.rules_token_list):
            logger.info("group_all: Grouping rules. String %s of %s.",
                        i+1, len(self.rules_token_list))
            # Add a header to the groups_str for each note.
            self.groups_str += f"Notes #{i+1}:"
            # Group the rules from each note.
            notes, prompt_lst = self.group(copy=copy)
            # Add the grouped provisions to the groups_str.
            self.groups_str += notes
            self.groups_str += "\n \n"
            # Add prompt_lst to all_prompts_lst
            all_prompts_lst += prompt_lst

        # Save the prompts used in this method
        self.prompt_lst.append(save_used_prompts(
            "## Group prompts", all_prompts_lst))

    def group_synthesize(self):
        """Synthesize separate notes on legal rules.
        When the group_all method produces multiple outputs, those outputs need to be synthesized
        into one output. This method calls an LLM to combine those outputs.
        """
        # Set prompts for LLM.
        # Set system prompt with contents from txt file
        prompt_system = set_full_prompt(
            os.path.join(get_root_dir(), "data", "prompts",
                         'extract', "prompt_synthesize.txt"),
            self.section
        )
        # Set human prompt and query. Note that {query} is required for LLMChain to work.
        prompt_human = textwrap.dedent(
            """\
        Notes:
        {query}
        """)
        query = self.groups_str
        # Set condense prompt
        prompt_condense = textwrap.dedent(
            """Condense the following material:
        {query}
        """
        )

        # Call llm_router_gpt4 to synthesize notes.
        logger.info("group_synthesize: Synthesizing notes.")
        output, total_tokens, model, prompt_lst = llm_router_gpt4(
            prompt_system,
            prompt_human,
            query,
            prompt_condense,
            self.section.llm_settings
        )
        self.groups_str = output['text']

        # Save the prompts used in this method
        self.prompt_lst.append(save_used_prompts(
            "## Group synthesize prompts", prompt_lst))

        sleep_for_tokens(total_tokens, model)

    def group_condense(self):
        """Condense notes on legal rules if the notes are too long for context window for
        subsequent LLM calls.
        """
        # Set prompt for LLM.
        # Set system prompt with contents from txt file
        prompt_system = set_full_prompt(
            os.path.join(get_root_dir(), "data", "prompts",
                         'extract', "prompt_condense.txt"),
            self.section
        )

        # Call llm_condense_string to condense notes.
        logger.info("group_condense: Condensing notes.")
        self.groups_str, prompt_lst = llm_condense_string(
            self.groups_str,
            prompt_system,
            self.section.llm_settings.model,
            self.section.llm_settings.chunk_size,
            self.section.llm_settings.chunk_overlap
        )

        # Save the prompts used in this method
        self.prompt_lst.append(save_used_prompts(
            "## Group condense prompt", prompt_lst))

    def group_organize(self):
        """Convert string of grouped law provisions to list and token-list of groups.
        Also set section.groups_str to self.groups_str.
        """
        self.section.groups_str = self.groups_str
        self.groups_list = self.groups_str.split('***')
        # Remove groups that are too short.
        # Depending on how previous outputs were formatted,
        # there may be items in groups_list that are not groups but
        # empty strings or headings. We want to remove those.
        self.groups_list = [
            group for group in self.groups_list if len(group) >= 50]
        self.groups_token_list = string_to_token_list(self.groups_str)

    def group_process(self):
        """Execute methods for grouping as one composite process.
        """
        # Group rules.
        self.group_all()
        # Synthesize rules (if group_all results in multiple notes).
        if len(self.rules_token_list) > 1:
            self.group_synthesize()

        attempts = 0
        # Condense rules (if rules are too long for context window).
        while (num_tokens(self.groups_str) > self.section.llm_settings.max_tokens
               and attempts < self.section.llm_settings.max_attempts):
            self.group_condense()
            attempts += 1
            if attempts == self.section.llm_settings.max_attempts:
                raise ValueError("After "+str(self.section.llm_settings.max_attempts) +
                                 " attempts, the input is still too long.")
        # Organize rules into list and token list.
        self.group_organize()

    def get_outputs(self):
        """Get outputs from this class.
        """
        return self.__dict__

    def save_attributes(self):
        """Save attributes to JSON file
        """
        filename = os.path.join(self.section.path_json, "extract.json")
        self.save_to_json(filename)

    def load_attributes(self):
        """Load attributes from JSON file.
        """
        filename = os.path.join(self.section.path_json, "extract.json")
        self.load_from_json(filename)

    def save_to_md(self):
        """Save prompts and outputs to markdown file.
        """
        # Save prompts to markdown file
        self.save_prompts_to_md("extract_prompts")
        # Save outputs to markdown file
        # Set path for markdown file.
        timestamp = get_timestamp()
        name = f"extract_{timestamp}.md"
        # Open markdown file.
        with open(
            os.path.join(self.section.path_md, name),
            'w',
            encoding="utf-8"
        ) as f:
            # Write copy_str to markdown file.
            f.write("## Copy\n\n")
            f.write("*Legal rules the LLM copied from its casebriefs.* \n \n")
            f.write(self.copy_str)
            f.write("\n\n")
            # Write rules_str to markdown file.
            f.write("## Rules\n\n")
            f.write(
                "*Legal rules extracted from copy_str, removing case information.* \n \n")
            f.write(self.rules_str)
            f.write("\n\n")
            # Write groups_str to markdown file.
            f.write("## Groups\n\n")
            f.write("*Legal rules grouped by the LLM.* \n \n")
            f.write(self.groups_str)
            f.write("\n\n")
