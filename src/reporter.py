"""Reporter class for creating reporter's note for the Section.

### Attributes

- `briefcases`: A Briefcases object containing case briefs.
- `comment`: A Comment object containing the comment for the section.
- `illustration`: An Illustration object containing the illustrations for the comment.
- `section`: The section of the law.
- `outline`: A list representation of the outline of the comment, reformatted by removing 
the * characters.
- `reporter`: A list of reporter's notes for each part of the comment.
- `prompt_lst`: A list of prompts.
- `prompt_str`: A string representation of the prompts.
- `prompt_temp`: A temporary list of prompts.

### Methods

- `__init__(self, briefcases, comment, illustration, section)`: Initializes the Reporter 
object with the given parameters.
- `report_part(self, part)`: Creates a reporter's note for one part of the comment.
- `report_all(self, start_index=0)`: Creates reporter's notes for all parts of the comment. 
The `start_index` can be specified if a previous run was interrupted.
- `get_outputs(self)`: Returns the outputs from this class.
- `save_attributes(self)`: Saves the attributes to a JSON file.
- `load_attributes(self)`: Loads the attributes from a JSON file.
- `save_to_md(self)`: Saves the prompts and outputs to a markdown file.

"""
import logging
import textwrap
import os

from src.baseclass import BaseClass
from src.utils_file import (
    get_root_dir
)
from src.utils_llm import (
    num_tokens,
    sleep_for_tokens,
    llm_router,
    trim_part_for_tokens
)
from src.utils_string import (
    set_full_prompt,
    get_timestamp,
    save_used_prompts
)

# Set up logger
logger = logging.getLogger('restatement')


