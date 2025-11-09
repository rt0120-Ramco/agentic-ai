"""
Multi-Tool Orchestrator Agent with FastMCP and LLM
================================================

An enhanced agent system that uses FastMCP for MCP protocol handling and LLM 
for intelligent multi-tool orchestration. This agent can process complex requests
by automatically determining which tools to use and how to chain them together.

Features:
- FastMCP integration for modern MCP protocol handling
- LLM-driven tool selection and chaining
- Intelligent parameter mapping between tools
- Support for complex multi-step workflows
- Real-time execution monitoring
- Error handling and recovery
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, asdict
from datetime import datetime
import traceback

# FastMCP imports
from fastmcp import FastMCP
from fastmcp.utilities import create_tool

# OpenAI for LLM capabilities
from openai import AsyncAzureOpenAI

# Configuration
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class AgentConfig:
    """Configuration for the Multi-Tool Agent"""
    # Azure OpenAI Configuration
    azure_openai_endpoint: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    azure_openai_api_key: str = os.getenv("AZURE_OPENAI_API_KEY", "")
    azure_openai_deployment: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4")
    azure_openai_api_version: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    
    # Agent Configuration
    max_tool_chain_length: int = 5
    execution_timeout: int = 120  # seconds
    
    # MCP Server Configuration
    mcp_host: str = "localhost"
    mcp_port: int = 8001

@dataclass
class ToolExecution:
    """Represents a single tool execution in a chain"""
    tool_name: str
    parameters: Dict[str, Any]
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None
    timestamp: Optional[str] = None

@dataclass
class AgentExecution:
    """Represents a complete agent execution session"""
    session_id: str
    user_query: str
    strategy: str  # "single_tool", "tool_chain", "clarification"
    tool_executions: List[ToolExecution]
    final_result: Optional[Any] = None
    total_execution_time: Optional[float] = None
    success: bool = False
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "session_id": self.session_id,
            "user_query": self.user_query,
            "strategy": self.strategy,
            "tool_executions": [asdict(te) for te in self.tool_executions],
            "final_result": self.final_result,
            "total_execution_time": self.total_execution_time,
            "success": self.success,
            "error_message": self.error_message
        }

class MultiToolOrchestrator:
    """
    LLM-driven tool orchestrator that determines execution strategies
    and manages complex tool chains
    """
    
    def __init__(self, config: AgentConfig, available_tools: List[Dict[str, Any]]):
        self.config = config
        self.available_tools = available_tools
        self.openai_client = None
        self._setup_openai_client()
        
    def _setup_openai_client(self):
        """Initialize Azure OpenAI client"""
        if self.config.azure_openai_api_key and self.config.azure_openai_endpoint:
            try:
                self.openai_client = AsyncAzureOpenAI(
                    api_key=self.config.azure_openai_api_key,
                    api_version=self.config.azure_openai_api_version,
                    azure_endpoint=self.config.azure_openai_endpoint
                )
                logger.info("✅ Azure OpenAI client initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Azure OpenAI client: {e}")
                self.openai_client = None
        else:
            logger.warning("⚠️  Azure OpenAI credentials not found")
    
    def _create_tools_description(self) -> str:
        """Create a formatted description of available tools for LLM"""
        descriptions = []
        for tool in self.available_tools:
            name = tool.get("name", "unknown")
            description = tool.get("description", "No description")
            
            # Extract parameters from inputSchema
            input_schema = tool.get("inputSchema", {})
            properties = input_schema.get("properties", {})
            required = input_schema.get("required", [])
            
            param_info = []
            for param_name, param_details in properties.items():
                param_type = param_details.get("type", "string")
                param_desc = param_details.get("description", "")
                is_required = param_name in required
                param_info.append(f"    - {param_name} ({param_type}): {param_desc} {'*REQUIRED*' if is_required else ''}")
            
            tool_desc = f"🔧 {name}:\n  Description: {description}"
            if param_info:
                tool_desc += f"\n  Parameters:\n" + "\n".join(param_info)
            
            descriptions.append(tool_desc)
        
        return "\n\n".join(descriptions)
    
    async def analyze_execution_strategy(self, user_query: str) -> Dict[str, Any]:
        """
        Use LLM to analyze user query and determine optimal execution strategy
        """
        if not self.openai_client:
            return {
                "strategy": "error",
                "error": "LLM not available - Azure OpenAI client not initialized"
            }
        
        tools_description = self._create_tools_description()
        
        prompt = f"""
