"""Discern class for discerning the best black letter law provision based on disagreements from caselaw.

## Attributes

- `extract`: An instance of the `Extract` class, which contains the groups of rules from which the consensus, disagreements, and unique rules will be extracted.
- `section`: The section of the law that the cases and briefs belong to.
- `consensus`: The consensus rule extracted from the groups.
- `disagreement`: The points of disagreement extracted from the groups.
- `unique`: The unique rules or exceptions extracted from the groups.
- `groups_sum`: A summary of information from the groups variables.
- `consensus_rule`: The discerned consensus rule.
- `disagreement_lst`: The list of points of disagreement to include in the final rule.
- `resolve_outputs`: The list of resolved outputs for each disagreement.
- `resolve_rule`: The rewritten rule following the resolve process.
- `clear`: Notes on clarifying the rule.
- `final`: The revised, final rule.
- `explanation`: Explanation of the rule, which is passed to the `Comment` class as notes for determining what comments to write.
- `prompt_lst`: A list of prompts used to generate the rules and groups.
- `prompt_str`: A string of prompts used to generate the rules and groups.

## Methods

- `__init__(self, extract, section)`: Initializes the `Discern` class with an instance of the `Extract` class and a section.
- `get_consensus(self)`: Discerns the consensus rule based on description of consensus produced by `Extract` class.
- `get_disagreement(self)`: Decides what points of disagreement to include in the final rule based on notes about disagreement produced by `Group` class instance.
- `resolve(self)`: Resolves each point of disagreement by creating instances of `Resolve` class for each point of disagreement.
- `get_resolve_rule(self)`: Creates a rewritten rule following the resolve process. It uses the LLMChain to generate the rewritten rule and saves it to `self.resolve_rule`.
- `get_clear(self)`: Creates notes on how the rule could be made more clear and logical. It uses the LLMChain to generate the notes and saves them to `self.clear`.
- `get_edit(self)`: Creates a revised, final rule based on notes on how the rule could be made more clear and logical. It uses the LLMChain to generate the final rule and saves it to `self.final`.
- `set_explanation(self)`: Sets the explanation of the rule, which is a string passed to the `Comment` class as notes for determining what comments to write.
- `get_outputs(self)`: Returns the outputs from this class.
- `save_attributes(self)`: Saves the attributes to a JSON file.
- `load_attributes(self)`: Loads the attributes from a JSON file.
- `save_to_md(self)`: Saves the prompts and outputs to a markdown file.
"""

import logging
import textwrap
import os

