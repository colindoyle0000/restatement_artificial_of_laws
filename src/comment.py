"""Comment class for creating comment for black letter law provision.

### Attributes

- `briefcases`: A Briefcases object containing case briefs.
- `groups_str`: A string representation of the groups.
- `provision_final`: The final version of the provision.
- `explanation`: The explanation of the provision.
- `section`: The section of the law.
- `outline_str`: A string representation of the outline of the comment.
- `outline_list`: A list representation of the outline of the comment.
- `comments`: A list of comments.
- `comments_str`: A string representation of the comments.
- `prompt_lst`: A list of prompts.
- `prompt_str`: A string representation of the prompts.
- `prompt_temp`: A temporary list of prompts.

### Methods

- `__init__(self, briefcases, groups_str, provision_final, explanation, section)`: Initializes the Comment object with the given parameters.
- `outline(self)`: Creates an outline of the Comment.
- `create_comment(self, heading)`: Creates a component of the Comment.
- `create_comments(self, start_index=0)`: Creates comments for each heading in the outline. The `start_index` can be specified if a previous run was interrupted.
- `get_outputs(self)`: Returns the outputs from this class.
- `save_attributes(self)`: Saves the attributes to a JSON file.
- `load_attributes(self)`: Loads the attributes from a JSON file.
- `save_to_md(self)`: Saves the prompts and outputs to a markdown file.
"""
import os
import logging
import textwrap

from click import prompt
from src.utils_file import (
    get_root_dir,
    save_to_json,
    load_from_json,
    save_prompts_to_md
)
from src.utils_llm   import (
    num_tokens,
    sleep_for_tokens,
    string_to_token_list,
    llm_loop_gpt4,
    llm_condense_string,
    llm_router,
    llm_router_gpt4,
    trim_part_for_tokens
)
from src.utils_string import (
    set_full_prompt,
    get_timestamp,
    save_used_prompts
)

# Set up logger
logger = logging.getLogger('restatement')