class Reporter(BaseClass):
    """ Class for creating reporters note for the Section.
    """

    def __init__(
        self,
        briefcases,
        comment,
        illustration,
        section
    ):
        super().__init__(section)
        # Initialize attributes for this instance.

        self.briefcases = briefcases
        self.comment = comment
        self.illustration = illustration
        self.comment = comment

        # Create a reformatted copy of the comment outline for use in Reporter's Note output.
        # Reformat by removing the * characters from each string.
        self.outline = [s.replace('*', '') for s in self.comment.outline_list]

        # Initialize variables for this instance
        self.reporter = []
        # Temporary list of prompts
        # This list is used within loops, then appended to prompt_list after loops are completed.
        self.prompt_temp = []

    def report_part(self, part):
        """Create reporters note for one part of the Comment
        """
        # Set prompts for LLM.
        # Set system prompt with contents from txt file
        prompt_system = set_full_prompt(
            os.path.join(get_root_dir(), "data", "prompts",
                         'reporter', "prompt_reporter.txt"),
            self.section
        )
        # Set human prompt. Note that {query} is required for LLMChain to work.
        prompt_human = textwrap.dedent(
            """
        Write the Reporters Note for this part of the Section.
        {query}
        """)

        # Get relevant briefs for query
        k = 1
        relevant_briefs = []
        # Get relevant briefs, looping until token limit is reached or
        # maximum k value is exceeded
        while True:
            try:
                # Get relevant briefs from briefs_db (vector database)
                relevant_briefs_x = self.briefcases.briefs_db.similarity_search(
                    part, k=k)
            except Exception:
                break
            # Convert relevant briefs to a list of strings
            relevant_briefs_x_doc = [
                doc.page_content for doc in relevant_briefs]
            # Join the list of strings with newline characters
            relevant_briefs_x_str = "\n \n".join(relevant_briefs_x_doc)
            # Calculate token length of input variables
            input_tokens = (
                num_tokens(relevant_briefs_x_str)
                + num_tokens(part)
                + num_tokens(prompt_system)
                + num_tokens(prompt_human)
            )
            # Check if token limit is exceeded
            if input_tokens > self.section.llm_settings.chunk_size:
                # If so, break out of loop
                break
            # Check if we have collected ten briefs
            if k >= 10:
                # If so, break out of loop
                relevant_briefs = relevant_briefs_x
                break
            # If token limit is not exceeded and maximum k value is not exceeded,
            # increment k, set relevant_briefs and continue loop
            k += 1
            relevant_briefs = relevant_briefs_x

        relevant_briefs_doc = [doc.page_content for doc in relevant_briefs]
        relevant_briefs_str = "\n \n".join(relevant_briefs_doc)

        # Set query to include the part and relevant briefs string.

        query = f"""

        Part of the Comment:
        {part}

        Potentially relevant cases:
        {relevant_briefs_str}
        """

        # Trim system prompt back to fit under token limit (should not be necessary)
        logger.debug("Token length of query: %s", num_tokens(query))

        remainder = query + prompt_human
        prompt_system = trim_part_for_tokens(
            prompt_system,
            remainder,
            max_tokens=self.section.llm_settings.chunk_size
        )

        # Set condense prompt (should not be necessary)
        prompt_condense = textwrap.dedent(
            """
            Do not edit the black letter law provision, outline, or component heading.
            Condense the casebriefs.
            """
        )

        # Call llm_router_gpt4 to create reporters note for this part
        logger.info("report_part: Creating reporters note for part")
        output, total_tokens, model, prompt_lst = llm_router(
            prompt_system,
            prompt_human,
            query,
            prompt_condense,
            self.section.llm_settings
        )
        return output, total_tokens, model, prompt_lst

    def report_all(self, start_index=0):
        """Create reporters note for all parts of the Section.
        start_index can be specified if a previous run was interrupted.
        """
        # If starting from beginning, then clear the reporter list and prompt_temp list.
        if start_index == 0:
            logger.debug("report_all: Clearing reporter and prompt_temp lists")
            self.reporter = []
            self.prompt_temp = []
        # Loop through ills_comments to create reporters note for each part
        logger.info(
            "report_all: Creating reporters note for all parts of the Section")
        for i, part in enumerate(self.illustration.ills_comments[start_index:]):
            logger.info("report_all: Creating reporters note for part %s of %s",
                        i + 1, len(self.illustration.ills_comments))
            # Get the corresponding outline string from self.outline and make it bold type.
            # This part of the output is hardcoded in Python rather than used as part of the prompt
            # because LLMs are bad at following prompt instructions about style formatting.
            outline_str = f"**{self.outline[start_index + i]}**"
            # Create reporters note for part
            part_report, part_tokens, part_model, prompt_lst = self.report_part(
                part)
            # Append the reporters note for the part to the reporter list
            self.reporter.append(f"{outline_str}\n\n{part_report['text']}")

            # Add prompts to prompt_temp list.
            self.prompt_temp += prompt_lst

            # Sleep function to prevent hitting API limit.
            sleep_for_tokens(part_tokens, part_model)

        # Set section.reporter_final to the final draft of the Reporter's Note from this method.
        self.section.reporter_final = "\n \n".join(self.reporter)

        # Save the prompts used in this method
        self.prompt_lst.append(save_used_prompts(
            "## Reporter prompts", self.prompt_temp))

    def get_outputs(self):
        """Get outputs from this class.
        """
        return self.__dict__

    def save_attributes(self):
        """Save attributes to JSON file
        """
        filename = os.path.join(self.section.path_json, "illustration.json")
        self.save_to_json(filename)

    def load_attributes(self):
        """Load attributes from JSON file.
        """
        filename = os.path.join(self.section.path_json, "illustration.json")
        self.load_from_json(filename)

    def save_to_md(self):
        """Save prompts and outputs to markdown file.
        """
        # Save prompts to markdown file
        self.save_prompts_to_md("reporter_prompts")
        # Save outputs to markdown file
        # Set path for markdown file.
        timestamp = get_timestamp()
        name = f"reporter_{timestamp}.md"
        # Open markdown file.
        with open(
            os.path.join(self.section.path_md, name),
            'w',
            encoding="utf-8"
        ) as f:
            # Write Reporter's Note
            f.write("# Reporter's Note\n\n")
            for part in self.reporter:
                f.write(f"{part}\n\n")
