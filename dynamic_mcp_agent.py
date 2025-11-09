#!/usr/bin/env python3
"""
Dynamic MCP Tool Pool Agent
===========================

An intelligent agent that works with a pool of registered MCP tools and uses LLM
to dynamically determine which tools to use, how many, and how to map outputs
between them. The LLM has full control over tool orchestration.

Key Features:
- Dynamic tool registration and discovery
- LLM-driven tool selection from available pool
- Automatic output-to-input mapping between tools
- Variable-length tool chains (1 to N tools)
- Returns the final tool's result
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
import uuid
import inspect
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Try to import OpenAI - graceful fallback if not available
try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
    logger.info("✅ OpenAI package available for LLM integration")
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("⚠️ OpenAI package not available - falling back to simulation mode")

@dataclass
class MCPTool:
    """Represents a registered MCP tool with its metadata"""
    name: str
    description: str
    function: Callable
    input_schema: Dict[str, Any]
    output_schema: Optional[Dict[str, Any]] = None
    tags: List[str] = field(default_factory=list)
    examples: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class ToolExecutionPlan:
    """LLM-generated execution plan for tool orchestration"""
    tools: List[Dict[str, Any]]
    reasoning: str
    expected_output: str
    confidence: float

@dataclass
class DynamicAgentConfig:
    """Configuration for the dynamic agent"""
    max_tools_in_chain: int = 10
    execution_timeout: int = 300
    llm_temperature: float = 0.1
    enable_parallel_execution: bool = False
    
    # AI Model Configuration
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model_name: str = os.getenv("MODEL_NAME", "gpt-4o-mini")
    max_tokens: int = 2000
    enable_ai_analysis: bool = True  # Set to False to use simulation mode

class MCPToolPool:
    """Registry and manager for MCP tools"""
    
    def __init__(self):
        self.tools: Dict[str, MCPTool] = {}
        
    def register_tool(self, tool: MCPTool) -> None:
        """Register a new MCP tool in the pool"""
        self.tools[tool.name] = tool
        logger.info(f"🔧 Registered MCP tool: {tool.name}")
    
    def get_tool(self, name: str) -> Optional[MCPTool]:
        """Get a tool by name"""
        return self.tools.get(name)
    
    def list_tools(self) -> List[MCPTool]:
        """Get all registered tools"""
        return list(self.tools.values())
    
    def get_tools_by_tags(self, tags: List[str]) -> List[MCPTool]:
        """Get tools that match any of the given tags"""
        matching_tools = []
        for tool in self.tools.values():
            if any(tag in tool.tags for tag in tags):
                matching_tools.append(tool)
        return matching_tools
    
    def generate_llm_context(self) -> str:
        """Generate comprehensive tool context for LLM"""
        if not self.tools:
            return "No tools available in the pool."
        
        context_parts = ["Available MCP Tools:"]
        
        for tool in self.tools.values():
            context_parts.append(f"\n🔧 {tool.name}:")
            context_parts.append(f"  Description: {tool.description}")
            
            # Input schema
            if tool.input_schema:
                context_parts.append("  Input Parameters:")
                properties = tool.input_schema.get("properties", {})
                required = tool.input_schema.get("required", [])
                
                for param_name, param_info in properties.items():
                    param_type = param_info.get("type", "unknown")
                    param_desc = param_info.get("description", "No description")
                    is_required = "✅ REQUIRED" if param_name in required else "🔹 Optional"
                    context_parts.append(f"    • {param_name} ({param_type}) {is_required}: {param_desc}")
            
            # Output schema
            if tool.output_schema:
                context_parts.append("  Output Fields:")
                output_props = tool.output_schema.get("properties", {})
                for field_name, field_info in output_props.items():
                    field_desc = field_info.get("description", "No description")
                    context_parts.append(f"    • {field_name}: {field_desc}")
            
            # Tags and examples
            if tool.tags:
                context_parts.append(f"  Tags: {', '.join(tool.tags)}")
            
            if tool.examples:
                context_parts.append("  Examples:")
                for example in tool.examples[:2]:  # Limit to 2 examples
                    context_parts.append(f"    • {json.dumps(example, indent=6)}")
        
        return "\n".join(context_parts)

class DynamicMCPAgent:
    """
    Dynamic agent that uses LLM to orchestrate any pool of MCP tools
    """
    
    def __init__(self, config: DynamicAgentConfig = None):
        self.config = config or DynamicAgentConfig()
        self.tool_pool = MCPToolPool()
        self.execution_history: List[Dict[str, Any]] = []
        self.openai_client = None
        self._setup_ai_client()
        
    def register_mcp_tool(self, 
                         name: str,
                         description: str, 
                         function: Callable,
                         input_schema: Dict[str, Any],
                         output_schema: Optional[Dict[str, Any]] = None,
                         tags: List[str] = None,
                         examples: List[Dict[str, Any]] = None) -> None:
        """Register a new MCP tool with the agent"""
        
        tool = MCPTool(
            name=name,
            description=description,
            function=function,
            input_schema=input_schema,
            output_schema=output_schema,
            tags=tags or [],
            examples=examples or []
        )
        
        self.tool_pool.register_tool(tool)
    
    def _setup_ai_client(self) -> None:
        """Initialize AI client for LLM analysis"""
        if not self.config.enable_ai_analysis:
            logger.info("🤖 AI analysis disabled - using simulation mode")
            return
            
        if not OPENAI_AVAILABLE:
            logger.warning("⚠️ OpenAI not available - using simulation mode")
            return
            
        if not self.config.openai_api_key:
            logger.warning("⚠️ OpenAI API key not provided - using simulation mode")
            return
        
        try:
            self.openai_client = AsyncOpenAI(
                api_key=self.config.openai_api_key,
                base_url=self.config.openai_base_url
            )
            logger.info(f"🤖 AI client initialized - Model: {self.config.model_name}")
        except Exception as e:
            logger.error(f"❌ Failed to initialize AI client: {e}")
            self.openai_client = None
    
    async def analyze_user_request_with_llm(self, user_query: str) -> ToolExecutionPlan:
        """
        Use LLM to analyze user request and generate dynamic execution plan
        This is where the magic happens - LLM decides everything!
        """
        
        tools_context = self.tool_pool.generate_llm_context()
        
        # Use real AI analysis if available, otherwise fall back to simulation
        if self.openai_client and self.config.enable_ai_analysis:
            return await self._real_llm_analysis(user_query, tools_context)
        else:
            logger.info("🔄 Using simulation mode for analysis")
            return await self._simulate_llm_analysis(user_query, tools_context)
    
    async def _real_llm_analysis(self, user_query: str, tools_context: str) -> ToolExecutionPlan:
        """
        Use real AI model to analyze user request and generate execution plan
        """
        prompt = f"""