from src.utils_file import (
    get_root_dir,
    save_to_json,
    load_from_json,
    save_prompts_to_md
)
from src.utils_llm import (
    num_tokens,
    sleep_for_tokens,
    string_to_token_list,
    llm_call,
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
from src.resolve import Resolve

# Set up logger
logger = logging.getLogger('restatement')
    
class Discern:
    """Class for discerning the best black letter law provision.
    This class uses an output from Extract class organized by Consensus, Points of 
    disagreement, and unique rules or exceptions.
    This class writes the consensus rule, decides what points of disagreement to include, uses the
    Resolve class to resolve each point of disagreement, combines the consensus rule with the resolved
    rules, creates notes on how the rule could be made more clear and logical, and creates a revised, final rule.
    """

    def __init__(
        self,
        extract,
        section
        ):

        self.extract = extract
        self.section = section

        # Consensus
        self.consensus = self.extract.groups_list[0]
        # Points of disagreement
        self.disagreement = self.extract.groups_list[1]
        # Unique rules or exceptions
        self.unique = self.extract.groups_list[2]

        # Summary of information from groups variables
        self.groups_sum = ""

        # Consensus rule
        self.consensus_rule = ""

        # Points of disagreement to include
        self.disagreement_lst = []

        # List of resolve outputs for each disagreement
        self.resolve_outputs = []

        # Rewritten rule following resolve process
        self.resolve_rule = ""

        # Notes on clarifying rule
        self.clear = ""

        # Revised, final rule
        self.final = ""

        # Explanation of rule
        # String is passed to Comment class as notes for determining what comments to write.
        self.explanation = ""

        # List and string of prompts
        self.prompt_lst = []
        self.prompt_str = ""

    def get_consensus(self):
        """Discern the consensus rule based on description of consensus produced by Extract class.
        """
        # Set prompts for LLM.
        # Set system prompt with contents from from txt file
        prompt_system = set_full_prompt(
            os.path.join(get_root_dir(), "data", "prompts", 'discern', "prompt_consensus.txt"),
            self.section
        )
        # Set human prompt amd query. Note that {query} is required for LLMChain to work.
        prompt_human = textwrap.dedent(
        """
        Your notes:
        {query}
        """)
        query = self.consensus
        # Set condense prompt
        prompt_condense = "Condense this text but do not alter the meaning."

        # Call on LLM to discern the consensus rule.
        logger.info("get_consensus: Getting consensus rule.")
        output, total_tokens, model, prompt_lst = llm_router(
            prompt_system,
            prompt_human,
            query,
            prompt_condense,
            self.section.llm_settings
        )
        
        # Save output to self.consensus_rule
        self.consensus_rule = output['text']
        
        # Save the prompts used in this method
        self.prompt_lst.append(save_used_prompts("## Consensus prompts", prompt_lst))

        # Sleep for tokens
        sleep_for_tokens(total_tokens, model)

    def get_disagreement(self):
        """Decide what points of disagreement to include in the final rule based on notes about 
        disagreement produced by Group class instance.
        """
        # Set prompts for LLM.
        # Set system prompt with contents from txt file
        prompt_system = set_full_prompt(
            os.path.join(get_root_dir(), "data", "prompts", 'discern', "prompt_disagree.txt"),
            self.section
        )
        # Set human prompt amd query. Note that {query} is required for LLMChain to work.
        prompt_human = textwrap.dedent(
        """
        Your notes:
        {query}
        """)
        query = textwrap.dedent(
        f"""
        Consensus rule:
        {self.consensus_rule}
        Points of disagreement:
        {self.disagreement}
        """
        )
        # Set condense prompt
        prompt_condense = "Condense this text but do not alter the meaning."
        
        # System prompt may be too long for LLM to handle. Trim it if necessary.
        logger.debug("Token length of system prompt: %s", num_tokens(prompt_system))
        remainder = prompt_human + query
        prompt_system = trim_part_for_tokens(
            prompt_system,
            remainder,
            self.section.llm_settings.max_tokens,
            self.section.llm_settings.max_tokens_long / 2
        )

        # Call on LLM to decide what points of disagreement to include in the final rule.
        logger.info("get_disagreement: Getting points of disagreement to address in final rule.")
        output, total_tokens, model, prompt_lst = llm_router(
            prompt_system,
            prompt_human,
            query,
            prompt_condense,
            self.section.llm_settings
        )
       
        # Save output to self.disagreement_lst
        self.disagreement_lst = output['text'].split('####')
        # Remove any strings that are too short to be a disagreement
        # This may occur if the output includes blank lines or headings.
        self.disagreement_lst = [item for item in self.disagreement_lst if len(item) >= 100]
      
        # Save the prompts used in this method
        self.prompt_lst.append(save_used_prompts("## Disagreement prompts", prompt_lst))

        # Sleep for tokens
        sleep_for_tokens(total_tokens, model)

    def resolve(self):
        """Resolve each point of disagreement.
        Do this by creating instances of Resolve class for each point of disagreement.
        """
        logger.info("Resolving points of disagreement.")
        logger.info("Number of points of disagreement: %s", len(self.disagreement_lst))
        issue_tally = 1
        self.resolve_outputs = ""
        for issue in self.disagreement_lst:
            logger.info("Resolving issue %s", issue_tally)
            resolve = Resolve(
                briefcases=self.section.briefcases,
                extract=self.extract,
                discern=self,
                section=self.section,
                issue=issue
                )
            resolve.get_rules()
            resolve.get_authority()
            resolve.set_authority_sum()
            resolve.get_majority()
            resolve.get_reasoning()
            resolve.get_fit()
            resolve.get_decide()
            resolve.write_rule()
            resolve.save_to_md()
            self.resolve_outputs += f"{resolve.new_rule} \n \n"
            issue_tally += 1

    def get_resolve_rule(self):
        """Create a rewritten rule following the resolve process.
        """
        # Set prompts for LLM.
        # Set system prompt with contents from txt file
        prompt_system = set_full_prompt(
            os.path.join(get_root_dir(), "data", "prompts", 'discern', "prompt_resolve.txt"),
            self.section
        )

        # Set human prompt amd query. Note that {query} is required for LLMChain to work.
        prompt_human = textwrap.dedent(
        """
        Your notes:
        {query}
        """)
        query = textwrap.dedent(
        f"""
        Consensus rule:
        {self.consensus_rule}
        Other rules:
        {self.resolve_outputs}
        """)

        # Set condense prompt
        prompt_condense = "Condense this text but do not alter the meaning."

        # Call on LLMChain to create a rewritten rule following the resolve process.
        logger.info("get_resolve_rule: Getting rewritten rule following the resolve process.")
        output, total_tokens, model, prompt_lst = llm_router(
            prompt_system,
            prompt_human,
            query,
            prompt_condense,
            self.section.llm_settings
        )
        
        # Save output to self.resolve_rule
        self.resolve_rule = output['text']
        
        # Save the prompts used in this method
        self.prompt_lst.append(save_used_prompts("## Resolve prompts", prompt_lst))

        # Sleep for tokens
        sleep_for_tokens(total_tokens, model)

    def get_clear(self):
        """Create notes on how the rule could be made more clear and logical.
        """
        # Set prompts for LLM.
        # Set system prompt with contents from txt file
        prompt_system = set_full_prompt(
            os.path.join(get_root_dir(), "data", "prompts", 'discern', "prompt_clear.txt"),
            self.section
        )
        # Set human prompt amd query. Note that {query} is required for LLMChain to work.
        prompt_human = textwrap.dedent(
        """
        Your notes:
        {query}
        """)
        query = self.resolve_rule
        # Set condense prompt
        prompt_condense = "Condense this text but do not alter the meaning."

        # Call on LLMChain to create notes on how the rule could be made more clear and logical.
        logger.info("get_clear: Getting notes on how the rule could be made more clear and logical.")
        output, total_tokens, model, prompt_lst = llm_router(
            prompt_system,
            prompt_human,
            query,
            prompt_condense,
            self.section.llm_settings
        )
        
        # Save output to self.clear
        self.clear = output['text']
        
        # Save the prompts used in this method
        self.prompt_lst.append(save_used_prompts("## Clear prompts", prompt_lst))

        # Sleep for tokens
        sleep_for_tokens(total_tokens, model)

    def get_edit(self):
        """Create a revised, final rule based on notes on how the rule could be made more clear and logical.
        """
        # Set prompts for LLM.
        # Set system prompt with contents from txt file
        prompt_system = set_full_prompt(
            os.path.join(get_root_dir(), "data", "prompts", 'discern', "prompt_edit.txt"),
            self.section
        )
        # Set human prompt. Note that {query} is required for LLMChain to work.
        prompt_human = textwrap.dedent(
        """
        Your notes:
        {query}
        """)
        # Set query to self.resolve_rule and self.clear (used within human prompt in this method)
        query = textwrap.dedent(
        f"""
        Draft rule:
        {self.resolve_rule}
        
        Notes on potential improvements:
        {self.clear}
        """
        )
        # Set a condense prompt
        prompt_condense = """Condense the "Notes" but do not make any changes to the Draft rule.
        """

        # Call on LLMChain to create a revised, final rule.
        logger.info("get_edit: Getting revised, final rule.")
        output, total_tokens, model, prompt_lst = llm_router_gpt4(
            prompt_system,
            prompt_human,
            query,
            prompt_condense,
            self.section.llm_settings
        )
        
        # Set output to self.final
        self.final = output['text']

        # Set section.provision_final to the final draft of the black-letter law provision.
        self.section.provision_final = self.final

        # Save the prompts used in this method
        self.prompt_lst.append(save_used_prompts("## Edit prompts", prompt_lst))

        # Sleep for tokens
        sleep_for_tokens(total_tokens, model)
        
    def set_explanation(self):
        """Set explanation of rule.
        self.explanation is a string passed to Comment class as notes for determining what 
        comments to write.
        """
        self.explanation = textwrap.dedent(
        f"""

        {self.consensus_rule}

        {self.disagreement}
        """
        )
        # Set section.explanation to self.explanation to pass to Comment class.
        self.section.explanation = self.explanation

    def get_outputs(self):
        """Get outputs from this class.
        """
        return self.__dict__
        
    def save_attributes(self):
        """Save attributes to JSON file
        """
        filename = os.path.join(self.section.path_json, "discern.json")
        save_to_json(self, filename)
    
    def load_attributes(self):
        """Load attributes from JSON file.
        """
        filename = os.path.join(self.section.path_json, "discern.json")
        load_from_json(self, filename)

    def save_to_md(self):
        """Save prompts and outputs to markdown file.
        """
        # Save prompts to markdown file
        save_prompts_to_md(self, "discern_prompts")
        # Save outputs to markdown file
        # Set path for markdown file.
        timestamp = get_timestamp()
        name = f"discern_{timestamp}.md"
        # Open markdown file.
        with open(
            os.path.join(self.section.path_md, name),
            'w',
            encoding="utf-8"
        ) as f:
            # Write consensus rule
            f.write("# Consensus rule\n\n")
            f.write(self.consensus_rule)
            f.write("\n\n")
            # Write points of disagreement
            f.write("# Points of disagreement\n\n")
            f.write('\n'.join(self.disagreement_lst))
            f.write("\n\n")
            # Write resolve outputs for each disagreement
            f.write("# Resolve outputs\n\n")
            f.write(self.resolve_outputs)
            f.write("\n\n")
            # Write rewritten rule following resolve process
            f.write("# Resolve rule\n")
            f.write("*Rewritten rule following resolve process.* \n\n")
            f.write(self.resolve_rule)
            f.write("\n\n")
            # Write notes on how the rule could be made more clear and logical
            f.write("# Clear\n")
            f.write("*Notes on how the rule could be made more clear and logical.* \n\n")
            f.write(self.clear)
            f.write("\n\n")
            # Write revised, final rule
            f.write("# Final\n")
            f.write("*Revised, final rule.* \n\n")
            f.write(self.final)
            f.write("\n\n")
            # Write explanation of rule
            f.write("# Explanation\n")
            f.write("*Explanation of rule to be used when writing comments.* \n\n")
            f.write(self.explanation)
