#!/usr/bin/env python3
"""
Agent Registry & Onboarding System
==================================

A comprehensive system for onboarding and managing specialized agents with their own:
- Business policies and rules
- MCP tool registrations  
- Execution workflows
- LLM-powered decision making

Key Features:
- Dynamic agent registration from YAML/JSON configs
- Policy-aware agent orchestration
- MCP tool pool management per agent
- Workflow execution with LLM intelligence
"""

import asyncio
import json
import logging
import yaml
from typing import Any, Dict, List, Optional, Callable, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
import uuid
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import OpenAI
try:
    from openai import AsyncAzureOpenAI
    OPENAI_AVAILABLE = True
    logger.info("✅ OpenAI package available for agent orchestration")
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("⚠️ OpenAI package not available - using simulation mode")

@dataclass
class AgentPolicy:
    """Represents a business policy for an agent"""
    policy_id: str
    name: str
    description: str
    rules: List[Dict[str, Any]]
    priority: int = 1
    active: bool = True

@dataclass
class AgentTool:
    """Represents an MCP tool available to an agent"""
    tool_id: str
    name: str
    description: str
    parameters: Dict[str, Any]
    endpoint: Optional[str] = None
    handler_class: Optional[str] = None

@dataclass
class AgentWorkflowStep:
    """Represents a step in agent workflow execution"""
    step_id: str
    name: str
    description: str
    tool_name: str
    input_mapping: Dict[str, str] = field(default_factory=dict)
    output_mapping: Dict[str, str] = field(default_factory=dict)
    conditions: List[str] = field(default_factory=list)
    required: bool = True

@dataclass
class AgentDefinition:
    """Complete definition of a specialized agent"""
    agent_id: str
    name: str
    description: str
    version: str
    policies: List[AgentPolicy]
    tools: List[AgentTool]
    workflow_steps: List[AgentWorkflowStep]
    llm_prompt_template: str
    created_date: Optional[datetime] = None
    