You are an expert AI agent that analyzes user queries and determines the optimal sequence of MCP tools to execute.

USER QUERY: "{user_query}"

{tools_context}

ANALYSIS TASK:
Analyze the user query and determine the best execution strategy. Consider:
1. What is the user trying to accomplish?
2. Which tools are needed from the available pool?
3. What is the optimal sequence of tool execution?
4. How should outputs from one tool be mapped to inputs of the next?

BUSINESS DOMAIN KNOWLEDGE:
- Purchase Request (PR) → Purchase Order (PO) → Goods Receipt (GR) → Movement/Inspection
- Use tool chains for comprehensive analysis, tracking, or multi-step workflows
- Use single tools for simple lookups or direct queries
- Extract exact identifiers (PO numbers, PR numbers, receipt numbers) from the query

RESPONSE FORMAT (JSON ONLY):
{{
  "strategy": "single_tool|tool_chain|clarification",
  "reasoning": "Clear explanation of your decision and approach",
  "confidence": 0.85,
  
  // For single_tool strategy:
  "tool_name": "exact_tool_name",
  "parameters": {{"param": "extracted_value"}},
  
  // For tool_chain strategy:
  "tool_chain": [
    {{
      "tool_name": "first_tool_name",
      "parameters": {{"param": "extracted_value"}},
      "output_mapping": {{"output_field": "context_key"}}
    }},
    {{
      "tool_name": "second_tool_name", 
      "parameters": {{"param": "{{{{context_key}}}}"}},
      "output_mapping": {{"output_field": "next_context_key"}}
    }},
    {{
      "tool_name": "final_tool_name",
      "parameters": {{"param": "{{{{next_context_key}}}}"}},
      "output_mapping": {{}}
    }}
  ],
  
  // For clarification strategy:
  "clarification_message": "What specific information do you need?",
  "suggestions": ["suggestion1", "suggestion2"]
}}

