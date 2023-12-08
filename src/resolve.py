"""Resolve class for resolving points of disagreement.

This class is a subclass of `Discern`, which creates instances of this class for each point of disagreement that needs to be resolved.

### Attributes

- `briefcases`: A `Briefcases` object containing case briefs.
- `extract`: An `Extract` object containing extracted information.
- `discern`: A `Discern` object containing discerned information.
- `section`: A `Section` object containing section information.
- `issue`: A string representing the issue to be resolved.
- `rules_str`: A string representing different versions of the rule within the disagreement.
- `rules_lst`: A list of different versions of the rule within the disagreement.
- `authority_lst`: A list of authorities for each version of the rule.
- `authority_sum`: A string summarizing the authority for each version of the rule.
- `majority`: A string representing notes on the majority rule and trends.
- `reasoning`: A string representing notes on the reasoning behind the rules from caselaw.
- `fit`: A string representing notes on the rule that fits within the body of law, produces the best outcomes, and aligns with the purpose of Restatements of Law.
- `decide`: A string representing notes on the decision.
- `new_rule`: A string representing the new rule based on the decision.
- `prompt_lst`: A list of prompts.
- `prompt_str`: A string of prompts.

### Methods

- `get_rules(self)`: Creates a legal rule for each side of the disagreement.
- `get_authority(self)`: Gets the legal authority for each rule in `self.rules_lst`.
- `set_authority_sum(self)`: Sets a summary of authority information collected in the `get_authority` method.
- `get_majority(self)`: Creates notes on the majority rule and trends.
- `get_reasoning(self)`: Gets the reasoning behind the rules from caselaw.
- `get_fit(self)`: Creates notes on the rule that fits within the body of law, produces the best outcomes, and aligns with the purpose of Restatements of Law.
- `get_decide(self)`: Decides on the best rule based on the information gathered so far.
- `write_rule(self)`: Writes the rule for this particular disagreement based on the decision made in the `get_decide` method.
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
    list_to_token_list,
    num_tokens,
    sleep_for_tokens,
    string_to_token_list,
    llm_call,
    llm_loop,
    llm_loop_gpt4,
    llm_condense_string,
    llm_router,
    llm_router_gpt4,
    trim_part_for_tokens
)

from src.utils_string import (
    set_prompt,
    replace_prompt_variables,
    set_full_prompt,
    get_timestamp,
    save_used_prompts
)

# Set up logger
logger = logging.getLogger('restatement')

class Resolve:
    """Class for resolving points of disagreement.
    This is a subclass of Discern, which creates instances of this class for each point of 
    disagreement that needs to be resolved.
    """

    def __init__(
        self,
        briefcases,
        extract,
        discern,
        section,
        issue
        ):

        self.briefcases = briefcases
        self.extract = extract
        self.discern = discern
        self.section = section
        self.issue = issue

        # Different versions of the rule within the disagreement
        self.rules_str = ""
        self.rules_lst = []

        # Authority for each version of the rule
        self.authority_lst = []
        # Summary of authority
        self.authority_sum = ""

        # Notes on majority rule and trends
        self.majority = ""
        # Notes on the reasoning behind the rules from caselaw
        self.reasoning = ""
        # Notes on rule that fits within body of law, produces best outcomes, and aligns 
        # with purpose of Restatements of Law
        self.fit = ""
        # Notes on decision
        self.decide = ""
        # New rule based on decision
        self.new_rule = ""

        # List of prompts
        self.prompt_lst = []
        # String of prompts
        self.prompt_str = ""
    
    def get_rules(self):
        """Create legal rule for each side of disagreement.
        """
        # Set prompts for LLM.
        # Set system prompt with contents from txt file
        prompt_system = set_full_prompt(
            os.path.join(get_root_dir(), "data", "prompts", 'resolve', "prompt_rules.txt"),
            self.section
        )
        prompt_human = textwrap.dedent(
        """
        Your notes:
        {query}
        """)
        query = self.issue
        # Set condense prompt
        prompt_condense = textwrap.dedent(
            """
            Condense this text but do not alter the meaning: 
            
            {query}
            """
        )

        # Call on LLM to decide what points of disagreement to include in the final rule.
        logger.info("get_rules: Creating legal rule for each side of disagreement.")
        output, total_tokens, model, prompt_lst = llm_router_gpt4(
            prompt_system,
            prompt_human,
            query,
            prompt_condense,
            self.section.llm_settings
        )

        # Save output to self.rules_lst
        self.rules_str = output['text']
        self.rules_lst = output['text'].split('***')

        # Save the prompts used in this method
        self.prompt_lst.append(save_used_prompts("## Rules prompts", prompt_lst))

        # Sleep for tokens
        sleep_for_tokens(total_tokens, model)

    def get_authority(self):
        """Get legal authority for each rule in self.rules_lst.
        """
        self.authority_lst = []
        # Each item in list is a list with the following structure:
        # [0] Rule
        # [1] Legal authority for that rule as string
        # [2] Legal authority for that rule as list
        # [3] Number of cases (calculated by measuring the length of [2])
        # [4] Casebriefs of legal authority for that rule as list
        # [5] Reasoning behind the rule from casebriefs as string
        self.authority_lst = [[rule, '', [], 0, [], ""] for rule in self.rules_lst]
        
        for rule in self.authority_lst:
            rule[1] = ""
            # Get rules from self.rules_lst as a string, except for current rule.
            other_rules = self.rules_lst.copy()
            other_rules.remove(rule[0])
            other_rules = '\n'.join(other_rules)

            # Set prompts for LLM.
            # Set system prompt with contents from txt file
            prompt_system = set_full_prompt(
            os.path.join(get_root_dir(), "data", "prompts", 'resolve', "prompt_authority.txt"),
            self.section
        )
            # Set human prompt amd query. Note that {query} is required for LLMChain to work.        
            prompt_human = textwrap.dedent(
            f"""
            This version of legal rule: 
            {rule[0]}
            
            Other versions of legal rule:
            {other_rules}
            """)
            prompt_human += textwrap.dedent(
            """
            Your notes:
            {query}
            """)
            # Set condense prompt
            prompt_condense = textwrap.dedent(
                """
                Condense this text but do not alter the meaning.
                """
            )

            # Call on LLM to loop through copy_token_list to get legal authority for each rule.
            logger.info("get_authority: Calling on LLM to get legal authority for each rule.")
            output_list, prompt_lst = llm_loop(
                prompt_system,
                prompt_human,
                self.extract.copy_token_list,
                prompt_condense,
                self.section.llm_settings
            )

            # Turn the list into one string.
            rule[1] = '\n'.join(output_list)
            # Split the string into a list of lines.
            rule[2] = rule[1].split('\n')
            # Get the number of cases.
            rule[3] = len(rule[2])

            # Save the prompts used in this method
            self.prompt_lst.append(save_used_prompts("## Authority prompts", prompt_lst))

    def set_authority_sum(self):
        """Set summary of authority information collected in get_authority method.
        """
        self.authority_sum = ""
        for authority in self.authority_lst:
            string = textwrap.dedent(
            f"""
            Provision: 
            {authority[0]}
            Cases supporting provision:
            {authority[1]}
            Number of cases:
            {authority[3]}
            """
            )
            self.authority_sum += string
        
        # If summary exceeds token limits, remove list of cases supporting each provision.
        if num_tokens(self.authority_sum) > self.section.llm_settings.max_tokens:
            self.authority_sum = ""
            for authority in self.authority_lst:
                string = textwrap.dedent(
                f"""
                Provision: 
                {authority[0]}
                Number of cases supporting provision:
                {authority[3]}
                """
                )
                self.authority_sum += string
    
    def get_majority(self):
        """Create notes on majority rule and trends.
        """
        # Set prompts for LLM.
        # Set system prompt with contents from txt file
        prompt_system = set_full_prompt(
            os.path.join(get_root_dir(), "data", "prompts", 'resolve', "prompt_majority.txt"),
            self.section
        )
        prompt_human = textwrap.dedent(
        """
        Your notes:
        {query}
        """)
        query = self.authority_sum
        # Set condense prompt
        prompt_condense = textwrap.dedent(
            """
            Condense this text but do not alter the meaning: 
           
            {query}
            """
        )

        # Call on LLM to create notes on majority rule and trends.
        logger.info("get_majority: Creating notes on majority rule and trends.")
        output, total_tokens, model, prompt_lst = llm_router(
            prompt_system,
            prompt_human,
            query,
            prompt_condense,
            self.section.llm_settings
        )

        # Save output
        self.majority = output['text']

        # Save the prompts used in this method
        self.prompt_lst.append(save_used_prompts("## Majority prompts", prompt_lst))

        # Sleep for tokens
        sleep_for_tokens(total_tokens, model)

    def get_reasoning(self):
        """Get reasoning behind the rules from caselaw.
        """
        # For each rule, get available reasoning from casebriefs.
        for rule in self.authority_lst:
            # Retrieve relevant briefs
            # Loop through each case in the list of cases supporting the rule.
            for case in rule[2]:
                case_name = f"Case Name {case}"
                # Retrieve relevant casebrief
                relevant_brief = self.briefcases.briefs_db.similarity_search(case_name, k=1)
                # Convert relevant_brief to a list of strings
                relevant_brief = [doc.page_content for doc in relevant_brief]
                # Join the list of strings into one string
                relevant_brief = '\n'.join(relevant_brief)
                # Add relevant casebrief to rule[4]
                rule[4].append(relevant_brief)
            # Create token list of casebriefs
            briefs_token_list = list_to_token_list(
                rule[4],
                self.section.llm_settings.chunk_size_long,
                self.section.llm_settings.chunk_overlap
            )
            # Set prompts for LLM.
            # Set system prompt with contents from txt file
            prompt_system = set_full_prompt(
                os.path.join(get_root_dir(), "data", "prompts", 'resolve', "prompt_reasoning.txt"),
                self.section
            )
            prompt_human = textwrap.dedent(
            f"""
            Legal rule: 
            {rule[0]}
            
            """)
            prompt_human += textwrap.dedent(
            """
            Your notes:
            {query}
            """)
            # Set condense prompt
            prompt_condense = textwrap.dedent(
                """
                Condense this text but do not alter the meaning.
                """
            )
            # Call on LLM to loop through briefs_token_list to get reasoning behind the rules from caselaw.
            logger.info("get_reasoning: Getting reasoning behind rule from caselaw.")
            output_list, prompt_lst = llm_loop(
                prompt_system,
                prompt_human,
                briefs_token_list,
                prompt_condense,
                self.section.llm_settings
            )
            
            # Turn the list into one string.
            rule[5] = '\n'.join(output_list)

        # Create string of reasoning behind the rules from caselaw.
        self.reasoning = ""
        for rule in self.authority_lst:
            string = textwrap.dedent(
            f"""
            Rule: 
            {rule[0]}

            Reasoning behind rule from legal cases:
            {rule[5]}
            """
            )
            self.reasoning += string
        # Save the prompts used in this method
        self.prompt_lst.append(save_used_prompts("## Reasoning prompts", prompt_lst))

    def get_fit(self):
        """Create notes on rule that fits within body of law, produces best outcomes, and aligns
        with purpose of Restatements of Law.
        """
        # Set prompts for LLM.
        # Set system prompt with contents from txt file
        prompt_system = set_full_prompt(
            os.path.join(get_root_dir(), "data", "prompts", 'resolve', "prompt_fit.txt"),
            self.section
        )

        prompt_human = textwrap.dedent(
        """
        
        Your notes:
        {query}
        """)
        query = textwrap.dedent(
        f"""
        Settled part of legal rule:
        {self.discern.consensus_rule}
        Point of disagreement:
        {self.issue}
        Potential additions to rule:
        {self.reasoning}
        """
        )
        # Set condense prompt
        prompt_condense = textwrap.dedent(
            """
            Condense this text but do not alter the meaning.
            """
        )

        # Call on LLM to create notes on rule that fits within body of law, produces best outcomes,
        # and aligns with purpose of Restatements of Law.
        logger.info("get_fit: Creating notes on rule that fits within body of law, produces best outcomes, and aligns with purpose of Restatements of Law.")
        output, total_tokens, model, prompt_lst = llm_router(
            prompt_system,
            prompt_human,
            query,
            prompt_condense,
            self.section.llm_settings
        )

        # Save output
        self.fit = output['text']

        # Save the prompts used in this method
        self.prompt_lst.append(save_used_prompts("## Fit prompts", prompt_lst))

        # Sleep for tokens
        sleep_for_tokens(total_tokens, model)

    def get_decide(self):
        """Decide on best rule.
        """
        # Set prompts for LLM.
        # Set system prompt with contents from txt file
        prompt_system = set_full_prompt(
            os.path.join(get_root_dir(), "data", "prompts", 'resolve', "prompt_decide.txt"),
            self.section
        )

        prompt_human = textwrap.dedent(
        """
        Your notes:
        {query}
        """)
        query = textwrap.dedent(
        f"""
        Settled part of legal rule:
        {self.discern.consensus_rule}
        Point of disagreement:
        {self.issue}
        Potential additions to rule:
        {self.reasoning}
        Majority & Trends:
        {self.majority}
        Fit:
        {self.fit}
        """
        )
        # Set condense prompt
        prompt_condense = textwrap.dedent(
            """
            Condense this text but do not alter the meaning.
            """
        )

        # Call on LLM to decide on best rule.
        logger.info("get_decide: Deciding on best rule.")
        output, total_tokens, model, prompt_lst = llm_router(
            prompt_system,
            prompt_human,
            query,
            prompt_condense,
            self.section.llm_settings
        )

        # Save output
        self.decide = output['text']

        # Save the prompts used in this method
        self.prompt_lst.append(save_used_prompts("## Decide prompts", prompt_lst))

        # Sleep for tokens
        sleep_for_tokens(total_tokens, model)

    def write_rule(self):
        """Write the rule for this particular disagreement.
        """
        # Set prompts for LLM.
        # Set system prompt with contents from txt file
        prompt_system = set_full_prompt(
            os.path.join(get_root_dir(), "data", "prompts", 'resolve', "prompt_write.txt"),
            self.section
        )
        prompt_human = textwrap.dedent(
        """
        Your notes:
        {query}
        """)
        query = textwrap.dedent(
        f"""
        Settled part of legal rule:
        {self.discern.consensus_rule}
        Point of disagreement:
        {self.issue}
        Potential addition to rule:
        {self.rules_str}
        Notes contemplating best addition to adopt:
        {self.decide}
        """
        )
        # Set condense prompt
        prompt_condense = textwrap.dedent(
            """
            Condense this text but do not alter the meaning.
            """
        )
        
        # System prompt may be too long for LLM. Trim it if necessary.
        logger.debug("Token length of system prompt: %s", num_tokens(prompt_system))
        remainder = prompt_human + query
        prompt_system = trim_part_for_tokens(
            prompt_system,
            remainder,
            self.section.llm_settings.max_tokens,
            self.section.llm_settings.max_tokens_long / 2
        )

        # Call on LLM to write rule.
        logger.info("write_rule: Writing rule.")
        output, total_tokens, model, prompt_lst = llm_router(
            prompt_system,
            prompt_human,
            query,
            prompt_condense,
            self.section.llm_settings
        )

        # Save output
        self.new_rule = output['text']

        # Save the prompts used in this method
        self.prompt_lst.append(save_used_prompts("## Revise prompts", prompt_lst))

        # Sleep for tokens
        sleep_for_tokens(total_tokens, model)

    def get_outputs(self):
        """Get outputs from this class.
        """
        return self.__dict__
        
    def save_attributes(self):
        """Save attributes to JSON file
        """
        filename = os.path.join(self.section.path_json, "resolve.json")
        save_to_json(self, filename)
    
    def load_attributes(self):
        """Load attributes from JSON file.
        """
        filename = os.path.join(self.section.path_json, "resolve.json")
        load_from_json(self, filename)

    def save_to_md(self):
        """Save prompts and outputs to markdown file.
        """
        # Save prompts to markdown file
        save_prompts_to_md(self, "resolve_prompts")
        # Save outputs to markdown file
        # Set path for markdown file.
        timestamp = get_timestamp()
        name = f"resolve_{timestamp}.md"
        # Open markdown file.
        with open(
            os.path.join(self.section.path_md, name),
            'w',
            encoding="utf-8"
        ) as f:
            # Write Rules
            f.write("# Rules\n\n")
            f.write(f"{self.rules_str}\n\n")
            # Write Authority
            f.write("# Authority\n\n")
            f.write(f"{self.authority_sum}\n\n")
            # Write Majority & Trends
            f.write("# Majority & Trends\n\n")
            f.write(f"{self.majority}\n\n")
            # Write Reasoning
            f.write("# Reasoning\n\n")
            f.write(f"{self.reasoning}\n\n")
            # Write Fit
            f.write("# Fit\n\n")
            f.write(f"{self.fit}\n\n")
            # Write Decide
            f.write("# Decide \n\n")
            f.write("*Notes on decision* \n\n")
            f.write(f"{self.decide}\n\n")
            # Write Revise
            f.write("# New Rule \n\n")
            f.write("*New rule based on decision* \n\n")
            f.write(f"{self.new_rule}\n\n")