class AgentRegistry:
    """Registry for managing multiple specialized agents"""
    
    def __init__(self):
        self.agents: Dict[str, AgentDefinition] = {}
        self.active_agents: Dict[str, 'SpecializedAgent'] = {}
        self.openai_client = None
        self._initialize_openai_client()
        
    def _initialize_openai_client(self):
        """Initialize Azure OpenAI client"""
        if not OPENAI_AVAILABLE:
            logger.info("🔄 OpenAI not available - agents will use simulation mode")
            return
            
        api_key = os.getenv("OPENAI_API_KEY")
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        
        if not api_key or not endpoint:
            logger.info("🔄 Azure OpenAI credentials not provided - using simulation mode")
            return
            
        try:
            self.openai_client = AsyncAzureOpenAI(
                api_key=api_key,
                azure_endpoint=endpoint,
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
            )
            logger.info("🤖 Azure OpenAI client initialized for agent registry")
        except Exception as e:
            logger.warning(f"⚠️ Failed to initialize Azure OpenAI client: {e}")
            self.openai_client = None
    
    async def register_agent_from_yaml(self, yaml_path: str) -> str:
        """Register a new agent from YAML configuration"""
        
        try:
            with open(yaml_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
                
            agent_def = self._parse_agent_config(config)
            
            # Register agent definition
            self.agents[agent_def.agent_id] = agent_def
            
            # Create active agent instance
            active_agent = SpecializedAgent(agent_def, self.openai_client)
            await active_agent.initialize()
            self.active_agents[agent_def.agent_id] = active_agent
            
            logger.info(f"✅ Registered agent: {agent_def.name} (ID: {agent_def.agent_id})")
            return agent_def.agent_id
            
        except Exception as e:
            logger.error(f"❌ Failed to register agent from {yaml_path}: {e}")
            raise
    
    def _parse_agent_config(self, config: Dict[str, Any]) -> AgentDefinition:
        """Parse YAML config into AgentDefinition"""
        
        # Parse policies
        policies = []
        for policy_config in config.get('policies', []):
            policy = AgentPolicy(
                policy_id=policy_config['policy_id'],
                name=policy_config['name'],
                description=policy_config['description'],
                rules=policy_config['rules'],
                priority=policy_config.get('priority', 1),
                active=policy_config.get('active', True)
            )
            policies.append(policy)
            
        # Parse tools
        tools = []
        for tool_config in config.get('tools', []):
            tool = AgentTool(
                tool_id=tool_config['tool_id'],
                name=tool_config['name'],
                description=tool_config['description'],
                parameters=tool_config['parameters'],
                endpoint=tool_config.get('endpoint'),
                handler_class=tool_config.get('handler_class')
            )
            tools.append(tool)
            
        # Parse workflow steps
        workflow_steps = []
        for step_config in config.get('workflow_steps', []):
            step = AgentWorkflowStep(
                step_id=step_config['step_id'],
                name=step_config['name'],
                description=step_config['description'],
                tool_name=step_config['tool_name'],
                input_mapping=step_config.get('input_mapping', {}),
                output_mapping=step_config.get('output_mapping', {}),
                conditions=step_config.get('conditions', []),
                required=step_config.get('required', True)
            )
            workflow_steps.append(step)
            
        return AgentDefinition(
            agent_id=config['agent_id'],
            name=config['name'],
            description=config['description'],
            version=config['version'],
            policies=policies,
            tools=tools,
            workflow_steps=workflow_steps,
            llm_prompt_template=config['llm_prompt_template'],
            created_date=datetime.now()
        )
    
    async def execute_agent_workflow(self, agent_id: str, workitem: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a workflow using the specified agent"""
        
        if agent_id not in self.active_agents:
            raise ValueError(f"Agent {agent_id} not found in registry")
            
        agent = self.active_agents[agent_id]
        return await agent.execute_workflow(workitem)
    
    def list_registered_agents(self) -> List[Dict[str, Any]]:
        """List all registered agents"""
        
        agents_list = []
        for agent_id, agent_def in self.agents.items():
            agents_list.append({
                "agent_id": agent_id,
                "name": agent_def.name,
                "description": agent_def.description,
                "version": agent_def.version,
                "policies_count": len(agent_def.policies),
                "tools_count": len(agent_def.tools),
                "workflow_steps_count": len(agent_def.workflow_steps),
                "active": agent_id in self.active_agents
            })
            
        return agents_list

class SpecializedAgent:
    """A specialized agent with its own policies, tools, and workflows"""
    
    def __init__(self, definition: AgentDefinition, openai_client=None):
        self.definition = definition
        self.openai_client = openai_client
        self.tool_handlers = {}
        self.execution_context = {}
        
    async def initialize(self):
        """Initialize the agent with its tools and policies"""
        
        logger.info(f"🔧 Initializing agent: {self.definition.name}")
        
        # Initialize tool handlers
        await self._initialize_tools()
        
        # Initialize policies
        self._initialize_policies()
        
        logger.info(f"✅ Agent {self.definition.name} initialized with {len(self.tool_handlers)} tools and {len(self.definition.policies)} policies")
        
    async def _initialize_tools(self):
        """Initialize MCP tools for this agent"""
        
        # Import and use real MCP tool stubs
        try:
            from mcp_tool_stubs import create_mcp_tool_handlers
            real_handlers = create_mcp_tool_handlers()
            
            for tool_def in self.definition.tools:
                if tool_def.name in real_handlers:
                    # Use real MCP tool stub
                    self.tool_handlers[tool_def.name] = real_handlers[tool_def.name]
                    logger.info(f"   🔧 Registered MCP tool: {tool_def.name}")
                elif tool_def.handler_class:
                    # Dynamic import and instantiation
                    handler = await self._create_tool_handler(tool_def)
                    self.tool_handlers[tool_def.name] = handler
                else:
                    # Fallback mock tool
                    self.tool_handlers[tool_def.name] = self._create_mock_tool(tool_def)
                    logger.info(f"   ⚙️ Using mock tool: {tool_def.name}")
                    
        except ImportError as e:
            logger.warning(f"⚠️ Could not import MCP tool stubs: {e}")
            # Fallback to mock tools
            for tool_def in self.definition.tools:
                self.tool_handlers[tool_def.name] = self._create_mock_tool(tool_def)
                
    async def _create_tool_handler(self, tool_def: AgentTool):
        """Create a tool handler from class name"""
        # In production, this would dynamically import and instantiate
        # For now, return a mock handler
        return self._create_mock_tool(tool_def)
        
    def _create_mock_tool(self, tool_def: AgentTool):
        """Create a mock tool handler for demonstration"""
        
        async def mock_handler(**kwargs):
            return {
                "tool_name": tool_def.name,
                "status": "success",
                "result": f"Mock result from {tool_def.name}",
                "input_params": kwargs,
                "execution_time": "0.1s"
            }
            
        return mock_handler
        
    def _initialize_policies(self):
        """Initialize business policies for this agent"""
        
        logger.info(f"📋 Loading {len(self.definition.policies)} policies for {self.definition.name}")
        
        for policy in self.definition.policies:
            logger.info(f"   • {policy.name}: {len(policy.rules)} rules")
            
    async def execute_workflow(self, workitem: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the agent's workflow for a given workitem"""
        
        execution_id = str(uuid.uuid4())[:8]
        logger.info(f"🎯 Executing {self.definition.name} workflow [ID: {execution_id}]")
        
        # Use LLM to analyze workitem and determine execution strategy
        if self.openai_client:
            strategy = await self._llm_analyze_workitem(workitem)
        else:
            strategy = self._simulate_analysis(workitem)
            
        # Execute workflow steps based on LLM strategy
        results = await self._execute_workflow_steps(workitem, strategy, execution_id)
        
        return {
            "execution_id": execution_id,
            "agent_id": self.definition.agent_id,
            "agent_name": self.definition.name,
            "workitem": workitem,
            "strategy": strategy,
            "results": results,
            "status": "completed",
            "execution_time": datetime.now().isoformat()
        }
        
    async def _llm_analyze_workitem(self, workitem: Dict[str, Any]) -> Dict[str, Any]:
        """Use LLM to analyze workitem and determine execution strategy"""
        
        # Build context about agent capabilities
        agent_context = f"""
Agent: {self.definition.name}
Description: {self.definition.description}

Available Tools:
{self._build_tools_context()}

Business Policies:
{self._build_policies_context()}

Workflow Steps:
{self._build_workflow_context()}
"""

        system_prompt = f"""{self.definition.llm_prompt_template}

{agent_context}

Analyze the workitem and determine execution strategy. Respond with JSON:
{{
    "analysis": "workitem analysis",
    "selected_steps": ["step_ids_to_execute"],
    "policy_applications": ["applicable_policies"],
    "execution_order": ["ordered_step_execution"],
    "expected_outcome": "description"
}}"""

        user_prompt = f"Workitem: {json.dumps(workitem, indent=2)}"
        
        try:
            logger.info("🤖 LLM analyzing workitem for strategy determination...")
            
            response = await self.openai_client.chat.completions.create(
                model=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5-mini"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_completion_tokens=1500
            )
            
            ai_content = response.choices[0].message.content
            strategy = json.loads(ai_content)
            
            logger.info(f"🧠 LLM Strategy: {strategy.get('analysis', 'No analysis provided')[:100]}...")
            return strategy
            
        except Exception as e:
            logger.error(f"❌ LLM analysis failed: {e}")
            return self._simulate_analysis(workitem)
            
    def _simulate_analysis(self, workitem: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate analysis when LLM not available"""
        
        logger.info("🔄 Using simulation mode for workitem analysis")
        
        return {
            "analysis": f"Simulated analysis for {self.definition.name} agent",
            "selected_steps": [step.step_id for step in self.definition.workflow_steps if step.required],
            "policy_applications": [policy.policy_id for policy in self.definition.policies if policy.active],
            "execution_order": [step.step_id for step in self.definition.workflow_steps],
            "expected_outcome": "Simulated workflow execution based on defined steps"
        }
        
    async def _execute_workflow_steps(self, workitem: Dict[str, Any], strategy: Dict[str, Any], execution_id: str) -> List[Dict[str, Any]]:
        """Execute workflow steps based on LLM strategy"""
        
        results = []
        # Include both workitem and flattened workitem keys in context for easier access
        context = {
            "workitem": workitem,
            **workitem  # Flatten workitem keys to top level for direct access
        }
        
        selected_steps = strategy.get("selected_steps", [])
        execution_order = strategy.get("execution_order", selected_steps)
        
        for step_id in execution_order:
            # Find step definition - try by step_id first, then by name
            step_def = next((s for s in self.definition.workflow_steps if s.step_id == step_id), None)
            if not step_def:
                # Try finding by step name (LLM might return step names instead of IDs)
                step_def = next((s for s in self.definition.workflow_steps if s.name == step_id), None)
            if not step_def:
                logger.warning(f"⚠️ Step {step_id} not found in workflow definition")
                continue
                
            logger.info(f"🔧 Executing step: {step_def.name}")
            
            try:
                # Prepare input parameters
                input_params = self._prepare_step_input(step_def, context)
                
                # Execute tool
                if step_def.tool_name in self.tool_handlers:
                    step_result = await self.tool_handlers[step_def.tool_name](**input_params)
                else:
                    logger.warning(f"⚠️ Tool {step_def.tool_name} not found")
                    step_result = {"error": f"Tool {step_def.tool_name} not available"}
                
                # Apply output mapping
                mapped_output = self._apply_output_mapping(step_def, step_result)
                
                # Update context with mapped output and preserve workitem data
                context.update(mapped_output)
                context.update(workitem)  # Ensure workitem data stays available
                
                results.append({
                    "step_id": step_id,
                    "step_name": step_def.name,
                    "tool_name": step_def.tool_name,
                    "input_params": input_params,
                    "raw_result": step_result,
                    "mapped_output": mapped_output,
                    "status": "success"
                })
                
            except Exception as e:
                logger.error(f"❌ Step {step_id} failed: {e}")
                results.append({
                    "step_id": step_id,
                    "step_name": step_def.name,
                    "error": str(e),
                    "status": "failed"
                })
                
                if step_def.required:
                    logger.error(f"🚨 Required step {step_id} failed, stopping workflow")
                    break
                    
        return results
        
    def _prepare_step_input(self, step_def: AgentWorkflowStep, context: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare input parameters for a workflow step"""
        
        input_params = {}
        
        for param_name, mapping_expr in step_def.input_mapping.items():
            if mapping_expr.startswith("{{") and mapping_expr.endswith("}}"):
                # Extract value from context using dot notation
                context_key = mapping_expr[2:-2].strip()
                value = self._get_nested_value(context, context_key)
                if value is not None:
                    input_params[param_name] = value
                else:
                    logger.warning(f"⚠️ Context key {context_key} not found for parameter {param_name}")
            else:
                # Direct value
                input_params[param_name] = mapping_expr
                
        return input_params
        
    def _get_nested_value(self, data: Dict[str, Any], key_path: str) -> Any:
        """Get value from nested dictionary using dot notation"""
        
        try:
            keys = key_path.split('.')
            value = data
            
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return None
                    
            return value
        except Exception:
            return None
        
    def _apply_output_mapping(self, step_def: AgentWorkflowStep, step_result: Dict[str, Any]) -> Dict[str, Any]:
        """Apply output mapping to step result"""
        
        mapped_output = {}
        
        for output_key, result_path in step_def.output_mapping.items():
            value = self._get_nested_value(step_result, result_path)
            if value is not None:
                mapped_output[output_key] = value
            else:
                logger.warning(f"⚠️ Result path {result_path} not found in step result")
                
        return mapped_output
        
    def _build_tools_context(self) -> str:
        """Build tools context for LLM"""
        lines = []
        for tool in self.definition.tools:
            lines.append(f"- {tool.name}: {tool.description}")
        return "\n".join(lines)
        
    def _build_policies_context(self) -> str:
        """Build policies context for LLM"""
        lines = []
        for policy in self.definition.policies:
            lines.append(f"- {policy.name}: {policy.description}")
        return "\n".join(lines)
        
    def _build_workflow_context(self) -> str:
        """Build workflow context for LLM"""
        lines = []
        for step in self.definition.workflow_steps:
            lines.append(f"- {step.name}: {step.description}")
        return "\n".join(lines)

# Demo function
async def demo_agent_registry():
    """Demonstrate the agent registry system"""
    
    print("🏗️ Agent Registry & Onboarding System Demo")
    print("=" * 60)
    
    # Initialize registry
    registry = AgentRegistry()
    
    print(f"🤖 Azure OpenAI: {'✅ Connected' if registry.openai_client else '❌ Simulation Mode'}")
    print()
    
    # Register supplier-filter-agent (will be loaded from YAML)
    try:
        agent_id = await registry.register_agent_from_yaml("supplier-filter-agent.yml")
        print(f"✅ Successfully registered agent: {agent_id}")
    except FileNotFoundError:
        print("⚠️ supplier-filter-agent.yml not found - creating demo agent...")
        # We'll create a demo agent programmatically
        await _create_demo_agent(registry)
    
    # List registered agents
    agents = registry.list_registered_agents()
    print(f"\n📋 Registered Agents: {len(agents)}")
    for agent in agents:
        print(f"   • {agent['name']} (v{agent['version']}) - {agent['tools_count']} tools, {agent['policies_count']} policies")
    
    # Execute a workflow
    if agents:
        agent_id = agents[0]['agent_id']
        workitem = {
            "request_type": "supplier_filtering",
            "criteria": {
                "min_rating": 4.0,
                "max_lead_time": 7,
                "budget_limit": 100000
            },
            "category": "electronics"
        }
        
        print(f"\n🎯 Executing workflow for agent: {agents[0]['name']}")
        print(f"📋 Workitem: {workitem}")
        print("-" * 50)
        
        result = await registry.execute_agent_workflow(agent_id, workitem)
        
        print(f"✅ Execution completed [ID: {result['execution_id']}]")
        print(f"🎯 Strategy: {result['strategy'].get('analysis', 'N/A')[:100]}...")
        print(f"🔧 Steps executed: {len(result['results'])}")
        
        for step_result in result['results']:
            status_icon = "✅" if step_result['status'] == 'success' else "❌"
            print(f"   {status_icon} {step_result['step_name']}")

async def _create_demo_agent(registry: AgentRegistry):
    """Create a demo agent programmatically"""
    
    demo_config = {
        "agent_id": "supplier-filter-demo",
        "name": "Supplier Filter Agent (Demo)",
        "description": "Demo agent for filtering suppliers based on business policies",
        "version": "1.0.0",
        "llm_prompt_template": "You are a supplier filtering specialist. Analyze workitems and apply business policies to filter and rank suppliers.",
        "policies": [
            {
                "policy_id": "supplier_rating_policy",
                "name": "Supplier Rating Policy",
                "description": "Minimum rating requirements for supplier selection",
                "rules": [
                    {"condition": "rating >= 4.0", "action": "include"},
                    {"condition": "rating < 4.0", "action": "exclude"}
                ]
            }
        ],
        "tools": [
            {
                "tool_id": "search_suppliers",
                "name": "search_suppliers",
                "description": "Search for suppliers based on criteria",
                "parameters": {"criteria": "dict", "location": "str"}
            },
            {
                "tool_id": "filter_suppliers",
                "name": "filter_suppliers",
                "description": "Filter suppliers based on policies",
                "parameters": {"suppliers": "list", "policies": "list"}
            }
        ],
        "workflow_steps": [
            {
                "step_id": "search",
                "name": "Search Suppliers",
                "description": "Search for suppliers matching basic criteria",
                "tool_name": "search_suppliers",
                "input_mapping": {"criteria": "{{workitem.criteria}}"},
                "output_mapping": {"found_suppliers": "result"}
            },
            {
                "step_id": "filter",
                "name": "Apply Policies",
                "description": "Filter suppliers using business policies",
                "tool_name": "filter_suppliers",
                "input_mapping": {"suppliers": "{{found_suppliers}}", "policies": "rating_policy"},
                "output_mapping": {"filtered_suppliers": "result"}
            }
        ]
    }
    
    agent_def = registry._parse_agent_config(demo_config)
    registry.agents[agent_def.agent_id] = agent_def
    
    active_agent = SpecializedAgent(agent_def, registry.openai_client)
    await active_agent.initialize()
    registry.active_agents[agent_def.agent_id] = active_agent
    
    logger.info(f"✅ Created demo agent: {agent_def.name}")

if __name__ == "__main__":
    asyncio.run(demo_agent_registry())