CRITICAL RULES:
1. Always respond with valid JSON only
2. Extract exact parameter values from user query
3. Use {{{{placeholder}}}} syntax for parameter mapping
4. Confidence should reflect certainty of strategy choice
5. Tool names must match exactly from available tools
6. Consider business process flows for tool chaining
"""

        try:
            logger.info(f"🤖 Sending query to {self.config.model_name} for analysis...")
            
            response = await self.openai_client.chat.completions.create(
                model=self.config.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at analyzing user queries for MCP tool orchestration. Always respond with valid JSON."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=self.config.llm_temperature,
                max_tokens=self.config.max_tokens
            )
            
            response_text = response.choices[0].message.content.strip()
            logger.info(f"🧠 AI Model Response Length: {len(response_text)} chars")
            
            # Parse JSON response
            try:
                # Try direct JSON parsing first
                strategy = json.loads(response_text)
                logger.info(f"✅ AI Analysis Complete - Strategy: {strategy.get('strategy', 'unknown')}")
                return self._convert_ai_response_to_plan(strategy)
                
            except json.JSONDecodeError as e:
                # Try to extract JSON from markdown code blocks
                import re
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
                if json_match:
                    strategy = json.loads(json_match.group(1))
                    logger.info(f"✅ AI Analysis Complete (from code block) - Strategy: {strategy.get('strategy', 'unknown')}")
                    return self._convert_ai_response_to_plan(strategy)
                else:
                    logger.error(f"❌ Failed to parse AI response as JSON: {e}")
                    logger.error(f"Raw response: {response_text[:500]}...")
                    # Fall back to simulation
                    return await self._simulate_llm_analysis(user_query, tools_context)
                    
        except Exception as e:
            logger.error(f"❌ Error calling AI model: {e}")
            # Fall back to simulation on any error
            return await self._simulate_llm_analysis(user_query, tools_context)
    
    def _convert_ai_response_to_plan(self, ai_response: Dict[str, Any]) -> ToolExecutionPlan:
        """Convert AI model response to ToolExecutionPlan"""
        strategy = ai_response.get("strategy", "clarification")
        
        if strategy == "single_tool":
            tools = [
                {
                    "tool_name": ai_response.get("tool_name", ""),
                    "parameters": ai_response.get("parameters", {}),
                    "output_mapping": {}
                }
            ]
        elif strategy == "tool_chain":
            tools = ai_response.get("tool_chain", [])
        else:
            tools = []
        
        return ToolExecutionPlan(
            tools=tools,
            reasoning=ai_response.get("reasoning", "AI-generated analysis"),
            expected_output=ai_response.get("expected_output", "Tool execution results"),
            confidence=ai_response.get("confidence", 0.8)
        )
    
    async def _simulate_llm_analysis(self, user_query: str, tools_context: str) -> ToolExecutionPlan:
        """
        Simulate LLM analysis for tool orchestration
        In production, this would be replaced with actual LLM calls
        """
        query_lower = user_query.lower()
        available_tools = list(self.tool_pool.tools.keys())
        
        # Simulate intelligent analysis based on query patterns
        if any(word in query_lower for word in ["trace", "track", "follow", "movement", "flow"]):
            # Complex workflow needed
            if "purchase" in query_lower or "po" in query_lower or "order" in query_lower:
                tools_plan = [
                    {
                        "tool_name": "view_purchase_order",
                        "parameters": {"po_number": self._extract_identifier(user_query, "po")},
                        "output_mapping": {"PoNo": "reference_number"}
                    },
                    {
                        "tool_name": "help_on_receipt_document", 
                        "parameters": {"ref_doc_no_from": "{{reference_number}}"},
                        "output_mapping": {"ReceiptNo": "receipt_id"}
                    },
                    {
                        "tool_name": "view_movement_details",
                        "parameters": {"receipt_no": "{{receipt_id}}"},
                        "output_mapping": {}  # Final result
                    }
                ]
                
                return ToolExecutionPlan(
                    tools=tools_plan,
                    reasoning="User wants to trace PO flow - requires 3-step workflow: PO → Receipt → Movement",
                    expected_output="Movement history and current location details",
                    confidence=0.95
                )
        
        elif (any(word in query_lower for word in ["complete", "full", "everything", "details"]) and 
              any(word in query_lower for word in ["request", "pr"])) or \
             (any(word in query_lower for word in ["get", "show", "find"]) and 
              any(word in query_lower for word in ["request", "pr"])):
            # PR complete analysis
            tools_plan = [
                {
                    "tool_name": "view_purchase_request",
                    "parameters": {"pr_number": self._extract_identifier(user_query, "pr")},
                    "output_mapping": {"PrNo": "pr_reference"}
                },
                {
                    "tool_name": "search_purchase_orders",
                    "parameters": {"pr_no_from": "{{pr_reference}}", "pr_no_to": "{{pr_reference}}"},
                    "output_mapping": {"PoNo": "related_po"}
                },
                {
                    "tool_name": "view_purchase_order",
                    "parameters": {"po_number": "{{related_po}}"},
                    "output_mapping": {}  # Final result
                }
            ]
            
            return ToolExecutionPlan(
                tools=tools_plan,
                reasoning="User wants complete PR analysis - requires PR → Search → PO workflow",
                expected_output="Complete purchase order details related to the PR",
                confidence=0.90
            )
        
        elif any(word in query_lower for word in ["where", "location", "happened", "after"]) and \
             any(word in query_lower for word in ["order", "po", "delivery", "received"]):
            # Movement tracking for orders
            tools_plan = [
                {
                    "tool_name": "view_purchase_order",
                    "parameters": {"po_number": self._extract_identifier(user_query, "po")},
                    "output_mapping": {"PoNo": "reference_number"}
                },
                {
                    "tool_name": "help_on_receipt_document", 
                    "parameters": {"ref_doc_no_from": "{{reference_number}}"},
                    "output_mapping": {"ReceiptNo": "receipt_id"}
                },
                {
                    "tool_name": "view_movement_details",
                    "parameters": {"receipt_no": "{{receipt_id}}"},
                    "output_mapping": {}  # Final result
                }
            ]
            
            return ToolExecutionPlan(
                tools=tools_plan,
                reasoning="User wants to track order location/movement - requires PO → Receipt → Movement workflow",
                expected_output="Current location and movement history",
                confidence=0.92
            )
        
        elif any(word in query_lower for word in ["inspection", "quality", "qc"]):
            # Quality workflow
            tools_plan = [
                {
                    "tool_name": "view_movement_details",
                    "parameters": {"receipt_no": self._extract_identifier(user_query, "receipt")},
                    "output_mapping": {"ReceiptNo": "receipt_ref"}
                },
                {
                    "tool_name": "view_inspection_details", 
                    "parameters": {"receipt_no": "{{receipt_ref}}"},
                    "output_mapping": {}  # Final result
                }
            ]
            
            return ToolExecutionPlan(
                tools=tools_plan,
                reasoning="User wants quality inspection info - requires Movement → Inspection workflow",
                expected_output="Quality inspection results and details",
                confidence=0.85
            )
        
        else:
            # Simple single tool execution
            if "purchase order" in query_lower or "po" in query_lower:
                tool_name = "view_purchase_order"
                parameters = {"po_number": self._extract_identifier(user_query, "po")}
            elif "purchase request" in query_lower or "pr" in query_lower:
                tool_name = "view_purchase_request"
                parameters = {"pr_number": self._extract_identifier(user_query, "pr")}
            else:
                # Default fallback
                return ToolExecutionPlan(
                    tools=[],
                    reasoning="Query unclear - need clarification from user",
                    expected_output="Clarification request",
                    confidence=0.3
                )
            
            tools_plan = [
                {
                    "tool_name": tool_name,
                    "parameters": parameters,
                    "output_mapping": {}  # Final result
                }
            ]
            
            return ToolExecutionPlan(
                tools=tools_plan,
                reasoning=f"Simple single tool query - using {tool_name}",
                expected_output=f"Details from {tool_name}",
                confidence=0.80
            )
    
    def _extract_identifier(self, query: str, id_type: str) -> str:
        """Extract identifiers from query based on type"""
        import re
        
        if id_type == "po":
            match = re.search(r'(PO\w+|\b[A-Z0-9]+\d+\w*)', query, re.IGNORECASE)
            return match.group(1) if match else "PO123"
        elif id_type == "pr":
            match = re.search(r'(PR\w+|REQ\w+|\b[A-Z0-9]+\d+\w*)', query, re.IGNORECASE)
            return match.group(1) if match else "PR123"
        elif id_type == "receipt":
            match = re.search(r'(GR\w+|REC\w+|\b\d+)', query, re.IGNORECASE)
            return match.group(1) if match else "GR1041"
        else:
            match = re.search(r'(\b[A-Z0-9]+\d+\w*)', query, re.IGNORECASE)
            return match.group(1) if match else "ID123"
    
    async def execute_tool_plan(self, plan: ToolExecutionPlan) -> Dict[str, Any]:
        """
        Execute the LLM-generated tool plan with dynamic output mapping
        """
        if not plan.tools:
            return {
                "type": "clarification",
                "message": "I need more information to help you. Could you be more specific?",
                "available_tools": list(self.tool_pool.tools.keys())
            }
        
        context = {}
        execution_results = []
        final_result = None
        
        logger.info(f"🎯 Executing {len(plan.tools)}-step tool plan: {plan.reasoning}")
        
        for i, step in enumerate(plan.tools):
            tool_name = step["tool_name"]
            parameters = step["parameters"]
            output_mapping = step.get("output_mapping", {})
            
            # Resolve parameter placeholders
            resolved_params = self._resolve_parameters(parameters, context)
            
            # Get and execute the tool
            tool = self.tool_pool.get_tool(tool_name)
            if not tool:
                raise ValueError(f"Tool '{tool_name}' not found in pool")
            
            logger.info(f"🔧 Step {i+1}/{len(plan.tools)}: Executing {tool_name}")
            
            # Execute the tool function
            start_time = asyncio.get_event_loop().time()
            
            try:
                if asyncio.iscoroutinefunction(tool.function):
                    result = await tool.function(**resolved_params)
                else:
                    result = tool.function(**resolved_params)
            except Exception as e:
                logger.error(f"❌ Tool execution failed: {tool_name} - {e}")
                raise
            
            execution_time = asyncio.get_event_loop().time() - start_time
            
            # Store execution details
            execution_results.append({
                "step": i + 1,
                "tool_name": tool_name,
                "parameters": resolved_params,
                "result": result,
                "execution_time": execution_time,
                "output_mapping": output_mapping
            })
            
            # Apply output mapping for next steps
            if output_mapping:
                if isinstance(result, dict):
                    for result_field, context_key in output_mapping.items():
                        if result_field in result:
                            context[context_key] = result[result_field]
                elif isinstance(result, list) and result:
                    # Handle list results - use first item
                    first_item = result[0]
                    if isinstance(first_item, dict):
                        for result_field, context_key in output_mapping.items():
                            if result_field in first_item:
                                context[context_key] = first_item[result_field]
            
            # Store raw result for context as well
            context[f"step_{i}_result"] = result
            
            # The last tool's result is the final result
            final_result = result
        
        return {
            "type": "dynamic_execution", 
            "plan_reasoning": plan.reasoning,
            "confidence": plan.confidence,
            "execution_steps": execution_results,
            "final_result": final_result,
            "total_steps": len(plan.tools)
        }
    
    def _resolve_parameters(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve parameter placeholders using execution context"""
        resolved = {}
        
        for key, value in parameters.items():
            if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
                placeholder = value[2:-2]
                if placeholder in context:
                    resolved[key] = context[placeholder]
                    logger.debug(f"🔄 Resolved {{{{placeholder}}}}: {placeholder} → {context[placeholder]}")
                else:
                    logger.warning(f"⚠️ Placeholder not found: {placeholder}")
                    resolved[key] = value  # Keep original if not found
            else:
                resolved[key] = value
        
        return resolved
    
    async def process_request(self, user_query: str) -> Dict[str, Any]:
        """
        Main entry point - processes any user request using dynamic tool orchestration
        """
        session_id = str(uuid.uuid4())
        start_time = asyncio.get_event_loop().time()
        
        logger.info(f"🎯 Processing dynamic request [Session: {session_id[:8]}]: {user_query}")
        
        try:
            # Step 1: LLM analyzes request and generates execution plan
            plan = await self.analyze_user_request_with_llm(user_query)
            
            # Step 2: Execute the plan dynamically
            result = await self.execute_tool_plan(plan)
            
            # Step 3: Package the response
            response = {
                "session_id": session_id,
                "user_query": user_query,
                "success": True,
                "execution_time": asyncio.get_event_loop().time() - start_time,
                **result
            }
            
            # Store in execution history
            self.execution_history.append(response)
            
            logger.info(f"✅ Dynamic execution completed [Session: {session_id[:8]}] - {len(plan.tools)} tools used")
            
            return response
            
        except Exception as e:
            logger.error(f"❌ Error in dynamic processing: {e}")
            return {
                "session_id": session_id,
                "user_query": user_query,
                "success": False,
                "error": str(e),
                "execution_time": asyncio.get_event_loop().time() - start_time
            }

