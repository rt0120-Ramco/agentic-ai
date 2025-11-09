"""
Tool Chain Orchestrator - LLM-Driven Dynamic Tool Chaining
==========================================================

This module provides a generic, scalable tool chaining system that:
1. Uses LLM to determine which tools to call and in what sequence
2. Handles dynamic input/output mapping between tools
3. Supports iteration when APIs return multiple values
4. Works with any number of tools without hardcoding

The system is completely LLM-driven and requires no manual configuration
for new tool chains.
"""

import asyncio
import json
import html
import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from openai import AsyncAzureOpenAI

logger = logging.getLogger(__name__)

@dataclass
class ToolChainStep:
    """Represents a single step in a tool chain"""
    tool_name: str
    input_params: Dict[str, Any]
    iteration_source: Optional[str] = None  # If this step should iterate over results from previous step
    output_mapping: Optional[Dict[str, str]] = None  # How to map outputs for next step


@dataclass
class ToolChainResult:
    """Result of executing a tool chain"""
    success: bool
    steps_executed: List[Dict[str, Any]]
    final_result: Any
    error_message: Optional[str] = None


class DomainFlowValidator:
    """
    Validates and optimizes tool chains based on business domain knowledge.
    Ensures chains follow logical business flows.
    """
    
    # Business flow patterns
    DOMAIN_FLOWS = {
        "purchase_flow": ["PR", "PO", "GR", "Movement", "Invoice", "Payment"]
    }
    
    # Tool to domain mapping
    TOOL_DOMAIN_MAP = {
        "view_purchase_request": "PR",
        "search_purchase_orders": "PR_to_PO",
        "view_purchase_order": "PO", 
        "help_on_receipt_document": "PO_to_GR",
        "view_receipt_document": "GR",
        "view_movement_details": "Movement",
        "view_inspection_details": "Inspection",
        "view_subcontract_request": "SCR"
    }
    
    def validate_chain(self, tool_chain: List[ToolChainStep]) -> Tuple[bool, str, List[ToolChainStep]]:
        """
        Validate and optimize a tool chain based on domain flows.
        
        Returns:
            (is_valid, message, optimized_chain)
        """
        if not tool_chain:
            return False, "Empty tool chain", []
        
        # Check for logical flow
        domain_sequence = [self.TOOL_DOMAIN_MAP.get(step.tool_name, step.tool_name) for step in tool_chain]
        
        # Validate business logic
        validation_result = self._validate_business_logic(domain_sequence)
        if not validation_result[0]:
            return validation_result[0], validation_result[1], tool_chain
        
        # Optimize chain if possible
        optimized_chain = self._optimize_chain(tool_chain)
        
        return True, "Chain validated and optimized", optimized_chain
    
    def _validate_business_logic(self, domain_sequence: List[str]) -> Tuple[bool, str]:
        """Validate the domain sequence follows business logic"""
        
        # Check for invalid reverse flows
        invalid_patterns = [
            ["GR", "PO"],  # Can't go from GR back to PO
            ["Invoice", "GR"],  # Can't go from Invoice back to GR
            ["Payment", "Invoice"]  # Can't go from Payment back to Invoice
        ]
        
        for i in range(len(domain_sequence) - 1):
            current_domain = domain_sequence[i]
            next_domain = domain_sequence[i + 1]
            
            if [current_domain, next_domain] in invalid_patterns:
                return False, f"Invalid business flow: {current_domain} → {next_domain}"
        
        return True, "Valid business flow"
    
    def _optimize_chain(self, tool_chain: List[ToolChainStep]) -> List[ToolChainStep]:
        """Optimize the tool chain by removing redundant steps"""
        
        # Remove redundant consecutive calls to same tool
        optimized = []
        prev_tool = None
        
        for step in tool_chain:
            if step.tool_name != prev_tool:
                optimized.append(step)
                prev_tool = step.tool_name
        
        return optimized