class Comment:
    """ Class for creating comment for black letter law provision.
    """
    
    def __init__(
        self,
        briefcases,
        groups_str,
        provision_final,
        explanation,
        section
        ):

        self.briefcases = briefcases
        self.groups_str = groups_str
        self.provision_final = provision_final
        self.explanation = explanation
        self.section = section

        # Initialize variables for this instance
        self.outline_str = ""
        self.outline_list = []
        self.comments = []
        self.comments_str = ""
        # List of prompts
        self.prompt_lst = []
        # String of prompts
        self.prompt_str = ""
        # Temporary list of prompts
        # This list is used within loops, then appended to prompt_lst after loops are completed.
        self.prompt_temp = []

    def outline(self):
        """Create an outline of the Comment.
        """
        # Set prompts for LLM.
        # Set system prompt with contents from txt file
        prompt_system = set_full_prompt(
            os.path.join(get_root_dir(), "data", "prompts", 'comment', "prompt_outline.txt"),
            self.section
        )
        # Set human prompt. Note that {query} is required for LLMChain to work.
        prompt_human = textwrap.dedent(
        """
        Write an outline of the Comment for this provision.
        Your notes are: 
        {query}
        """)
        # Set query to include the provision, explanation, and groups_str
        query = textwrap.dedent(
        f"""
        Black letter law provision: 
        {self.provision_final} 
        Explanation:
        {self.explanation}
        """)
        
        # System prompt has many examples. May need to trim back to fit under token limit.
        logger.debug("Token length of system prompt: %s", num_tokens(prompt_system))
        remainder = prompt_human + query
        prompt_system = trim_part_for_tokens(
            prompt_system,
            remainder,
            max_tokens=self.section.llm_settings.max_tokens,
            trim_tokens=(self.section.llm_settings.max_tokens / 2)
            )

        # Set condense prompt (should not be necessary)
        prompt_condense = "Do not edit the black letter law provision. Condense the Notes and Explanation."

        # Call llm_router_gpt4 to create outline
        logger.info("outline: Creating outline of Comment.")
        output, total_tokens, model, prompt_lst = llm_router_gpt4(
            prompt_system,
            prompt_human,
            query,
            prompt_condense,
            self.section.llm_settings
            )
        # Set outline_str
        self.outline_str = output['text']

        # Split outline_str into a list of strings
        self.outline_list = self.outline_str.split("\n")
        # Remove any strings that are too short to be a heading
        # This may occur if the outline_str includes blank lines or headings that are not comment headings.
        self.outline_list = [item for item in self.outline_list if len(item) >= 15]
    
        # Save the prompts used in this method
        self.prompt_lst.append(save_used_prompts("## Outline prompts", prompt_lst))

        # Sleep for tokens
        sleep_for_tokens(total_tokens, model)

    def create_comment(self, heading):
        """Create a component of the Comment.
        """
        # Set prompts for LLM.
        # Set system prompt with contents from txt file
        prompt_system = set_full_prompt(
            os.path.join(get_root_dir(), "data", "prompts", 'comment', "prompt_comment.txt"),
            self.section
        )
        # Set human prompt. Note that {query} is required for LLMChain to work.
        prompt_human = textwrap.dedent(
        """
        Write one component of the Comment for this provision.
        Your notes are:
        {query}
        """)
        # Retrieve relevant briefs
        k = 1
        relevant_briefs = []
        # Get relevant briefs, looping until token limit is reached or 
        # maximum k value is exceeded
        while True:
            try:
                # Get relevant briefs from briefs_db (vector database)
                relevant_briefs_x = self.briefcases.briefs_db.similarity_search(heading, k=k)
            except Exception as e:
                break
            # Convert relevant briefs to a list of strings
            relevant_briefs_x_doc = [doc.page_content for doc in relevant_briefs]
            # Join the list of strings with newline characters
            relevant_briefs_x_str = "\n \n".join(relevant_briefs_x_doc)
            # Calculate token length of input variables
            input_tokens = (
                num_tokens(relevant_briefs_x_str)
                + num_tokens(heading)
                + num_tokens(self.provision_final)
                + num_tokens(self.outline_str)
                + num_tokens(self.explanation)
                + num_tokens(prompt_system)
                + num_tokens(prompt_human)
            )            
            # Check if token limit is exceeded
            if input_tokens > self.section.llm_settings.chunk_size:
                # If so, break out of loop
                break
            # Check if we have collected eight briefs
            if k >= 8:
                # If so, break out of loop
                relevant_briefs = relevant_briefs_x
                break
            # If token limit is not exceeded and maximum k value is not exceeded, 
            # increment k, set relevant_briefs and continue loop
            k += 1
            relevant_briefs = relevant_briefs_x
        
        # If the relevant_briefs list has items, then set relevant_briefs_str
        if len(relevant_briefs) > 0:
            relevant_briefs_doc = [doc.page_content for doc in relevant_briefs]
            relevant_briefs_str = "\n \n".join(relevant_briefs_doc)
        # Otherwise, set relevant_briefs_str to empty string
        else:
            relevant_briefs_str = ""

        # Set query to include the provision, outline, heading, explanation, and relevant briefs
        query = textwrap.dedent(
        f"""
        Black letter law provision: 
        {self.provision_final} 
        Outline:
        {self.outline_str}
        Component heading:
        {heading}
        Explanation:
        {self.explanation}
        Potentially relevant casebriefs:
        {relevant_briefs_str}
        """
        )
        # Set condense prompt (typically should not be necessary)
        prompt_condense = "Do not edit the black letter law provision, outline, or component heading. Condense the casebriefs."

        # Call llm_router to create comment
        logger.info("create_comment: Creating comment for heading: %s", heading)
        output, total_tokens, model, prompt_lst = llm_router(
            prompt_system,
            prompt_human,
            query,
            prompt_condense,
            self.section.llm_settings
            )
            
        return output, total_tokens, model, prompt_lst

    def create_comments(self, start_index=0):
        """Create comments for each heading in the outline.
        start_index can be specified if a previous run was interrupted.
        """
        # If starting from beginning, then clear the comments list and prompt_temp list.
        if start_index == 0:
            self.comments = []
            self.prompt_temp = []
        # Loop through outline_list to create comments
        logger.info("create_comments: Creating comments. %s headings to process.", len(self.outline_list[start_index:]))
        for heading in self.outline_list[start_index:]:
            logger.info("create_comments: Creating comment %s of %s", self.outline_list.index(heading) + 1, len(self.outline_list[start_index:]))
            # Create comment
            output, total_tokens, model, prompt_lst = self.create_comment(heading)
            # Add comment to comments list
            self.comments.append(output['text'])
            # Add prompts to temporary prompt list.
            self.prompt_temp += prompt_lst
            # Sleep for tokens
            sleep_for_tokens(total_tokens, model)

        # Join comments into a single string
        self.comments_str = "\n \n".join(self.comments)

        # Set section.comment_final to the final draft of the Comment from this method.
        self.section.comment_final = self.comments_str
        
        # Save the prompts used in this method
        self.prompt_lst.append(save_used_prompts("## Comment prompts", self.prompt_temp))
    
    def get_outputs(self):
        """Get outputs from this class.
        """
        return self.__dict__
        
    def save_attributes(self):
        """Save attributes to JSON file
        """
        filename = os.path.join(self.section.path_json, "comment.json")
        save_to_json(self, filename)
    
    def load_attributes(self):
        """Load attributes from JSON file.
        """
        filename = os.path.join(self.section.path_json, "comment.json")
        load_from_json(self, filename)

    def save_to_md(self):
        """Save prompts and outputs to markdown file.
        """
        # Save prompts to markdown file
        save_prompts_to_md(self, "comment_prompts")
        # Save outputs to markdown file
        # Set path for markdown file.
        timestamp = get_timestamp()
        name = f"comment_{timestamp}.md"
        # Open markdown file.
        with open(
            os.path.join(self.section.path_md, name),
            'w',
            encoding="utf-8"
        ) as f:
            # Write outline
            f.write("# Outline\n\n")
            f.write(self.outline_str)
            f.write("\n\n")
            # Write comments
            f.write("# Comments\n\n")
            f.write(self.comments_str)
            f.write("\n\n")