You are an intelligent agent that analyzes user queries to determine the optimal execution strategy.

USER QUERY: "{user_query}"

AVAILABLE TOOLS:
{tools_description}

EXECUTION STRATEGIES:
1. "single_tool" - Query can be answered with one tool call
2. "tool_chain" - Query requires multiple connected tool calls
3. "clarification" - Query is unclear and needs user clarification

BUSINESS DOMAIN KNOWLEDGE:
- Purchase Request (PR) → Purchase Order (PO) → Goods Receipt (GR) → Movement/Inspection
- Use tool chains for "movement", "trace", "flow", or "complete process" queries
- Use single tools for specific document lookups with clear identifiers

ANALYSIS RULES:
- Extract exact document numbers/identifiers from user query
- For movement/trace queries: always use tool_chain strategy
- For simple document views: use single_tool strategy
- If query is vague or ambiguous: use clarification strategy

RESPONSE FORMAT (JSON ONLY):
{{
  "strategy": "single_tool|tool_chain|clarification",
  "reasoning": "Brief explanation of decision",
  "confidence": 0.85,
  
  // For single_tool strategy:
  "tool_name": "exact_tool_name",
  "parameters": {{"param": "value"}},
  
  // For tool_chain strategy:
  "tool_chain": [
    {{
      "tool_name": "first_tool",
      "parameters": {{"param": "value"}},
      "output_fields": ["field1", "field2"]
    }},
    {{
      "tool_name": "second_tool", 
      "parameters": {{"param": "{{field1}}"}},
      "output_fields": ["result_field"]
    }}
  ],
  
  // For clarification strategy:
  "clarification_message": "What specific information do you need?",
  "suggestions": ["suggestion1", "suggestion2"]
}}