# Demo: Register sample MCP tools
async def register_sample_tools(agent: DynamicMCPAgent):
    """Register sample MCP tools for demonstration"""
    
    # Simulate real MCP tool functions
    async def view_purchase_order(po_number: str, amendment_no: str = "0") -> Dict[str, Any]:
        await asyncio.sleep(0.2)  # Simulate API call
        return {
            "PoNo": po_number,
            "SupplierName": "Dynamic Industries Ltd",
            "PoAmount": 35000.00,
            "PoStatus": "Active",
            "PoDate": "2024-11-09",
            "LineItems": [
                {"ItemCode": "DYN001", "Description": "Dynamic Components", "Quantity": 75, "UnitPrice": 466.67}
            ]
        }
    
    async def view_purchase_request(pr_number: str) -> Dict[str, Any]:
        await asyncio.sleep(0.15)
        return {
            "PrNo": pr_number,
            "RequesterName": "Alice Johnson",
            "Department": "Procurement",
            "PrStatus": "Converted",
            "TotalAmount": 35000.00,
            "RequestDate": "2024-11-05"
        }
    
    async def search_purchase_orders(pr_no_from: str = None, pr_no_to: str = None, 
                                   po_no_from: str = None, po_no_to: str = None) -> List[Dict[str, Any]]:
        await asyncio.sleep(0.25)
        return [
            {
                "PoNo": f"PO-{pr_no_from.replace('PR', '')}" if pr_no_from else "PO-DYN123",
                "PrNo": pr_no_from or "PR-DYN123",
                "SupplierName": "Dynamic Industries Ltd",
                "PoAmount": 35000.00,
                "PoDate": "2024-11-07",
                "PoStatus": "Active"
            }
        ]
    
    async def help_on_receipt_document(ref_doc_no_from: str = None, ref_doc_no_to: str = None) -> List[Dict[str, Any]]:
        await asyncio.sleep(0.18)
        return [
            {
                "ReceiptNo": "GR-DYN2024",
                "RefDocNo": ref_doc_no_from or "PO-DYN123",
                "ReceivedDate": "2024-11-09",
                "ReceivedQty": 75,
                "AcceptedQty": 75,
                "RejectedQty": 0
            }
        ]
    
    async def view_movement_details(receipt_no: str) -> Dict[str, Any]:
        await asyncio.sleep(0.22)
        return {
            "ReceiptNo": receipt_no,
            "MovementHistory": [
                {
                    "Date": "2024-11-09T09:00:00",
                    "FromLocation": "Receiving Bay",
                    "ToLocation": "Warehouse B-2", 
                    "Quantity": 75,
                    "MovementType": "Goods Receipt"
                },
                {
                    "Date": "2024-11-09T11:30:00",
                    "FromLocation": "Warehouse B-2",
                    "ToLocation": "Quality Lab",
                    "Quantity": 75,
                    "MovementType": "QC Transfer"
                }
            ],
            "CurrentLocation": "Quality Lab",
            "CurrentStock": 75
        }
    
    async def view_inspection_details(receipt_no: str) -> Dict[str, Any]:
        await asyncio.sleep(0.16)
        return {
            "ReceiptNo": receipt_no,
            "InspectionDate": "2024-11-09T12:00:00",
            "Inspector": "Bob Wilson",
            "InspectionResult": "Pass",
            "QualityGrade": "A+",
            "DefectCount": 0,
            "SampleSize": 8,
            "TestResults": {
                "DimensionalCheck": "Pass",
                "MaterialTest": "Pass",
                "FunctionalTest": "Pass"
            }
        }
    
    # Register all tools with comprehensive metadata
    agent.register_mcp_tool(
        name="view_purchase_order",
        description="Retrieve comprehensive purchase order information including supplier details, amounts, and line items",
        function=view_purchase_order,
        input_schema={
            "type": "object",
            "properties": {
                "po_number": {"type": "string", "description": "Purchase order number"},
                "amendment_no": {"type": "string", "description": "Amendment number", "default": "0"}
            },
            "required": ["po_number"]
        },
        output_schema={
            "type": "object", 
            "properties": {
                "PoNo": {"type": "string", "description": "Purchase order number"},
                "SupplierName": {"type": "string", "description": "Supplier company name"},
                "PoAmount": {"type": "number", "description": "Total purchase order amount"},
                "PoStatus": {"type": "string", "description": "Current PO status"},
                "LineItems": {"type": "array", "description": "PO line items with details"}
            }
        },
        tags=["purchase", "order", "procurement", "supplier"],
        examples=[
            {"po_number": "PO123", "amendment_no": "0"},
            {"po_number": "JSLTEST46"}
        ]
    )
    
    agent.register_mcp_tool(
        name="view_purchase_request",
        description="Get purchase requisition details including requester info and approval status",
        function=view_purchase_request,
        input_schema={
            "type": "object",
            "properties": {
                "pr_number": {"type": "string", "description": "Purchase request number"}
            },
            "required": ["pr_number"]
        },
        output_schema={
            "type": "object",
            "properties": {
                "PrNo": {"type": "string", "description": "Purchase request number"},
                "RequesterName": {"type": "string", "description": "Name of person who made the request"},
                "Department": {"type": "string", "description": "Requesting department"},
                "PrStatus": {"type": "string", "description": "Current PR status"}
            }
        },
        tags=["purchase", "request", "requisition", "approval"],
        examples=[{"pr_number": "PR123"}]
    )
    
    # Register remaining tools...
    for tool_func, name, desc, tags in [
        (search_purchase_orders, "search_purchase_orders", "Search for purchase orders using various criteria", ["search", "purchase", "order"]),
        (help_on_receipt_document, "help_on_receipt_document", "Find receipt documents based on reference numbers", ["receipt", "document", "reference"]),
        (view_movement_details, "view_movement_details", "Get detailed stock movement history and current location", ["movement", "stock", "location", "tracking"]),
        (view_inspection_details, "view_inspection_details", "Retrieve quality inspection results and test data", ["inspection", "quality", "testing", "qc"])
    ]:
        agent.register_mcp_tool(
            name=name,
            description=desc,
            function=tool_func,
            input_schema={"type": "object", "properties": {}, "required": []},  # Simplified for demo
            tags=tags
        )