class ToolChainOrchestrator:
    """
    LLM-driven tool chain orchestrator that dynamically determines
    which tools to call and how to chain them based on user queries.
    """
    def _find_key_paths(self, data, target_key, current_path=""):
        """Recursively find all dot notation paths to a given key in nested dict/list."""
        paths = []
        if isinstance(data, dict):
            for k, v in data.items():
                new_path = f"{current_path}.{k}" if current_path else k
                if k == target_key:
                    paths.append(new_path)
                paths.extend(self._find_key_paths(v, target_key, new_path))
        elif isinstance(data, list):
            for item in data:
                paths.extend(self._find_key_paths(item, target_key, current_path))
        return paths

    def __init__(self, azure_openai_client: AsyncAzureOpenAI, tool_registry: Dict[str, Any]):
        self.azure_client = azure_openai_client
        self.tool_registry = tool_registry
        self.deployment_name = "gpt-4o-ramcoerp"
        self.domain_validator = DomainFlowValidator()

    def _normalize_param(self, tool_name: str, param_name: str, value: Any) -> Any:
        """
        Unescape all JSON escape characters for string parameters if known escape sequences are present.
        Apply additional normalization (e.g., upper) if specified.
        Always URL-encode string parameters for safe API usage.
        """
        import urllib.parse
        orig_value = value
        if isinstance(value, str):
            # Only decode and URL-encode if value contains explicit JSON escape sequences
            escape_seqs = ["\\n", "\\t", "\\r", "\\u", "\\\\"]
            if any(seq in value for seq in escape_seqs):
                try:
                    decoded_value = bytes(value, "utf-8").decode("unicode_escape")
                    logger.debug(f"[NORMALIZE] {tool_name}.{param_name}: Decoded escape sequences: '{orig_value}' → '{decoded_value}'")
                except Exception:
                    logger.debug(f"[NORMALIZE] {tool_name}.{param_name}: Failed to decode escape sequences: '{orig_value}'")
                    decoded_value = orig_value
                encoded_value = urllib.parse.quote(decoded_value, safe='')
                logger.debug(f"[NORMALIZE] {tool_name}.{param_name}: URL-encoded: '{decoded_value}' → '{encoded_value}'")
                value = encoded_value
            else:
                # If value contains a backslash and no escape sequences, always pass as-is
                if "\\" in value:
                    logger.debug(f"[NORMALIZE] {tool_name}.{param_name}: Contains backslash, passing as-is: '{value}'")
                    value = value
                else:
                    # No JSON escape characters or backslash, pass as-is
                    logger.debug(f"[NORMALIZE] {tool_name}.{param_name}: No JSON escape chars or backslash, passing as-is: '{value}'")
                    value = value
        tool_config = self.tool_registry.get(tool_name, {})
        api_config = tool_config.get("api_config", {})
        normalization = api_config.get("parameter_normalization", {})
        rule = normalization.get(param_name)
        if rule and isinstance(value, str):
            if rule == "upper":
                norm_value = value.upper()
                logger.debug(f"[NORMALIZE] {tool_name}.{param_name}: '{value}' → '{norm_value}' (upper)")
                return norm_value
            # Add more normalization rules here as needed
        return value

    async def analyze_user_query_for_tool_chain(self, user_query: str) -> List[ToolChainStep]:
        """
        Use LLM to analyze user query and determine the tool chain needed.
        Returns a list of ToolChainStep objects representing the sequence.
        """
        
        # Create tool descriptions for LLM
        tool_descriptions = self._create_tool_descriptions()
        
        # Create the prompt for LLM to determine tool chain
        prompt = self._create_tool_chain_prompt(user_query, tool_descriptions)
        logger.info(f"[LLM PROMPT] Prompt being sent to LLM:\n{prompt}")
        
        try:
            response = await self.azure_client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are an expert at analyzing user queries to determine the optimal sequence of API calls. Always respond with valid JSON. Consider business domain flows: PR → PO → GR → Movement → Invoice → Payment."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=2000
            )
            
            # Parse LLM response
            response_text = response.choices[0].message.content.strip()
            logger.info(f"LLM tool chain response: {response_text}")
            
            # Extract JSON from response
            chain_config = self._extract_json_from_response(response_text)
            
            logger.info(f"Raw tool chain config from LLM:\n{json.dumps(chain_config, indent=2)}")

            # Convert to ToolChainStep objects
            tool_chain = self._create_tool_chain_from_config(chain_config, user_query)
            
            # Validate and optimize using domain knowledge
            is_valid, validation_message, optimized_chain = self.domain_validator.validate_chain(tool_chain)
            
            if is_valid:
                logger.info(f"Generated and validated tool chain: {[step.tool_name for step in optimized_chain]}")
                logger.info(f"Validation: {validation_message}")
                return optimized_chain
            else:
                logger.warning(f"Tool chain validation failed: {validation_message}")
                logger.info(f"Using original chain: {[step.tool_name for step in tool_chain]}")
                return tool_chain
            
        except Exception as e:
            logger.error(f"Error analyzing user query for tool chain: {e}")
            return []
    
    def _create_tool_descriptions(self) -> str:
        """Create a formatted description of all available tools for the LLM"""
        descriptions = []
        for tool_name, tool_config in self.tool_registry.items():
            tool = tool_config.get("tool")
            if tool:
                descriptions.append(f"- {tool.name}: {tool.description}")
        return "\n".join(descriptions)

    def _extract_json_from_response(self, response_text: str) -> Dict[str, Any]:
        """Extract JSON from LLM response, handling markdown code blocks"""
        try:
            # Try direct JSON parse first
            return json.loads(response_text)
        except json.JSONDecodeError:
            # Try extracting from markdown code block
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            
            # Try extracting JSON object from text
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            
            raise ValueError(f"Could not extract valid JSON from response: {response_text}")
    
    def _create_tool_chain_from_config(self, chain_config: Dict[str, Any], user_query: str) -> List[ToolChainStep]:
        """
        Convert LLM config response to ToolChainStep objects.
        LLM only binds input_params for the first tool. For subsequent tools, orchestrator uses schema-driven mapping ONLY.
        """
        logger.debug(f"[DEBUG][ToolChainFromConfig] ENTRY: Processing chain_config with {len(chain_config.get('tool_chain', []))} tools")
        tool_chain = []
        tool_list = chain_config.get("tool_chain", [])
        
        for idx, step_config in enumerate(tool_list):
            tool_name = step_config.get("tool_name")
            logger.debug(f"[DEBUG][ToolChainFromConfig] Processing step {idx+1}: {tool_name}")
            
            if idx == 0:
                input_params = step_config.get("input_params", {})
                logger.debug(f"[DEBUG][ToolChainFromConfig] Step {idx+1} FIRST TOOL - using LLM input_params: {input_params}")
            else:
                # IGNORE LLM's input_params for non-first tools, use schema-driven mapping ONLY
                llm_input_params = step_config.get('input_params', {})
                logger.debug(f"[DEBUG][ToolChainFromConfig] Step {idx+1} NON-FIRST TOOL '{tool_name}' - IGNORING LLM input_params: {llm_input_params}")
                
                tool_schema = self.tool_registry.get(tool_name, {})
                logger.debug(f"[DEBUG][ToolChainFromConfig] tool_schema keys: {list(tool_schema.keys()) if tool_schema else 'None'}")
                
                input_schema = tool_schema.get("tool", {}).inputSchema if tool_schema.get("tool") else {}
                logger.debug(f"[DEBUG][ToolChainFromConfig] input_schema has properties: {bool(input_schema and 'properties' in input_schema)}")
                
                # Use all inputSchema properties, not just required
                all_params = set()
                if input_schema and "properties" in input_schema:
                    all_params = set(input_schema["properties"].keys())
                
                logger.debug(f"[DEBUG][ToolChainFromConfig] Step {idx+1} '{tool_name}' all_params: {all_params}")
                input_params = {}

                for param in all_params:
                    logger.debug(f"[DEBUG][ToolChainMapping] Processing param '{param}' for tool '{tool_name}'")
                    # Only include param if a mapping is found in previous steps' output_to_input_hints
                    found_mapping = False
                    for prev_idx in range(idx-1, -1, -1):
                        prev_tool = tool_list[prev_idx]["tool_name"]
                        prev_schema = self.tool_registry.get(prev_tool, {})
                        prev_api_config = prev_schema.get("api_config", {})
                        prev_hints = prev_api_config.get("output_to_input_hints", {})
                        logger.debug(f"[DEBUG][ToolChainMapping] Checking prev_tool '{prev_tool}' hints: {prev_hints}")
                        
                        if isinstance(prev_hints, dict):
                            for output_field, mappings in prev_hints.items():
                                logger.debug(f"[DEBUG][ToolChainMapping] Checking output_field '{output_field}' mappings: {mappings}")
                                if isinstance(mappings, list):
                                    for mapping in mappings:
                                        if (
                                            isinstance(mapping, dict)
                                            and mapping.get("tool") == tool_name
                                            and mapping.get("param") == param
                                        ):
                                            input_params[param] = f"<{output_field}>"
                                            logger.debug(f"[DEBUG][ToolChainMapping] FOUND MAPPING: {param} -> <{output_field}>")
                                            found_mapping = True
                                            break
                                    if found_mapping:
                                        break
                                elif isinstance(mappings, dict):
                                    if param in mappings:
                                        input_params[param] = f"<{output_field}>"
                                        logger.debug(f"[DEBUG][ToolChainMapping] FOUND MAPPING (dict): {param} -> <{output_field}>")
                                        found_mapping = True
                                        break
                            if found_mapping:
                                break
                        if found_mapping:
                            break
                    
                    if not found_mapping:
                        logger.debug(f"[DEBUG][ToolChainMapping] NO MAPPING FOUND for param '{param}' in tool '{tool_name}'")
                
                logger.debug(f"[DEBUG][ToolChainFromConfig] Step {idx+1} '{tool_name}' FINAL input_params: {input_params}")

            output_mapping = step_config.get("output_mapping", {})
            step = ToolChainStep(
                tool_name=tool_name,
                input_params=input_params,
                iteration_source=None,  # Iteration handled generically in execute_tool_chain
                output_mapping=output_mapping
            )
            tool_chain.append(step)
            logger.debug(f"[DEBUG][ToolChainFromConfig] Added step {idx+1}: {tool_name} with params {input_params}")
        
        logger.debug(f"[DEBUG][ToolChainFromConfig] EXIT: Created {len(tool_chain)} tool chain steps")
        return tool_chain

    async def execute_tool_chain(self, tool_chain: List[ToolChainStep], tool_executor_func) -> ToolChainResult:
        """Execute a tool chain by calling each step in sequence."""
        steps_executed = []
        context = {}  # Store results from previous steps

        def _extract_values_by_path(data, path):
            """
            Extract values from nested dict/list using dot-separated path.
            If the direct path yields no result, also search recursively for the last key segment anywhere in the structure.
            """
            keys = path.split('.')
            results = []

            def recurse(d, keys):
                if not keys:
                    return [d]
                key = keys[0]
                rest = keys[1:]
                if isinstance(d, dict):
                    if key in d:
                        return recurse(d[key], rest)
                elif isinstance(d, list):
                    res = []
                    for item in d:
                        res.extend(recurse(item, keys))
                    return res
                return []

            # Try direct path first
            results = recurse(data, keys)
            if results:
                return results

            # If not found, search for any occurrence of the last key segment
            last_key = keys[-1]
            def find_all_by_key(obj, target):
                found = []
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if k == target:
                            found.append(v)
                        found.extend(find_all_by_key(v, target))
                elif isinstance(obj, list):
                    for item in obj:
                        found.extend(find_all_by_key(item, target))
                return found

            fallback_results = find_all_by_key(data, last_key)
            return fallback_results

        try:
            for i, step in enumerate(tool_chain):
                logger.info(f"Executing step {i+1}: {step.tool_name}")

                # Debug log: context before each step execution
                logger.debug(f"[ToolChain] Context before executing {step.tool_name}: {json.dumps(context, indent=2)}")

                # Prepare input parameters
                input_params = self._resolve_input_parameters(step, context)
                logger.debug(f"[DEBUG] Resolved input_params for {step.tool_name}: {input_params}")

                # Robust iteration and substitution: always resolve input params from latest context
                iter_keys = [k for k, v in input_params.items() if isinstance(v, list)]
                if iter_keys:
                    iteration_results = []
                    iter_key = iter_keys[0]
                    iter_values = input_params[iter_key]
                    for iter_value in iter_values:
                        # For each iteration, resolve all input params from latest context
                        iteration_params = {}
                        # Identify all keys whose value is the same list as the iterated key
                        for k, v in input_params.items():
                            if (isinstance(v, list) and v is iter_values) or k == iter_key:
                                # Set all such params to the current value
                                if isinstance(iter_value, list) and len(iter_value) == 1:
                                    iteration_params[k] = iter_value[0]
                                else:
                                    iteration_params[k] = iter_value
                            elif isinstance(v, list):
                                # For other lists, use the first element (or blank if empty)
                                if len(v) > 0:
                                    iteration_params[k] = v[0]
                                else:
                                    iteration_params[k] = ""
                            elif isinstance(v, str) and v.startswith('<') and v.endswith('>'):
                                field_name = v[1:-1]
                                resolved = self._resolve_field_from_context(field_name, context)
                                if isinstance(resolved, list):
                                    iteration_params[k] = resolved[0] if resolved else ""
                                else:
                                    iteration_params[k] = resolved if resolved is not None else v
                            else:
                                iteration_params[k] = v
                        # If the parameter is still a list, but the tool expects a string, take the first element
                        if isinstance(iteration_params[iter_key], list):
                            if len(iteration_params[iter_key]) == 1:
                                iteration_params[iter_key] = iteration_params[iter_key][0]
                            else:
                                logger.warning(f"[DEBUG] Skipping value for {iter_key} because it is a list: {iteration_params[iter_key]}")
                                continue
                        # Prevent blank document numbers
                        if not iteration_params[iter_key]:
                            logger.warning(f"[DEBUG] Skipping blank value for {iter_key}")
                            continue
                        try:
                            result = await tool_executor_func(step.tool_name, iteration_params)
                            if result and (not isinstance(result, dict) or not result.get('error')):
                                iteration_results.append({"input": iteration_params, "result": result})
                            else:
                                logger.warning(f"[DEBUG] No receipt details for {iter_key}={iter_value}")
                                # Still append the result (even if empty or error) to show all attempts
                                iteration_results.append({"input": iteration_params, "result": result})
                        except Exception as e:
                            logger.warning(f"[DEBUG] Error for {iter_key}={iter_value}: {e}")
                            # Append error info for this iteration, but do not abort the chain
                            iteration_results.append({"input": iteration_params, "error": str(e)})
                    step_result = iteration_results
                else:
                    # For non-iterated steps, resolve all input params from latest context
                    resolved_params = {}
                    for k, v in input_params.items():
                        if isinstance(v, str) and v.startswith('<') and v.endswith('>'):
                            field_name = v[1:-1]
                            resolved = self._resolve_field_from_context(field_name, context)
                            resolved_params[k] = resolved if resolved is not None else v
                        else:
                            resolved_params[k] = v
                    step_result = await tool_executor_func(step.tool_name, resolved_params)
                    logger.debug(f"Raw tool response for '{step.tool_name}': {json.dumps(step_result, indent=2, ensure_ascii=False)}")

                # Store result in context
                logger.debug(f"[DEBUG] Tool '{step.tool_name}' raw result: {json.dumps(step_result, indent=2, ensure_ascii=False)}")
                if step.output_mapping:
                    for output_key, context_key in step.output_mapping.items():
                        context_key = html.unescape(context_key)
                        values = _extract_values_by_path(step_result, output_key)
                        logger.debug(f"[DEBUG] Extracting output for context: tool={step.tool_name}, output_key={output_key}, context_key={context_key}, values={values}")
                        if not values:
                            # Generic fallback: search for any matching key in the response
                            possible_paths = self._find_key_paths(step_result, output_key.split('.')[-1])
                            logger.debug(f"[DEBUG] Fallback search for output_key '{output_key}' in result. Possible paths: {possible_paths}")
                            for path in possible_paths:
                                values = _extract_values_by_path(step_result, path)
                                logger.debug(f"[DEBUG] Fallback extraction for path '{path}': {values}")
                                if values:
                                    logger.debug(f"[DEBUG] Fallback extraction: found values for {context_key} at {path}: {values}")
                                    break
                        # If only one value, store as scalar, else as list
                        if values:
                            context[context_key] = values[0] if len(values) == 1 else values
                            logger.debug(f"[DEBUG] Stored in context: {context_key} = {context[context_key]}")
                        else:
                            logger.warning(f"[DEBUG] Could not extract '{output_key}' from step result for tool '{step.tool_name}'. Full result: {json.dumps(step_result, indent=2, ensure_ascii=False)}")
                    logger.debug(f"[DEBUG] Context after extraction for tool {step.tool_name}: {json.dumps(context, indent=2)}")
                    # Additional debug: after search_purchase_orders, show PO numbers in context
                    # if step.tool_name == 'search_purchase_orders':
                    #     logger.info(f"[DEBUG][search_purchase_orders] PO numbers in context: {context}")
                else:
                    context[step.tool_name] = step_result
                logger.debug(f"[DEBUG] Context after step '{step.tool_name}': {json.dumps(context, indent=2, ensure_ascii=False)}")
                # Additional debug: before help_on_receipt_document, show resolved document numbers
                if step.tool_name == 'help_on_receipt_document':
                    logger.info(f"[DEBUG][help_on_receipt_document] Input params: {steps_executed[-1]['input_params'] if steps_executed else {}} | Context: {context}")

                steps_executed.append({
                    "step": i + 1,
                    "tool_name": step.tool_name,
                    "input_params": input_params,
                    "result": step_result
                })

            return ToolChainResult(
                success=True,
                steps_executed=steps_executed,
                final_result=context
            )
        except Exception as e:
            logger.error(f"Error executing tool chain: {e}")
            return ToolChainResult(
                success=False,
                steps_executed=steps_executed,
                final_result=None,
                error_message=str(e)
            )
    
    def _resolve_input_parameters(self, step: ToolChainStep, context: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve input parameters using explicit mappings from LLM output or schema hints, with normalization"""
        resolved_params = {}
        import logging
        logger.debug(f"[DEBUG][ResolveInputParams] Resolving input_params for tool '{step.tool_name}': {step.input_params}")
        resolved_params = {}
        for key, value in step.input_params.items():
            if isinstance(value, str):
                if value == "<output_from_previous>":
                    resolved_value = self._resolve_schema_driven_value(step.tool_name, key, context)
                elif value.startswith("<") and value.endswith(">"):
                    field_name = value[1:-1]
                    resolved_value = self._resolve_field_from_context(field_name, context)
                    logging.debug(f"[DEBUG][_resolve_input_parameters] key={key} placeholder={value} resolved_value={resolved_value} type={type(resolved_value)}")
                    # If the resolved value is a list:
                    if isinstance(resolved_value, list):
                        if len(resolved_value) == 1:
                            # Only one value, treat as scalar
                            resolved_params[key] = self._normalize_param(step.tool_name, key, resolved_value[0])
                        elif len(resolved_value) > 1:
                            # Multiple values, assign list for iteration
                            resolved_params[key] = resolved_value
                        else:
                            # Empty list, assign as-is
                            resolved_params[key] = resolved_value
                        continue
                    # If the resolved value is not None, assign it
                    elif resolved_value is not None:
                        resolved_params[key] = self._normalize_param(step.tool_name, key, resolved_value)
                        continue
                    else:
                        resolved_value = value
                else:
                    resolved_value = value
            else:
                resolved_value = value
            # Only normalize if not a list
            if isinstance(resolved_value, list):
                if len(resolved_value) == 1:
                    resolved_params[key] = self._normalize_param(step.tool_name, key, resolved_value[0])
                else:
                    resolved_params[key] = resolved_value
            else:
                resolved_params[key] = self._normalize_param(step.tool_name, key, resolved_value)
            logging.debug(f"[DEBUG][_resolve_input_parameters] FINAL key={key} resolved_params[key]={resolved_params[key]} type={type(resolved_params[key])}")
        logger.debug(f"[DEBUG][ResolveInputParams] Final resolved_params for tool '{step.tool_name}': {resolved_params}")
        return resolved_params
    
    def _resolve_schema_driven_value(self, tool_name: str, param_name: str, context: Dict[str, Any]) -> Any:
        """
        Resolve parameter value using schema-driven logic instead of pattern matching.
        Uses output_to_input_hints from tool configuration.
        """
        # Get tool configuration
        tool_config = self.tool_registry.get(tool_name, {})
        api_config = tool_config.get("api_config", {})

        # Direct match
        if param_name in context:
            return context[param_name]

        # Search inside list of dicts
        for context_key, context_value in context.items():
            if isinstance(context_value, list):
                for item in context_value:
                    if isinstance(item, dict) and param_name in item:
                        return item[param_name]

        # Use output_to_input_hints to find appropriate mapping
        hints = api_config.get("output_to_input_hints", {})
        for output_field, target_mappings in hints.items():
            for mapping in target_mappings:
                if mapping.get("tool") == tool_name and mapping.get("param") == param_name:
                    # Try to resolve from context using output_field
                    if output_field in context:
                        value = context[output_field]
                        if isinstance(value, list):
                            return value[0] if value else None
                        return value

        # Fallback to first available value (last resort)
        for value in context.values():
            if isinstance(value, list) and value:
                if isinstance(value[0], dict) and param_name in value[0]:
                    return value[0][param_name]
            elif isinstance(value, dict) and param_name in value:
                return value[param_name]

    def _resolve_field_from_context(self, field_name: str, context: Dict[str, Any]) -> Any:
        """
        Recursively resolve a specific field name from context.
        Fully generic: searches all nested dicts/lists, no tool-specific logic, no pattern matching, no fallback.
        """
        def normalize(s):
            return s.lower().replace('_', '').replace('-', '').replace(' ', '')
        
        norm_field = normalize(field_name)
        norm_bracketed = normalize(f'<{field_name}>')
        
        logger.debug(f"[DEBUG][ResolveField] Resolving field '{field_name}' (normalized: '{norm_field}') from context")
        logger.debug(f"[DEBUG][ResolveField] Context keys: {list(context.keys())}")
        
        def recursive_normalized_search(obj, target1, target2, path=""):
            logger.debug(f"[DEBUG][ResolveField] Searching at path '{path}' for targets '{target1}' or '{target2}'")
            if isinstance(obj, dict):
                for k, v in obj.items():
                    nk = normalize(k)
                    current_path = f"{path}.{k}" if path else k
                    logger.debug(f"[DEBUG][ResolveField] Checking key '{k}' (normalized: '{nk}') at path '{current_path}'")
                    if nk == target1 or nk == target2:
                        logger.debug(f"[DEBUG][ResolveField] FOUND MATCH: key '{k}' matches target, value: {v}")
                        return v[0] if isinstance(v, list) and v else v
                    result = recursive_normalized_search(v, target1, target2, current_path)
                    if result is not None:
                        logger.debug(f"[DEBUG][ResolveField] FOUND RECURSIVELY at path '{current_path}': {result}")
                        return result
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    current_path = f"{path}[{i}]" if path else f"[{i}]"
                    result = recursive_normalized_search(item, target1, target2, current_path)
                    if result is not None:
                        logger.debug(f"[DEBUG][ResolveField] FOUND IN LIST at path '{current_path}': {result}")
                        return result
            return None
        
        # First check top-level context keys
        for k, v in context.items():
            nk = normalize(k)
            logger.debug(f"[DEBUG][ResolveField] Top-level check: '{k}' (normalized: '{nk}') vs targets '{norm_field}' or '{norm_bracketed}'")
            if nk == norm_field or nk == norm_bracketed:
                logger.debug(f"[DEBUG][ResolveField] TOP-LEVEL MATCH: key '{k}' matches, value: {v}")
                # Return the full list if it's a list, not just the first value
                return v
        
        # Then do recursive search
        result = recursive_normalized_search(context, norm_field, norm_bracketed)
        if result is not None:
            logger.debug(f"[DEBUG][ResolveField] RECURSIVE MATCH found: {result}")
            return result
        
        logger.warning(f"[GENERIC RESOLVE] Could not resolve field '{field_name}' from context (keys: {list(context.keys())})")
        return ""

class ToolChainManager:
    """
    High-level manager for tool chaining operations.
    Integrates with existing MCP server architecture.
    """
    
    def __init__(self, azure_openai_client: AsyncAzureOpenAI, tool_registry: Dict[str, Any]):
        self.orchestrator = ToolChainOrchestrator(azure_openai_client, tool_registry)
    
    async def process_user_query_with_chaining(self, user_query: str, tool_executor_func) -> Dict[str, Any]:
        """
        Main entry point for processing user queries with tool chaining.
        
        This method centralizes ALL LLM decision-making logic:
        - Decides whether query needs chaining or single tool
        - Determines appropriate tool(s) to call
        - Handles parameter extraction and mapping
        - Executes single tool calls or complex chains
        - Returns clarification prompts when needed
        
        Args:
            user_query: Natural language query from user
            tool_executor_func: Function to execute individual tools
            
        Returns:
            Dict containing the complete execution result
        """
        
        logger.info(f"Processing user query with centralized LLM logic: {user_query}")
        
        try:
            # Step 1: LLM analyzes query to determine execution strategy
            execution_strategy = await self._analyze_query_execution_strategy(user_query)
            
            if execution_strategy["strategy"] == "clarification":
                return {
                    "success": True,
                    "type": "clarification",
                    "user_query": user_query,
                    "clarification": execution_strategy["message"],
                    "suggestions": execution_strategy.get("suggestions", [])
                }
            
            elif execution_strategy["strategy"] == "single_tool":
                # Single tool execution
                tool_name = execution_strategy["tool_name"]
                parameters = execution_strategy["parameters"]
                
                logger.info(f"Executing single tool: {tool_name}")
                result = await tool_executor_func(tool_name, parameters)
                
                # Create steps_executed for single tool (for dashboard logging)
                steps_executed = [{
                    "step": 1,
                    "tool_name": tool_name,
                    "input_params": parameters,
                    "result": result
                }]
                
                return {
                    "success": True,
                    "type": "single_tool",
                    "user_query": user_query,
                    "tool_name": tool_name,
                    "tool_chain": [tool_name],  # Add for consistency
                    "parameters": parameters,
                    "result": result,
                    "steps_executed": steps_executed,
                    "final_result": result,
                    "llm_reasoning": execution_strategy.get("reasoning", "")
                }
            
            elif execution_strategy["strategy"] == "tool_chain":
                # Tool chain execution
                tool_chain = execution_strategy["tool_chain"]
                
                logger.info(f"Executing tool chain: {[step.tool_name for step in tool_chain]}")
                result = await self.orchestrator.execute_tool_chain(tool_chain, tool_executor_func)
                
                return {
                    "success": result.success,
                    "type": "tool_chain",
                    "user_query": user_query,
                    "tool_chain": [step.tool_name for step in tool_chain],
                    "steps_executed": result.steps_executed,
                    "final_result": result.final_result,
                    "error": result.error_message,
                    "llm_reasoning": execution_strategy.get("reasoning", "")
                }
            
            else:
                return {
                    "success": False,
                    "error": f"Unknown execution strategy: {execution_strategy['strategy']}",
                    "user_query": user_query
                }
        
        except Exception as e:
            logger.error(f"Error in centralized query processing: {e}")
            return {
                "success": False,
                "error": str(e),
                "user_query": user_query
            }
    
    async def _analyze_query_execution_strategy(self, user_query: str) -> Dict[str, Any]:
        """
        Centralized LLM analysis to determine execution strategy.
        
        Returns:
            Dict with strategy ("single_tool", "tool_chain", "clarification")
            and associated parameters/tool chain/clarification message
        """
        
        # Create tool descriptions for LLM
        tool_descriptions = self.orchestrator._create_tool_descriptions()
        
        # Create analysis prompt
#         prompt = f"""
# Analyze this user query and determine the optimal execution strategy:

# USER QUERY: "{user_query}"

# AVAILABLE TOOLS:
# {tool_descriptions}

# EXECUTION STRATEGIES:
# 1. "single_tool" - Query can be answered with one tool call
# 2. "tool_chain" - Query requires multiple connected tool calls  
# 3. "clarification" - Query is unclear and needs user clarification

# BUSINESS FLOWS:
# - PR → PO → GR → Movement → Invoice → Payment
# - Direct document lookups when specific numbers provided

# ANALYSIS INSTRUCTIONS:
# 1. If query contains specific document numbers (PO123, PR456, GR789), prefer single tool
# 2. If query asks for "flow" or "trace" or "all related", use tool chain
# 3. If query is vague or ambiguous, request clarification
# 4. Use schema output_to_input_hints to determine chaining possibilities

# OUTPUT FORMAT:
# {{
#   "strategy": "single_tool|tool_chain|clarification",
#   "reasoning": "Brief explanation of decision",
#   "tool_name": "tool_name_if_single",
#   "parameters": {{"param": "value"}},
#   "tool_chain": [
#     {{
#       "tool_name": "tool1",
#       "input_params": {{"param": "value"}},
#       "output_mapping": {{"output": "context_key"}}
#     }}
#   ],
#   "message": "clarification_message_if_needed",
#   "suggestions": ["suggestion1", "suggestion2"]
# }}

# EXAMPLES:
# - "View PO JSLTEST46" → single_tool (view_purchase_order)
# - "Show complete flow for PR123" → tool_chain (search_purchase_orders → help_on_receipt_document → ...)
# - "Show me something" → clarification (too vague)
# """
        # Create schema-driven chaining rules
        try:
            from .mcp_tools_schema_enhanced import get_mcp_tools_with_api_config
        except ImportError:
            from mcp_tools_schema_enhanced import get_mcp_tools_with_api_config
        
        tools_with_config = get_mcp_tools_with_api_config()
        
        # Get document flow and chaining rules from schema
        document_flow = {}
        chaining_rules = []
        for item in tools_with_config:
            if item["tool"].name == "natural_language_query":  # This contains the metadata
                continue
            api_config = item.get("api_config", {})
            if "document_flow" in api_config:
                document_flow = api_config["document_flow"]
                chaining_rules = document_flow.get("chaining_rules", [])
                break
        
        # Generate output_to_input_hints section from schema
        hints_section = []
        for item in tools_with_config:
            tool_name = item["tool"].name
            api_config = item.get("api_config", {})
            output_hints = api_config.get("output_to_input_hints", {})
            if output_hints:
                hints_section.append(f"\n{tool_name} outputs:")
                for output_field, mappings in output_hints.items():
                    if isinstance(mappings, list):
                        for mapping in mappings:
                            if isinstance(mapping, dict):
                                target_tool = mapping.get("tool", "")
                                target_param = mapping.get("param", "")
                                hints_section.append(f"  {output_field} → {target_tool}.{target_param}")
        
        schema_hints = "\n".join(hints_section)
        schema_chaining_rules = "\n".join([f"- {rule}" for rule in chaining_rules])
        
        # Create analysis prompt - NO HARDCODED EXAMPLES
        prompt = f"""
Analyze this user query and determine the optimal execution strategy:
USER QUERY: "{user_query}"

AVAILABLE TOOLS:
{tool_descriptions}

EXECUTION STRATEGIES:
1. "single_tool" – Query can be answered with one tool call
2. "tool_chain" – Query requires multiple connected tool calls
3. "clarification" – Query is unclear and needs user clarification

SCHEMA-DRIVEN CHAINING RULES:
{schema_chaining_rules}

SCHEMA OUTPUT-TO-INPUT MAPPINGS:
{schema_hints}

ANALYSIS RULES:
- If query contains "movement" and mentions "PO" or "Purchase Order" → ALWAYS use tool_chain
- If query contains "movement" and mentions "PR" or "Purchase Request" → ALWAYS use tool_chain  
- If query asks for "movement", "trace", "flow", or "all related" → ALWAYS use tool_chain
- If query asks for movement/trace from PO → use tool_chain: PO → GR → Movement
- If query asks for movement/trace from PR → use tool_chain: PO → GR → Movement  
- Pattern "movement details for PO [number]" → ALWAYS tool_chain, never single_tool
- Pattern "movement details for PR [number]" → ALWAYS tool_chain, never single_tool
- If query is for simple document view (no movement/trace/flow) → single_tool
- Use ONLY the output_to_input_hints from schema above to determine valid tool chains
- Chain tools by following the schema mappings: Tool1 output_field → Tool2 input_param
- Use exact output field names as placeholders: <ExactOutputFieldName>

PARAMETER EXTRACTION:
- Extract ALL relevant parameters from the user query for each tool
- For document numbers: Extract exact values mentioned (PO numbers, PR numbers, etc.)
- For parameters: Use the tool schema to identify required parameters
- Always provide complete parameter sets for first tool in chain
- Use generic field extraction - do not hardcode specific formats

PARAMETER MAPPING RULES:
- If query mentions "PO" followed by identifier → extract as "po_number" parameter
- If query mentions "PR" followed by identifier → extract as "pr_number" parameter  
- If query mentions "GR" followed by identifier → extract as "gr_number" parameter
- Extract document identifiers exactly as mentioned in user query
- Include ALL parameters required by the first tool in the chain
- For tool_chain strategy: ALWAYS provide input_params for the first tool

EXAMPLE EXTRACTIONS:
- "show movement details for PR PRC/0903/2015" → pr_number: "PRC/0903/2015"
- "movement for PO 12345" → po_number: "12345"  
- "trace GR ABC123" → gr_number: "ABC123"

OUTPUT FORMAT:
{{
  "strategy": "single_tool | tool_chain | clarification",
  "reasoning": "Brief explanation of decision",
  "tool_name": "tool_name_if_single",
  "parameters": {{"param": "value"}},
  "tool_chain": [
    {{
      "tool_name": "tool1",
      "input_params": {{"param": "value"}},
      "output_mapping": {{"output_field": "<OutputFieldName>"}}
    }}
  ],
  "message": "clarification_message_if_needed",
  "suggestions": ["suggestion1", "suggestion2"]
}}

CRITICAL:
- NO hardcoded examples or patterns
- Use ONLY schema output_to_input_hints shown above
- Placeholders must match exact output field names: <ExactOutputFieldName>
- Do NOT use generic placeholders like <context_key> or <po_details>
- ALWAYS extract parameters from user query for the first tool in any chain
- Ensure all required parameters are provided for each tool
- For tool_chain strategy: The first tool MUST have complete input_params from user query
- NEVER leave input_params empty for the first tool in a chain
- Extract document numbers exactly as they appear in the user query
"""
        
        try:
            response = await self.orchestrator.azure_client.chat.completions.create(
                model=self.orchestrator.deployment_name,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are an expert at analyzing user queries to determine optimal execution strategies. Always respond with valid JSON."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=2000
            )
            
            # Parse LLM response
            response_text = response.choices[0].message.content.strip()
            logger.info(f"LLM execution strategy response: {response_text}")
            
            # Extract JSON from response
            strategy_config = self.orchestrator._extract_json_from_response(response_text)
            
            # Convert tool chain to ToolChainStep objects if present
            if strategy_config.get("strategy") == "tool_chain" and "tool_chain" in strategy_config:
                # Use the schema-driven mapping from _create_tool_chain_from_config instead of direct creation
                logger.debug(f"[DEBUG][AnalyzeStrategy] Using schema-driven mapping for tool_chain")
                tool_chain_steps = self.orchestrator._create_tool_chain_from_config(strategy_config, user_query)
                strategy_config["tool_chain"] = tool_chain_steps
            
            return strategy_config
            
        except Exception as e:
            logger.error(f"Error analyzing query execution strategy: {e}")
            # Fallback to clarification
            return {
                "strategy": "clarification",
                "message": f"I couldn't analyze your query properly. Could you please rephrase it? Error: {str(e)}",
                "suggestions": ["Try using specific document numbers", "Be more specific about what you want to see"]
            }