CRITICAL: Respond with valid JSON only. Extract exact parameter values from the user query.
"""

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.config.azure_openai_deployment,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at analyzing user queries for tool orchestration. Always respond with valid JSON."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=1500
            )
            
            response_text = response.choices[0].message.content.strip()
            logger.info(f"🧠 LLM Strategy Response: {response_text}")
            
            # Parse JSON response
            try:
                strategy = json.loads(response_text)
                return strategy
            except json.JSONDecodeError as e:
                # Try to extract JSON from markdown code blocks
                import re
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
                if json_match:
                    strategy = json.loads(json_match.group(1))
                    return strategy
                else:
                    logger.error(f"❌ Failed to parse LLM response as JSON: {e}")
                    return {
                        "strategy": "error",
                        "error": f"Invalid JSON response from LLM: {str(e)}"
                    }
                    
        except Exception as e:
            logger.error(f"❌ Error calling LLM for strategy analysis: {e}")
            return {
                "strategy": "error", 
                "error": f"LLM analysis failed: {str(e)}"
            }

class MultiToolAgent:
    """
    Main agent class that coordinates FastMCP server, LLM orchestrator,
    and tool execution
    """
    
    def __init__(self, config: AgentConfig = None):
        self.config = config or AgentConfig()
        self.mcp_server = FastMCP("Multi-Tool Agent")
        self.orchestrator = None
        self.available_tools = []
        self._setup_mcp_server()
        
    def _setup_mcp_server(self):
        """Setup FastMCP server with agent capabilities"""
        
        # Register the main agent processing tool
        @create_tool(
            name="process_agent_request",
            description="Process complex requests using intelligent tool orchestration and LLM-driven decision making"
        )
        async def process_agent_request(query: str) -> Dict[str, Any]:
            """
            Main entry point for agent processing
            
            Args:
                query: Natural language query from user
                
            Returns:
                Dict containing execution results, tool chain, and metadata
            """
            return await self.process_request(query)
        
        # Register tool for getting agent capabilities
        @create_tool(
            name="get_agent_capabilities", 
            description="Get information about agent capabilities and available tools"
        )
        async def get_agent_capabilities() -> Dict[str, Any]:
            """Get agent capabilities and available tools"""
            return {
                "agent_type": "Multi-Tool Orchestrator Agent",
                "capabilities": [
                    "LLM-driven tool selection",
                    "Multi-tool chain execution", 
                    "Intelligent parameter mapping",
                    "Real-time execution monitoring",
                    "Error handling and recovery"
                ],
                "available_tools": len(self.available_tools),
                "max_chain_length": self.config.max_tool_chain_length,
                "llm_enabled": self.orchestrator and self.orchestrator.openai_client is not None
            }
        
        # Register tool execution status endpoint
        @create_tool(
            name="get_execution_status",
            description="Get the status of tool execution and agent performance metrics"
        )
        async def get_execution_status() -> Dict[str, Any]:
            """Get execution status and metrics"""
            return {
                "status": "active",
                "timestamp": datetime.now().isoformat(),
                "config": {
                    "max_chain_length": self.config.max_tool_chain_length,
                    "execution_timeout": self.config.execution_timeout
                }
            }
        
        logger.info("✅ FastMCP server configured with agent tools")
    
    async def initialize(self):
        """Initialize the agent with available tools"""
        # In a real implementation, this would discover tools from external sources
        # For now, we'll simulate the Ramco tools from the reference
        self.available_tools = self._get_simulated_tools()
        
        # Initialize orchestrator with available tools
        self.orchestrator = MultiToolOrchestrator(self.config, self.available_tools)
        
        logger.info(f"🚀 Multi-Tool Agent initialized with {len(self.available_tools)} tools")
    
    def _get_simulated_tools(self) -> List[Dict[str, Any]]:
        """
        Simulate available tools based on the reference implementation
        In a real system, this would dynamically discover tools
        """
        return [
            {
                "name": "view_purchase_order",
                "description": "Retrieve comprehensive purchase order information including supplier details, line items, pricing, delivery schedules, and approval status",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "po_number": {
                            "type": "string",
                            "description": "Purchase order number (e.g., 'JSLTEST46', 'PO123')",
                            "examples": ["JSLTEST46", "PO123", "ORD789"]
                        },
                        "amendment_no": {
                            "type": "string", 
                            "description": "Amendment number for the purchase order",
                            "default": "0"
                        }
                    },
                    "required": ["po_number"]
                }
            },
            {
                "name": "view_purchase_request", 
                "description": "Get purchase requisition details including requester information, approval workflow status, budget allocation, and item specifications",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "pr_number": {
                            "type": "string",
                            "description": "Purchase request number (e.g., 'PR123', 'REQ456')",
                            "examples": ["PR123", "REQ456", "JSLTEST46"]
                        }
                    },
                    "required": ["pr_number"]
                }
            },
            {
                "name": "search_purchase_orders",
                "description": "Search for purchase orders based on various criteria including PR numbers, PO dates, suppliers, etc.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "pr_no_from": {
                            "type": "string",
                            "description": "Purchase request number from"
                        },
                        "pr_no_to": {
                            "type": "string",
                            "description": "Purchase request number to" 
                        },
                        "po_no_from": {
                            "type": "string",
                            "description": "Purchase order number from"
                        },
                        "po_no_to": {
                            "type": "string",
                            "description": "Purchase order number to"
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "help_on_receipt_document",
                "description": "Search and retrieve receipt document details based on reference document numbers",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "ref_doc_no_from": {
                            "type": "string",
                            "description": "Reference document number from (typically PO number)"
                        },
                        "ref_doc_no_to": {
                            "type": "string", 
                            "description": "Reference document number to"
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "view_movement_details",
                "description": "Get stock movement and warehouse operation details for goods receipts",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "receipt_no": {
                            "type": "string",
                            "description": "Receipt number for movement details",
                            "examples": ["1041", "GR123", "REC456"]
                        }
                    },
                    "required": ["receipt_no"]
                }
            },
            {
                "name": "view_inspection_details",
                "description": "Retrieve inspection results and quality control data for goods receipts",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "receipt_no": {
                            "type": "string", 
                            "description": "Receipt number for inspection",
                            "examples": ["1041", "GR123", "REC456"]
                        }
                    },
                    "required": ["receipt_no"]
                }
            }
        ]
    
    async def process_request(self, user_query: str) -> Dict[str, Any]:
        """
        Main request processing method that orchestrates the entire workflow
        """
        import uuid
        session_id = str(uuid.uuid4())
        start_time = asyncio.get_event_loop().time()
        
        logger.info(f"🎯 Processing request [Session: {session_id[:8]}]: {user_query}")
        
        execution = AgentExecution(
            session_id=session_id,
            user_query=user_query,
            strategy="unknown",
            tool_executions=[]
        )
        
        try:
            # Step 1: Analyze execution strategy using LLM
            strategy = await self.orchestrator.analyze_execution_strategy(user_query)
            execution.strategy = strategy.get("strategy", "error")
            
            if strategy.get("strategy") == "error":
                execution.error_message = strategy.get("error", "Unknown strategy analysis error")
                execution.success = False
                return execution.to_dict()
            
            elif strategy.get("strategy") == "clarification":
                execution.success = True
                execution.final_result = {
                    "type": "clarification",
                    "message": strategy.get("clarification_message", "Please provide more details"),
                    "suggestions": strategy.get("suggestions", [])
                }
                return execution.to_dict()
            
            elif strategy.get("strategy") == "single_tool":
                # Execute single tool
                result = await self._execute_single_tool(
                    strategy.get("tool_name"),
                    strategy.get("parameters", {}),
                    execution
                )
                execution.final_result = result
                execution.success = True
                
            elif strategy.get("strategy") == "tool_chain":
                # Execute tool chain
                result = await self._execute_tool_chain(
                    strategy.get("tool_chain", []),
                    execution
                )
                execution.final_result = result
                execution.success = True
                
            else:
                execution.error_message = f"Unknown strategy: {strategy.get('strategy')}"
                execution.success = False
            
        except Exception as e:
            logger.error(f"❌ Error processing request: {e}")
            logger.error(traceback.format_exc())
            execution.error_message = str(e)
            execution.success = False
        
        finally:
            execution.total_execution_time = asyncio.get_event_loop().time() - start_time
            
        logger.info(f"✅ Request processed [Session: {session_id[:8]}] - Success: {execution.success}")
        return execution.to_dict()
    
    async def _execute_single_tool(self, tool_name: str, parameters: Dict[str, Any], 
                                   execution: AgentExecution) -> Dict[str, Any]:
        """Execute a single tool"""
        start_time = asyncio.get_event_loop().time()
        
        tool_exec = ToolExecution(
            tool_name=tool_name,
            parameters=parameters,
            timestamp=datetime.now().isoformat()
        )
        
        try:
            # Simulate tool execution (in real implementation, this would call actual tools)
            result = await self._simulate_tool_call(tool_name, parameters)
            tool_exec.result = result
            tool_exec.execution_time = asyncio.get_event_loop().time() - start_time
            
            execution.tool_executions.append(tool_exec)
            
            logger.info(f"🔧 Tool executed: {tool_name} - Success")
            return {
                "type": "single_tool_result",
                "tool_name": tool_name,
                "parameters": parameters,
                "result": result
            }
            
        except Exception as e:
            tool_exec.error = str(e)
            tool_exec.execution_time = asyncio.get_event_loop().time() - start_time
            execution.tool_executions.append(tool_exec)
            raise
    
    async def _execute_tool_chain(self, tool_chain: List[Dict[str, Any]], 
                                  execution: AgentExecution) -> Dict[str, Any]:
        """Execute a chain of tools with parameter mapping"""
        context = {}
        chain_results = []
        
        logger.info(f"⛓️  Executing tool chain with {len(tool_chain)} steps")
        
        for i, step in enumerate(tool_chain):
            tool_name = step.get("tool_name")
            parameters = step.get("parameters", {})
            
            # Resolve parameter placeholders from previous results
            resolved_params = self._resolve_parameters(parameters, context)
            
            start_time = asyncio.get_event_loop().time()
            tool_exec = ToolExecution(
                tool_name=tool_name,
                parameters=resolved_params,
                timestamp=datetime.now().isoformat()
            )
            
            try:
                # Execute tool
                result = await self._simulate_tool_call(tool_name, resolved_params)
                tool_exec.result = result
                tool_exec.execution_time = asyncio.get_event_loop().time() - start_time
                
                # Store result in context for next steps
                context[f"step_{i}_result"] = result
                
                # Store output fields if specified
                output_fields = step.get("output_fields", [])
                for field in output_fields:
                    if isinstance(result, dict) and field in result:
                        context[field] = result[field]
                    elif isinstance(result, list) and result:
                        # Extract field from first item if result is a list
                        if isinstance(result[0], dict) and field in result[0]:
                            context[field] = result[0][field]
                
                chain_results.append({
                    "step": i + 1,
                    "tool_name": tool_name,
                    "parameters": resolved_params,
                    "result": result
                })
                
                execution.tool_executions.append(tool_exec)
                logger.info(f"🔧 Chain step {i+1}/{len(tool_chain)}: {tool_name} - Success")
                
            except Exception as e:
                tool_exec.error = str(e)
                tool_exec.execution_time = asyncio.get_event_loop().time() - start_time
                execution.tool_executions.append(tool_exec)
                logger.error(f"❌ Chain step {i+1} failed: {tool_name} - {e}")
                raise
        
        return {
            "type": "tool_chain_result",
            "chain_results": chain_results,
            "final_context": context
        }
    
    def _resolve_parameters(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve parameter placeholders using context from previous tool executions"""
        resolved = {}
        
        for key, value in parameters.items():
            if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
                # Extract placeholder name
                placeholder = value[2:-2]
                if placeholder in context:
                    resolved[key] = context[placeholder]
                else:
                    logger.warning(f"⚠️  Placeholder '{placeholder}' not found in context")
                    resolved[key] = value  # Keep original if not found
            else:
                resolved[key] = value
                
        return resolved
    
    async def _simulate_tool_call(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulate tool execution (in real implementation, this would make actual API calls)
        """
        # Simulate processing time
        await asyncio.sleep(0.5)
        
        # Return simulated results based on tool type
        if tool_name == "view_purchase_order":
            return {
                "PoNo": parameters.get("po_number", "PO123"),
                "SupplierName": "Sample Supplier Ltd",
                "PoAmount": 15000.00,
                "PoStatus": "Approved",
                "LineItems": [
                    {"ItemCode": "ITEM001", "Quantity": 100, "UnitPrice": 150.00}
                ]
            }
        elif tool_name == "search_purchase_orders":
            return [
                {
                    "PoNo": "PO123",
                    "SupplierName": "Sample Supplier Ltd", 
                    "POAmount": 15000.00,
                    "PoDate": "2024-11-01"
                }
            ]
        elif tool_name == "help_on_receipt_document":
            return [
                {
                    "ReceiptNo": "GR001",
                    "RefDocNo": parameters.get("ref_doc_no_from", "PO123"),
                    "ReceivedQty": 100,
                    "AcceptedQty": 100
                }
            ]
        elif tool_name == "view_movement_details":
            return {
                "ReceiptNo": parameters.get("receipt_no", "GR001"),
                "MovementHistory": [
                    {"Date": "2024-11-01", "Location": "Warehouse A", "Quantity": 100}
                ],
                "CurrentLocation": "Warehouse A"
            }
        else:
            return {"message": f"Simulated result for {tool_name}", "parameters": parameters}
    
    async def run_server(self):
        """Run the FastMCP server"""
        await self.initialize()
        
        logger.info(f"🚀 Starting Multi-Tool Agent server on {self.config.mcp_host}:{self.config.mcp_port}")
        
        # Run FastMCP server
        await self.mcp_server.run(
            host=self.config.mcp_host,
            port=self.config.mcp_port
        )

# Example usage and testing
async def main():
    """Main function for testing the agent"""
    config = AgentConfig()
    agent = MultiToolAgent(config)
    
    # Test the agent directly (without running server)
    await agent.initialize()
    
    # Test queries
    test_queries = [
        "Show me details of purchase order PO123",
        "I need to trace the complete movement flow for PR REQ456", 
        "Find all receipts for PO JSLTEST46 and show movement details",
        "What is the status?"  # Should trigger clarification
    ]
    
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"🎯 Testing Query: {query}")
        print(f"{'='*60}")
        
        result = await agent.process_request(query)
        print(f"📊 Result: {json.dumps(result, indent=2)}")

if __name__ == "__main__":
    # Run the server
    config = AgentConfig()
    agent = MultiToolAgent(config)
    
    # Choose to run server or test
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        asyncio.run(main())
    else:
        asyncio.run(agent.run_server())