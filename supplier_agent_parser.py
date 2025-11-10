#!/usr/bin/env python3
"""
Supplier Agent YAML Parser
==========================

Specialized parser for supplier-filter-agent.yml format that converts
your existing YAML structure into the AgentDefinition format for the 
Agent Registry System.

Handles the specific structure with:
- Agent metadata (name, description, inputs, outputs)
- Multiple policies with their own workflow steps
- Policy dependencies and enablement
- Step descriptions and execution order
"""

import yaml
import logging
from typing import Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

# Import our agent registry classes
from agent_registry_system import AgentDefinition, AgentPolicy, AgentTool, AgentWorkflowStep

logger = logging.getLogger(__name__)

class SupplierAgentParser:
    """Parser for supplier-filter-agent.yml format"""
    
    def __init__(self):
        self.tool_registry = self._initialize_tool_registry()
        
    def parse_yaml_file(self, yaml_path: str) -> AgentDefinition:
        """Parse supplier-filter-agent.yml into AgentDefinition"""
        
        with open(yaml_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
            
        return self._convert_to_agent_definition(config)
        
    def _convert_to_agent_definition(self, config: Dict[str, Any]) -> AgentDefinition:
        """Convert YAML config to AgentDefinition"""
        
        agent_config = config['agent']
        
        # Extract basic metadata
        agent_id = self._generate_agent_id(agent_config['name'])
        name = agent_config['name']
        description = agent_config['description']
        version = "1.0.0"  # Default version
        
        # Parse policies and their workflow steps
        policies = []
        all_workflow_steps = []
        
        for policy_config in agent_config.get('policies', []):
            policy, workflow_steps = self._parse_policy(policy_config, agent_id)
            policies.append(policy)
            all_workflow_steps.extend(workflow_steps)
            
        # Extract all unique tools from workflow steps
        tools = self._extract_tools_from_steps(all_workflow_steps)
        
        # Create LLM prompt template
        llm_prompt = self._generate_llm_prompt(agent_config, policies)
        
        return AgentDefinition(
            agent_id=agent_id,
            name=name,
            description=description,
            version=version,
            policies=policies,
            tools=tools,
            workflow_steps=all_workflow_steps,
            llm_prompt_template=llm_prompt,
            created_date=datetime.now()
        )
        
    def _parse_policy(self, policy_config: Dict[str, Any], agent_id: str) -> tuple[AgentPolicy, List[AgentWorkflowStep]]:
        """Parse a single policy configuration"""
        
        policy_id = f"{agent_id}_{policy_config['name'].lower().replace(' ', '_')}"
        
        # Convert policy to business rules
        rules = self._extract_policy_rules(policy_config)
        
        policy = AgentPolicy(
            policy_id=policy_id,
            name=policy_config['name'],
            description=policy_config['description'],
            rules=rules,
            priority=1,
            active=policy_config.get('enabled', True)
        )
        
        # Parse workflow steps for this policy
        workflow_steps = []
        for i, step_config in enumerate(policy_config.get('steps', [])):
            step = self._parse_workflow_step(step_config, policy_id, i)
            workflow_steps.append(step)
            
        return policy, workflow_steps
        
    def _parse_workflow_step(self, step_config: Dict[str, Any], policy_id: str, index: int) -> AgentWorkflowStep:
        """Parse a workflow step configuration"""
        
        step_name = step_config['name']
        step_id = f"{policy_id}_step_{index}_{step_name.lower().replace(' ', '_')}"
        
        # Map step to tool (using our tool registry)
        tool_name = self._map_step_to_tool(step_name)
        
        # Generate input/output mappings based on step name and description
        input_mapping, output_mapping = self._generate_step_mappings(step_name, step_config.get('description', ''))
        
        return AgentWorkflowStep(
            step_id=step_id,
            name=step_name,
            description=step_config.get('description', ''),
            tool_name=tool_name,
            input_mapping=input_mapping,
            output_mapping=output_mapping,
            conditions=[],
            required=True
        )
        
    def _extract_policy_rules(self, policy_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract business rules from policy description"""
        
        description = policy_config['description']
        rules = []
        
        # Parse natural language policy descriptions into structured rules
        if 'overall rating' in description.lower():
            rules.append({
                "condition": "supplier.overall_rating >= threshold",
                "action": "include_supplier",
                "parameters": {"threshold": 4.0}
            })
            
        if 'lead time' in description.lower():
            # Extract lead time threshold from description
            if '<= 3 days' in description:
                threshold = 3
            elif '<= 2 days' in description:
                threshold = 2
            else:
                threshold = 7
                
            rules.append({
                "condition": f"supplier.lead_time <= {threshold}",
                "action": "include_supplier",
                "parameters": {"max_lead_time_days": threshold}
            })
            
        if 'quality rating' in description.lower():
            rules.append({
                "condition": "supplier.quality_rating >= threshold",
                "action": "include_supplier", 
                "parameters": {"threshold": 4.0}
            })
            
        if 'delivery' in description.lower() or 'ontime' in description.lower():
            rules.append({
                "condition": "supplier.delivery_performance >= threshold",
                "action": "include_supplier",
                "parameters": {"threshold": 0.85}
            })
            
        if 'tie-breaker' in description.lower() and 'lowest' in description.lower():
            rules.append({
                "condition": "multiple_suppliers_qualify",
                "action": "select_lowest_cost",
                "parameters": {"sort_by": "basic_rate"}
            })
            
        return rules
        
    def _initialize_tool_registry(self) -> Dict[str, AgentTool]:
        """Initialize registry of available MCP tools"""
        
        tools = {}
        
        # Define MCP tools based on the workflow steps in your YAML
        tool_definitions = [
            {
                "tool_id": "get_purchase_request_details",
                "name": "get_purchase_request_details",
                "description": "Retrieve purchase request header and ML details using User ID/OU/Buyer",
                "parameters": {
                    "user_id": "string",
                    "ou": "string", 
                    "buyer": "string",
                    "purchase_request_id": "string"
                }
            },
            {
                "tool_id": "get_supplier_item_mapping", 
                "name": "get_supplier_item_mapping",
                "description": "Get supplier-item-variant mapping for procurement items",
                "parameters": {
                    "items": "list",
                    "ou": "string"
                }
            },
            {
                "tool_id": "get_supplier_addresses",
                "name": "get_supplier_addresses", 
                "description": "Retrieve supplier address details from supplier master",
                "parameters": {
                    "supplier_codes": "list"
                }
            },
            {
                "tool_id": "get_supplier_overall_ratings",
                "name": "get_supplier_overall_ratings",
                "description": "Get overall ratings for specified suppliers",
                "parameters": {
                    "supplier_codes": "list"
                }
            },
            {
                "tool_id": "get_supplier_lead_times",
                "name": "get_supplier_lead_times",
                "description": "Get lead times for supplier-item combinations with filtering",
                "parameters": {
                    "supplier_codes": "list",
                    "item_codes": "list",
                    "max_lead_time_days": "integer"
                }
            },
            {
                "tool_id": "get_supplier_quality_ratings",
                "name": "get_supplier_quality_ratings", 
                "description": "Get quality ratings/index for specified suppliers",
                "parameters": {
                    "supplier_codes": "list"
                }
            },
            {
                "tool_id": "get_supplier_delivery_ratings",
                "name": "get_supplier_delivery_ratings",
                "description": "Get on-time delivery performance ratings for suppliers", 
                "parameters": {
                    "supplier_codes": "list"
                }
            },
            {
                "tool_id": "get_blanket_purchase_order_details",
                "name": "get_blanket_purchase_order_details",
                "description": "Get valid blanket purchase order details for items",
                "parameters": {
                    "items": "list",
                    "ou": "string"
                }
            },
            {
                "tool_id": "llm_supplier_evaluation",
                "name": "llm_supplier_evaluation",
                "description": "LLM-powered supplier evaluation and selection",
                "parameters": {
                    "policy": "string",
                    "suppliers_data": "dict",
                    "items": "list"
                }
            },
            {
                "tool_id": "post_po_api_call",
                "name": "post_po_api_call", 
                "description": "Create purchase orders for selected suppliers",
                "parameters": {
                    "supplier_code": "string",
                    "item_code": "string",
                    "variant_code": "string", 
                    "need_date": "string",
                    "pr_line_no": "string"
                }
            },
            {
                "tool_id": "post_prs_api_call",
                "name": "post_prs_api_call",
                "description": "Create purchase requisitions for blanket orders",
                "parameters": {
                    "blpo_no": "string",
                    "blpo_line_no": "string",
                    "item_code": "string",
                    "variant_code": "string",
                    "need_date": "string",
                    "pr_line_no": "string"
                }
            },
            {
                "tool_id": "get_po_details",
                "name": "get_po_details",
                "description": "Retrieve purchase order details after creation",
                "parameters": {
                    "po_numbers": "list"
                }
            },
            {
                "tool_id": "get_prs_details", 
                "name": "get_prs_details",
                "description": "Retrieve purchase requisition details after creation",
                "parameters": {
                    "prs_numbers": "list"
                }
            },
            {
                "tool_id": "send_notifications",
                "name": "send_notifications",
                "description": "Send email notifications to stakeholders",
                "parameters": {
                    "recipients": "list",
                    "notification_type": "string",
                    "po_details": "dict",
                    "pr_details": "dict"
                }
            }
        ]
        
        for tool_def in tool_definitions:
            tool = AgentTool(
                tool_id=tool_def["tool_id"],
                name=tool_def["name"],
                description=tool_def["description"],
                parameters=tool_def["parameters"]
            )
            tools[tool.name] = tool
            
        return tools
        
    def _map_step_to_tool(self, step_name: str) -> str:
        """Map workflow step name to MCP tool name"""
        
        # Direct mapping for exact matches
        direct_mappings = {
            "get_purchase_request_details": "get_purchase_request_details",
            "get_supplier_item_mapping": "get_supplier_item_mapping", 
            "get_supplier_addresses": "get_supplier_addresses",
            "get_supplier_overall_ratings": "get_supplier_overall_ratings",
            "get_supplier_lead_times": "get_supplier_lead_times",
            "get_supplier_quality_ratings": "get_supplier_quality_ratings",
            "get_supplier_delivery_ratings": "get_supplier_delivery_ratings",
            "get_blanket_purchase_order_details": "get_blanket_purchase_order_details",
            "llm_supplier_evaluation": "llm_supplier_evaluation",
            "post_po_api_call": "post_po_api_call",
            "post_prs_api_call": "post_prs_api_call", 
            "get_po_details": "get_po_details",
            "get_prs_details": "get_prs_details",
            "send_notifications": "send_notifications"
        }
        
        return direct_mappings.get(step_name, step_name)
        
    def _extract_tools_from_steps(self, workflow_steps: List[AgentWorkflowStep]) -> List[AgentTool]:
        """Extract unique tools required by workflow steps"""
        
        tool_names = set(step.tool_name for step in workflow_steps)
        tools = []
        
        for tool_name in tool_names:
            if tool_name in self.tool_registry:
                tools.append(self.tool_registry[tool_name])
            else:
                # Create a generic tool definition
                tools.append(AgentTool(
                    tool_id=tool_name,
                    name=tool_name, 
                    description=f"MCP tool: {tool_name}",
                    parameters={"input": "any"}
                ))
                
        return tools
        
    def _generate_step_mappings(self, step_name: str, description: str) -> tuple[Dict[str, str], Dict[str, str]]:
        """Generate input/output mappings for workflow steps"""
        
        input_mapping = {}
        output_mapping = {}
        
        # Generate mappings based on step name patterns
        if "get_purchase_request_details" in step_name:
            input_mapping = {
                "user_id": "{{workitem.user_id}}",
                "ou": "{{workitem.ou}}", 
                "buyer": "{{workitem.buyer}}",
                "purchase_request_id": "{{workitem.purchase_request_id}}"
            }
            output_mapping = {
                "pr_header": "pr_header",
                "pr_ml_details": "ml_details",
                "items": "ml_details.items",
                "item_codes": "ml_details.item_codes"
            }
            
        elif "get_supplier_item_mapping" in step_name:
            input_mapping = {
                "items": "{{items}}",
                "ou": "{{workitem.ou}}"
            }
            output_mapping = {
                "supplier_item_mapping": "supplier_mapping",
                "supplier_codes": "supplier_codes"
            }
            
        elif "get_supplier_overall_ratings" in step_name:
            input_mapping = {
                "supplier_codes": "{{supplier_codes}}"
            }
            output_mapping = {
                "supplier_ratings": "overall_ratings"
            }
            
        elif "get_supplier_lead_times" in step_name:
            input_mapping = {
                "supplier_codes": "{{supplier_codes}}",
                "item_codes": "{{item_codes}}",
                "max_lead_time_days": "3"
            }
            output_mapping = {
                "supplier_lead_times": "lead_times"
            }
            
        elif "llm_supplier_evaluation" in step_name:
            input_mapping = {
                "policy": "OverallRatingLeadTimePolicy",
                "suppliers_data": "{{supplier_ratings}}",
                "items": "{{items}}"
            }
            output_mapping = {
                "selected_suppliers": "evaluation_results",
                "confidence_scores": "confidence"
            }
            
        elif "post_po_api_call" in step_name:
            input_mapping = {
                "supplier_code": "SUPP-002",
                "item_code": "ELEC-001",
                "variant_code": "V1",
                "need_date": "2025-11-15",
                "pr_line_no": "001"
            }
            output_mapping = {
                "po_numbers": "created_pos",
                "po_details": "created_pos"
            }
            
        elif "send_notifications" in step_name:
            input_mapping = {
                "recipients": "{{notification_recipients}}",
                "notification_type": "po_creation", 
                "po_details": "{{po_details}}",
                "pr_details": "{{pr_header}}"
            }
            output_mapping = {
                "notification_status": "notification_result"
            }
            
        return input_mapping, output_mapping
        
    def _generate_llm_prompt(self, agent_config: Dict[str, Any], policies: List[AgentPolicy]) -> str:
        """Generate LLM prompt template for the agent"""
        
        prompt = f"""You are a {agent_config['name']} specialized in procurement and supplier management.

{agent_config['description']}

Your responsibilities include:
- Analyzing purchase requests and requirements
- Applying business policies for supplier selection
- Evaluating suppliers based on multiple criteria (rating, lead time, quality, delivery performance)
- Making intelligent procurement decisions
- Coordinating purchase order creation and notifications

Available Business Policies:
"""
        
        for policy in policies:
            if policy.active:
                prompt += f"\n• {policy.name}: {policy.description}"
                
        prompt += """

When analyzing workitems:
1. Understand the procurement requirements and constraints
2. Apply relevant business policies based on the scenario
3. Evaluate supplier data comprehensively
4. Make confident, justified decisions
5. Provide clear reasoning for recommendations

Respond with structured JSON containing your analysis, selected suppliers, confidence scores, and detailed justification for each decision."""

        return prompt
        
    def _generate_agent_id(self, name: str) -> str:
        """Generate agent ID from name"""
        return name.lower().replace(' ', '_').replace('-', '_')

# Demonstration function
async def demo_supplier_agent_parsing():
    """Demonstrate parsing supplier-filter-agent.yml"""
    
    print("🔧 Supplier Agent YAML Parser Demo")
    print("=" * 60)
    
    try:
        # Parse the YAML file
        parser = SupplierAgentParser()
        agent_def = parser.parse_yaml_file("supplier-filter-agent.yml")
        
        print(f"✅ Successfully parsed: {agent_def.name}")
        print(f"📋 Agent ID: {agent_def.agent_id}")
        print(f"📝 Description: {agent_def.description[:100]}...")
        print(f"🔧 Version: {agent_def.version}")
        print()
        
        # Show policies
        print(f"📋 Policies ({len(agent_def.policies)}):")
        for policy in agent_def.policies:
            status = "✅ Active" if policy.active else "❌ Inactive"
            print(f"   • {policy.name} - {status}")
            print(f"     {len(policy.rules)} rules: {policy.description[:80]}...")
        print()
        
        # Show tools  
        print(f"🔧 MCP Tools ({len(agent_def.tools)}):")
        for tool in agent_def.tools:
            print(f"   • {tool.name}: {tool.description}")
        print()
        
        # Show workflow steps
        print(f"⚙️ Workflow Steps ({len(agent_def.workflow_steps)}):")
        current_policy = ""
        for step in agent_def.workflow_steps:
            # Group by policy
            policy_prefix = step.step_id.split('_step_')[0]
            if policy_prefix != current_policy:
                current_policy = policy_prefix
                policy_name = next((p.name for p in agent_def.policies if p.policy_id == policy_prefix), "Unknown")
                print(f"\n   📋 {policy_name}:")
                
            print(f"      {len(step.step_id.split('_'))-2}. {step.name}")
            print(f"         Tool: {step.tool_name}")
            if step.input_mapping:
                print(f"         Inputs: {len(step.input_mapping)} parameters")
            if step.output_mapping:
                print(f"         Outputs: {len(step.output_mapping)} results")
        
        return agent_def
        
    except Exception as e:
        print(f"❌ Failed to parse supplier-filter-agent.yml: {e}")
        raise

if __name__ == "__main__":
    import asyncio
    asyncio.run(demo_supplier_agent_parsing())