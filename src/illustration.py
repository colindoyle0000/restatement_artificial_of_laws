"""Illustration class for creating illustrations for the comments.

### Attributes

- `briefcases`: A Briefcases object containing case briefs.
- `provision`: A Provision object containing the provision for the section.
- `comment`: A Comment object containing the comment for the section.
- `section`: The section of the law.
- `plans`: A list of plans for illustrations for each part of the comment.
- `ills`: A list of illustrations for each part of the comment.
- `ills_comments`: A list combining the illustrations and comments.
- `prompt_lst`: A list of prompts.
- `prompt_str`: A string representation of the prompts.
- `prompt_temp`: A temporary list of prompts.

### Methods
- __init__(self, briefcases, provision, comment, section): Initializes the class with the given 
parameters. It also initializes several lists and strings that will be used later.
- create_plan(self, comment, prior_plans): Creates a plan for illustrations for a given comment. 
It sets up prompts for the language model, trims the query to fit under the token limit, and 
calls the llm_router method to create the plan.
- create_plans(self, start_index=0): Loops through comments, creating plans for each. 
It can start from a specified index if a previous run was interrupted.
- create_ill(self, comment, plan): Creates illustrations for a given comment. It sets up prompts
for the language model, trims the query to fit under the token limit, and calls the llm_router 
method to create the illustration.
- create_ills(self, start_index=0): Loops through comments, creating illustrations for each. 
It can start from a specified index if a previous run was interrupted.
- combine_ills_comments(self): Combines illustrations and comments into one list.
- get_outputs(self): Returns the outputs from this class.
- save_attributes(self): Saves the attributes of the class to a JSON file.
- load_attributes(self): Loads the attributes of the class from a JSON file.
- save_to_md(self): Saves the prompts and outputs to a markdown file.
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
    trim_part_for_tokens,
)
from src.utils_string import (
    set_full_prompt,
    get_timestamp,
    save_used_prompts
)

# Set up logger
logger = logging.getLogger('restatement')


class Illustration(BaseClass):
    """ Class for creating illustrations for the comments.
    """

    def __init__(
        self,
        briefcases,
        provision,
        comment,
        section
    ):
        super().__init__(section)
        # Initialize variables for this instance

        self.briefcases = briefcases
        self.provision = provision
        self.comment = comment

        # List of plans for illustrations
        self.plans = []
        # List of illustrations
        self.ills = []
        # List of illustrations and comments
        self.ills_comments = []
        # String of illustrations and comments
        self.ills_comments_str = ""

        # Temporary list of prompts
        # This list is used within loops, then appended to prompt_list after loops are completed.
        self.prompt_temp = []

    def create_plan(self, comment, prior_plans):
        """Create a plan for illustration(s) for a comment.
        """
        # Set prompts for LLM.
        # Set system prompt with contents from txt file
        prompt_system = set_full_prompt(
            os.path.join(get_root_dir(), "data", "prompts",
                         'illustration', "prompt_plan.txt"),
            self.section
        )
        # Set human prompt. Note that {query} is required for LLMChain to work.
        prompt_human = textwrap.dedent(
            """
        Write a plan for illustrations for this part of the Comment.
        Your notes are: 
        {query}
        """
        )

        # Set query to include the provision, comment, outline of all comments,
        # and illustration plans.
        query = textwrap.dedent(
            f"""
        
        Black letter law provision:
        {self.provision}
        
        Comment:
        {comment}
        
        Outline of all Comments:
        {self.comment.outline_str}
        
        Plans so far:
        {prior_plans}
        """
        )

        # If necessary, trim back query to fit under token limit.
        logger.debug("Token length of query: %s", num_tokens(query))
        remainder = prompt_system + prompt_human
        query = trim_part_for_tokens(
            query,
            remainder,
            self.section.llm_settings.max_tokens_long,
            self.section.llm_settings.max_tokens_long / 2
        )

        # Set condense prompt (typically should not be necessary)
        prompt_condense = textwrap.dedent(
            """
            Do not edit the black letter law provision, outline, or component heading.
            Condense the casebriefs.
            """
        )

        # Call llm_router to create plan
        logger.info("create_plan: Creating plan for illustrations.")
        output, total_tokens, model, prompt_lst = llm_router(
            prompt_system,
            prompt_human,
            query,
            prompt_condense,
            self.section.llm_settings
        )
        return output, total_tokens, model, prompt_lst

    def create_plans(self, start_index=0):
        """Loop through comments, creating plans for each.
        start_index can be specified if a previous run was interrupted.
        """
        # If starting from the beginning, then clear the plans list and temporary prompt list.
        if start_index == 0:
            self.plans = []
            self.prompt_temp = []
        # Loop through comments, creating plan(s) for each.
        logger.info("create_plans: Creating plans for illustrations.")
        for i, comment in enumerate(self.comment.comments[start_index:]):
            logger.info("create_plans: Processing comment %s of %s",
                        i+start_index+1, len(self.comment.comments))
            # Set prior plans from plans list.
            prior_plans = '\n'.join(self.plans)
            # Create plan for comment.
            output, total_tokens, model, prompt_lst = self.create_plan(
                comment, prior_plans)

            # Append plan to plans list.
            plan = output['text']
            self.plans.append(plan)

            # Add prompts to temporary prompt list.
            self.prompt_temp += prompt_lst

            # Sleep for tokens
            sleep_for_tokens(total_tokens, model)

        # Save the prompts used in this method
        self.prompt_lst.append(save_used_prompts(
            "## Illustration plan prompts", self.prompt_temp))

    def create_ill(self, comment, plan):
        """Create illustration(s) for a comment.
        """
        # Set prompts for LLM.
        # Set system prompt with contents from txt file
        prompt_system = set_full_prompt(
            os.path.join(get_root_dir(), "data", "prompts",
                         'illustration', "prompt_create.txt"),
            self.section
        )
        # Set human prompt. Note that {query} is required for LLMChain to work.
        prompt_human = textwrap.dedent(
            """
        Write illustrations for this part of the Comment.
        Your notes are: {query}
        """)
        # Get relevant briefs for query
        k = 1
        relevant_briefs = []
        # Get relevant briefs, looping until token limit is reached or
        # maximum k value is exceeded
        while True:
            # Get relevant briefs from briefs_db (vector database)
            relevant_briefs_x = self.briefcases.briefs_db.similarity_search(
                comment, k=k)
            # Convert relevant briefs to a list of strings
            relevant_briefs_x_doc = [
                doc.page_content for doc in relevant_briefs]
            # Join the list of strings with newline characters
            relevant_briefs_x_str = "\n \n".join(relevant_briefs_x_doc)
            # Calculate token length of input variables
            input_tokens = (
                num_tokens(relevant_briefs_x_str)
                + num_tokens(self.provision)
                + num_tokens(comment)
                + num_tokens(prompt_system)
                + num_tokens(prompt_human)
            )
            # Check if token limit is exceeded
            if input_tokens > self.section.llm_settings.chunk_size:
                # If so, break out of loop
                break
            # Check if we have collected five briefs
            if k >= 5:
                # If so, break out of loop
                relevant_briefs = relevant_briefs_x
                break
            # If token limit is not exceeded and maximum k value is not exceeded,
            # increment k, set relevant_briefs and continue loop
            k += 1
            relevant_briefs = relevant_briefs_x
        relevant_briefs_doc = [doc.page_content for doc in relevant_briefs]
        relevant_briefs_str = "\n \n".join(relevant_briefs_doc)

        # Set query to include the provision, comment, and briefs.
        query = textwrap.dedent(
            f"""
        Plan for illustrations:
        {plan}
        Black letter law provision:
        {self.provision}
        Comment:
        {comment}
        Relevant casebriefs:
        {relevant_briefs_str}
        """
        )

        # If necessary, trim back query to fit under token limit.
        logger.debug("Token length of query: %s", num_tokens(query))
        remainder = prompt_system + prompt_human
        query = trim_part_for_tokens(
            query,
            remainder,
            self.section.llm_settings.max_tokens_long,
            self.section.llm_settings.max_tokens_long / 2
        )

        # Set condense prompt (typically should not be necessary)
        prompt_condense = textwrap.dedent(
            """
            Do not edit the black letter law provision, outline, or component heading.
            Condense the casebriefs.
            """
        )

        # Call llm_router to create illustration
        logger.info("create_ill: Creating illustrations.")
        output, total_tokens, model, prompt_lst = llm_router(
            prompt_system,
            prompt_human,
            query,
            prompt_condense,
            self.section.llm_settings
        )
        return output, total_tokens, model, prompt_lst

    def create_ills(self, start_index=0):
        """Loop through comments, creating illustrations for each.
        start_index can be specified if a previous run was interrupted.
        """
        # If starting from the beginning,
        # then clear the ills_comments list and temporary prompt list.
        if start_index == 0:
            logger.debug(
                "create_ills: Clearing ills, ills_comments list, and temporary prompt list.")
            self.ills = []
            self.ills_comments = []
            self.prompt_temp = []
        # Loop through comments, creating illustration(s) for each.
        logger.info("create_ills: Creating illustrations.")
        for i, comment in enumerate(self.comment.comments[start_index:]):
            logger.info("create_ills: Processing comment %s of %s",
                        i+start_index+1, len(self.comment.comments))
            # Set plan for comment from plans list.
            plan = self.plans[i+start_index]
            # Create illustration for comment.
            output, total_tokens, model, prompt_lst = self.create_ill(
                comment, plan)

            # Append illustration to ills list.
            ill = output['text']
            self.ills.append(ill)

            # Add prompts to temporary prompt list.
            self.prompt_temp += prompt_lst

            # Sleep for tokens
            sleep_for_tokens(total_tokens, model)

        # Save the prompts used in this method
        self.prompt_lst.append(save_used_prompts(
            "## Illustration prompts", self.prompt_temp))

    def combine_ills_comments(self):
        """ Combine illustrations and comments into one list.
        """
        # Check if self.comments and self.ills have the same length
        if len(self.comment.comments) != len(self.ills):
            logger.warning(
                "Warning: self.comment.comments and self.ills have different lengths.")

        # Simultaneously iterate over self.comments and self.ills_edits to create ills_comments
        self.ills_comments = (
            [comment + "\n \n" + ill + "\n \n" for comment,
                ill in zip(self.comment.comments, self.ills)]
        )

        # Create comment_ills string from list of ills_comments
        self.ills_comments_str = "\n".join(self.ills_comments)

        # Set section.comment_final to the final draft of the Comment from this method.
        self.section.comment_final = self.ills_comments_str

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
        self.save_prompts_to_md("illustration_prompts")
        # Save outputs to markdown file
        # Set path for markdown file.
        timestamp = get_timestamp()
        name = f"illustration_{timestamp}.md"
        # Open markdown file.
        with open(
            os.path.join(self.section.path_md, name),
            'w',
            encoding="utf-8"
        ) as f:
            # Write plans
            f.write("# Illustration Plans\n\n")
            for plan in self.plans:
                f.write(plan)
                f.write("\n\n")
            # Write illustrations
            f.write("# Initial Illustrations\n\n")
            for ill in self.ills:
                f.write(ill)
                f.write("\n\n")
            # Write comments and illustrations
            f.write("# Combined Comments and Final Illustrations\n\n")
            f.write(self.ills_comments_str)
            f.write("\n\n")