async def demo():
    """Demonstrate the dynamic MCP agent"""
    print("\n" + "="*80)
    print("🤖 Dynamic MCP Tool Pool Agent - LLM-Driven Orchestration")
    print("="*80)
    
    # Configuration for AI model integration
    config = DynamicAgentConfig()
    config.enable_ai_analysis = bool(os.getenv("USE_AI_MODEL", "False").lower() in ["true", "1", "yes"])
    config.openai_api_key = os.getenv("OPENAI_API_KEY", "your-openai-api-key")
    config.openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    config.model_name = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    config.max_tokens = int(os.getenv("OPENAI_MAX_TOKENS", "2000"))
    config.llm_temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.1"))
    
    # Create agent with configuration and register tools
    agent = DynamicMCPAgent(config=config)
    await register_sample_tools(agent)
    
    print(f"✅ Registered {len(agent.tool_pool.tools)} MCP tools in the pool")
    print(f"🧠 LLM will decide which tools to use and how to chain them")
    
    # Test queries that require different levels of complexity
    test_queries = [
        "Show me PO12345",  # Simple single tool
        "Where is my order DYN456 right now?",  # Complex 3-tool chain
        "Get me everything about purchase request PR789",  # PR lifecycle chain  
        "Check quality inspection for receipt GR2024",  # QC workflow chain
        "What happened to order ABC999 after delivery?",  # Movement tracking chain
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n📝 Test Query {i}: {query}")
        print("-" * 60)
        
        result = await agent.process_request(query)
        
        if result['success']:
            print(f"🎯 LLM Plan: {result.get('plan_reasoning', 'N/A')}")
            print(f"🎲 Confidence: {result.get('confidence', 0):.0%}")
            print(f"🔧 Tools Used: {result.get('total_steps', 0)}")
            print(f"⏱️  Total Time: {result['execution_time']:.2f}s")
            
            # Show execution steps
            steps = result.get('execution_steps', [])
            if steps:
                print("📊 Execution Chain:")
                for step in steps:
                    print(f"   Step {step['step']}: {step['tool_name']} ({step['execution_time']:.2f}s)")
            
            # Show final result preview
            final_result = result.get('final_result')
            if final_result:
                if isinstance(final_result, dict):
                    preview_keys = list(final_result.keys())[:3]
                    preview = {k: final_result[k] for k in preview_keys}
                    print(f"📋 Final Result Preview: {json.dumps(preview, indent=2)}")
                else:
                    print(f"📋 Final Result: {str(final_result)[:100]}...")
        else:
            print(f"❌ Error: {result.get('error', 'Unknown error')}")
    
    print(f"\n{'='*80}")
    print("🎉 Dynamic MCP orchestration demo completed!")
    print(f"📚 Execution history contains {len(agent.execution_history)} sessions")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(demo())