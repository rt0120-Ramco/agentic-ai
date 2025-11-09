#!/usr/bin/env python3
"""
Ramco MCP Server - Independent HTTP Server
==========================================

This is the standalone MCP server for Ramco Purchase API integration.
Runs independently and accepts HTTP connections from MCP clients.
"""

import asyncio
import json
import logging
import os
import sys
import time
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import aiohttp
import jsonschema
from dotenv import load_dotenv
from openai import AsyncAzureOpenAI
from aiohttp import web
from aiohttp_cors import CorsConfig, setup as cors_setup

# Import API service (local copy)
from ramco_api_service import RamcoAPIService

# Import dashboard configuration and logger
from dashboard_config import DASHBOARD_DATA_DIR, ENABLE_DASHBOARD_LOGGING

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'tool-chain-dashboard'))

try:
    from tool_chain_logger import get_logger
    dashboard_logger = get_logger(data_directory=DASHBOARD_DATA_DIR) if ENABLE_DASHBOARD_LOGGING else None
    DASHBOARD_LOGGING_ENABLED = ENABLE_DASHBOARD_LOGGING and dashboard_logger is not None
    if DASHBOARD_LOGGING_ENABLED:
        print(f"✅ Dashboard logging enabled - Data path: {DASHBOARD_DATA_DIR}")
    else:
        print("⚠️  Dashboard logging disabled")
except ImportError as e:
    dashboard_logger = None
    DASHBOARD_LOGGING_ENABLED = False
    print(f"⚠️  Dashboard logger not available: {e}")

# Import enhanced MCP tools
from mcp_tools_schema_enhanced import (
    get_mcp_tools,
    get_mcp_tools_with_api_config, 
    get_tools_in_mcp_format as get_enhanced_tools
)

# Import tool chaining orchestrator
from tool_chain_orchestrator import ToolChainManager
import jsonschema

# Load environment variables
load_dotenv()

# Also try loading from parent directory where .env might be located
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

# Configure structured logging with both file and console output
def setup_logging():
    """Configure logging with file and console handlers"""
    log_dir = os.getenv("LOG_DIR", "logs")
    log_file = os.getenv("LOG_FILE", "ramco-mcp-server.log")
    # Set log level to DEBUG by default, allow override via LOG_LEVEL env variable
    log_level = os.getenv("LOG_LEVEL", "DEBUG").upper()
    
    # Create logs directory if it doesn't exist
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, log_file)
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_path, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Re-enable logging in case MinimalLogger disabled it
    logging.disable(logging.NOTSET)
    
    return log_path

# Setup logging and get log file path
log_file_path = setup_logging()
logger = logging.getLogger('ramco-mcp-server')
logger.info(f"Logging initialized - File: {log_file_path}")

# JSON-RPC Error Codes
class JSONRPCError:
    """Standard JSON-RPC error codes"""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    
    # Custom application error codes
    TOOL_NOT_FOUND = -32001
    TOOL_VALIDATION_ERROR = -32002
    API_ERROR = -32003
    NLP_ERROR = -32004
    CONFIGURATION_ERROR = -32005

# Configuration
class Config:
    """Configuration for the MCP server"""
    
    # HTTP Server Configuration
    HTTP_HOST = os.getenv("HTTP_HOST", "localhost")
    HTTP_PORT = int(os.getenv("HTTP_PORT", "8000"))
    
    # MCP Protocol Configuration
    MCP_PROTOCOL_VERSION = os.getenv("MCP_PROTOCOL_VERSION", "2025-03-26")
    
    # Logging Configuration
    LOG_DIR = os.getenv("LOG_DIR", "logs")
    LOG_FILE = os.getenv("LOG_FILE", "ramco-mcp-server.log")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_MAX_RESULT_SIZE = int(os.getenv("LOG_MAX_RESULT_SIZE", "1000"))  # Max chars to log for results
    
    # Azure OpenAI Configuration
    AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
    AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4")
    AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    
    # Ramco API Configuration
    RAMCO_BASE_URL = os.getenv("RAMCO_BASE_URL", "https://bebswarcnv13.pearl.com/coreapiops")
    RAMCO_AUTH_TOKEN = os.getenv("RAMCO_AUTH_TOKEN", "")
    
    # Default context values for Ramco APIs
    DEFAULT_LANG_ID = int(os.getenv("DEFAULT_LANG_ID", "1"))
    DEFAULT_OU_ID = int(os.getenv("DEFAULT_OU_ID", "1"))
    DEFAULT_ROLE_NAME = os.getenv("DEFAULT_ROLE_NAME", "admin")
    
    @classmethod
    def validate_environment(cls):
        """Validate required environment variables"""
        required_vars = {
            "RAMCO_BASE_URL": cls.RAMCO_BASE_URL,
            "RAMCO_AUTH_TOKEN": cls.RAMCO_AUTH_TOKEN
        }
        
        missing_vars = [var for var, value in required_vars.items() if not value]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Minimal logger for production
class MinimalLogger:
    def log_method_entry(self, method, params, cls):
        print(f"[{datetime.now().isoformat()}] {cls}.{method}: {params}")
    
    def log_method_exit(self, method, result, cls):
        print(f"[{datetime.now().isoformat()}] {cls}.{method}: {result}")
    
    def log_execution_flow(self, step, details, cls):
        print(f"[{datetime.now().isoformat()}] {cls}: {step} - {details}")

minimal_logger = MinimalLogger()

def validate_tool_arguments(tool_name: str, arguments: Dict[str, Any]) -> None:
    """
    Validate tool arguments against MCP tool schema.
    Raises ValueError for invalid arguments (becomes Protocol Error).
    """
    # Get the tool definition
    tool_def = None
    tools = get_mcp_tools()
    for tool in tools:
        if tool.name == tool_name:
            tool_def = tool
            break
    
    if not tool_def:
        error_msg = f"Unknown tool: {tool_name}"
        raise ValueError(error_msg)
    
    try:
        # Validate against the tool's inputSchema
        jsonschema.validate(instance=arguments, schema=tool_def.inputSchema)
    except jsonschema.ValidationError as e:
        error_msg = f"Invalid arguments for tool '{tool_name}': {e.message}"
        raise ValueError(error_msg)

class NaturalLanguageProcessor:
    """Enhanced NLP processor for MCP server."""
    
    def __init__(self, config, openai_client=None):
        """Initialize the NLP processor."""
        minimal_logger.log_method_entry("__init__", {}, "NaturalLanguageProcessor")
        
        # Use provided OpenAI client or create one
        self.client = openai_client
        
        if not self.client:
            # Check Azure OpenAI configuration
            api_key = config.AZURE_OPENAI_API_KEY
            endpoint = config.AZURE_OPENAI_ENDPOINT
            
            if not api_key or not endpoint:
                minimal_logger.log_execution_flow("Azure OpenAI not configured", "NLP will require configuration", "NaturalLanguageProcessor")
                self.client = None
            else:
                # Create Azure OpenAI client
                try:
                    from openai import AsyncAzureOpenAI
                    self.client = AsyncAzureOpenAI(
                        api_key=api_key,
                        api_version=config.AZURE_OPENAI_API_VERSION,
                        azure_endpoint=endpoint
                    )
                    minimal_logger.log_execution_flow("Azure OpenAI client created successfully", f"Endpoint: {endpoint}", "NaturalLanguageProcessor")
                except Exception as e:
                    minimal_logger.log_execution_flow(f"Failed to create Azure OpenAI client: {e}", "Client unavailable", "NaturalLanguageProcessor")
                    self.client = None
        else:
            minimal_logger.log_execution_flow("OpenAI client provided successfully", "NLP processor ready", "NaturalLanguageProcessor")
        
        self.config = config
        self.api_service = RamcoAPIService(config)
        minimal_logger.log_method_exit("__init__", "NLP processor initialized", "NaturalLanguageProcessor")
    
    async def process_query(self, user_query: str) -> Dict[str, Any]:
        """Process natural language query and execute appropriate tool."""
        minimal_logger.log_method_entry("process_query", {"user_query": user_query}, "NaturalLanguageProcessor")
        
        try:
            if not self.client:
                # No LLM available - return error instead of fallback
                minimal_logger.log_execution_flow("No LLM available", "Azure OpenAI must be configured", "NaturalLanguageProcessor")
                return {
                    "success": False,
                    "error": "Azure OpenAI is required for natural language processing. Please configure AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY in your environment.",
                    "original_query": user_query,
                    "configuration_needed": [
                        "AZURE_OPENAI_ENDPOINT",
                        "AZURE_OPENAI_API_KEY", 
                        "AZURE_OPENAI_DEPLOYMENT",
                        "AZURE_OPENAI_API_VERSION"
                    ]
                }
            
            # Get available tools and dynamic prompt section
            tools = get_mcp_tools()
            nlp_prompt = generate_nlp_prompt_section()
            
            # Create LLM prompt with dynamic tool information
            prompt = f"""
You are an AI assistant that helps with Ramco Purchase API operations. 

User query: "{user_query}"

{nlp_prompt}

INSTRUCTIONS:
1. Analyze the user query to identify document type keywords
2. Select the appropriate tool based on the keywords
3. Extract the document number/ID from the query and map it to the correct parameter name
4. Use ONLY the exact parameter names shown in the tool definitions above

For the query "{user_query}":

RESPOND WITH JSON IN THIS EXACT FORMAT:

If you can identify the tool and extract parameters:
{{
    "tool_name": "exact_tool_name_from_above",
    "parameters": {{"exact_parameter_name": "extracted_value"}},
    "confidence": 0.95,
    "reasoning": "brief explanation of tool selection and parameter extraction"
}}

CONFIDENCE SCORING GUIDELINES:
- 0.9-1.0: High confidence (exact keywords + complete parameters)
- 0.7-0.89: Medium confidence (good keywords + some parameters) 
- 0.5-0.69: Low confidence (partial keywords + minimal parameters)
- 0.0-0.49: Very low confidence (unclear or missing keywords)

If the query is unclear:
{{
    "needs_clarification": true,
    "question": "What type of document is this? Please specify the document type.",
    "suggested_queries": ["example query 1", "example query 2"]
}}

CRITICAL: Use exact parameter names from the tool definitions above!
"""

            # Log the prompt for debugging
            minimal_logger.log_execution_flow("LLM prompt constructed", f"Length: {len(prompt)}, Query: {user_query}", "NaturalLanguageProcessor")

            # Call LLM
            deployment = self.config.AZURE_OPENAI_DEPLOYMENT
            
            try:
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=deployment,
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant that processes purchase API requests."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0,
                        max_tokens=500
                    ),
                    timeout=30
                )
                
            except asyncio.TimeoutError:
                minimal_logger.log_execution_flow("LLM timeout", "process_query", "NaturalLanguageProcessor")
                return {
                    "success": False,
                    "error": "LLM processing timeout. Please try again.",
                    "original_query": user_query
                }
            except Exception as e:
                minimal_logger.log_execution_flow(f"LLM processing failed: {e}", "process_query", "NaturalLanguageProcessor")
                return {
                    "success": False,
                    "error": f"LLM processing failed: {str(e)}",
                    "original_query": user_query
                }
            
            llm_response = response.choices[0].message.content
            if not llm_response:
                return {
                    "success": False,
                    "error": "Empty response from LLM",
                    "original_query": user_query
                }
            
            llm_response = llm_response.strip()
            
            # Parse LLM response - handle markdown code blocks
            if llm_response.startswith("```json"):
                llm_response = llm_response.replace("```json", "", 1)
                if llm_response.endswith("```"):
                    llm_response = llm_response[:-3]
                llm_response = llm_response.strip()
            
            try:
                llm_result = json.loads(llm_response)
            except json.JSONDecodeError as e:
                minimal_logger.log_execution_flow(f"JSON parsing failed: {e}", "process_query", "NaturalLanguageProcessor")
                return {
                    "success": False,
                    "error": f"Invalid JSON response from LLM: {str(e)}",
                    "llm_response": llm_response[:500],
                    "original_query": user_query
                }
            
            # Check if clarification is needed
            if llm_result.get("needs_clarification", False):
                return {
                    "success": True,
                    "type": "clarification_needed",
                    "question": llm_result.get("question", "Please provide more specific information."),
                    "suggested_queries": llm_result.get("suggested_queries", []),
                    "original_query": user_query
                }
            
            # Validate and execute tool
            tool_name = llm_result.get("tool_name", "")
            parameters = llm_result.get("parameters", {})
            confidence = llm_result.get("confidence", 0.0)
            reasoning = llm_result.get("reasoning", "")
            
            minimal_logger.log_execution_flow("Tool execution", f"Tool: {tool_name}, Params: {parameters}", "NaturalLanguageProcessor")
            
            # Execute the tool
            if tool_name == "natural_language_query":
                # Recursive call protection
                return {"error": "Recursive natural_language_query call detected", "success": False}
            
            # Validate tool arguments
            validate_tool_arguments(tool_name, parameters)
            
            # Execute API call
            try:
                async with self.api_service as api:
                    api_result = await api.call_api(tool_name, parameters)
            except Exception as e:
                minimal_logger.log_execution_flow(f"API call failed: {e}", f"tool: {tool_name}", "NaturalLanguageProcessor")
                return {
                    "success": False,
                    "error": f"API call failed: {str(e)}",
                    "tool_name": tool_name,
                    "parameters": parameters,
                    "original_query": user_query
                }
            
            result = {
                "success": True,
                "type": "single_result",
                "tool_name": tool_name,
                "parameters": parameters,
                "result": api_result,
                "confidence": confidence,
                "llm_reasoning": reasoning,
                "original_query": user_query
            }
            
            minimal_logger.log_method_exit("process_query", "Query processed successfully", "NaturalLanguageProcessor")
            return result
            
        except Exception as e:
            minimal_logger.log_execution_flow(f"Process query error: {e}", "process_query", "NaturalLanguageProcessor")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "original_query": user_query
            }
    


class RamcoMCPServer:
    """Standalone MCP Server for Ramco Purchase API"""
    
    def __init__(self):
        self.app = None
        
        # Set up the OpenAI client and initialize services
        self.setup_openai_client()
    
    def truncate_for_log(self, data: Any, max_size: int = None) -> str:
        """
        Truncate large data for logging to prevent log bloat.
        
        Args:
            data: Data to convert to string and potentially truncate
            max_size: Maximum size in characters (defaults to Config.LOG_MAX_RESULT_SIZE)
        
        Returns:
            Truncated string representation of the data
        """
        if max_size is None:
            max_size = Config.LOG_MAX_RESULT_SIZE
        
        data_str = json.dumps(data, indent=2) if not isinstance(data, str) else data
        
        if len(data_str) <= max_size:
            return data_str
        
        # Truncate and add indication
        truncated = data_str[:max_size - 50]  # Leave room for truncation message
        return f"{truncated}... [TRUNCATED - Original size: {len(data_str)} chars]"

    def setup_openai_client(self):
        """Setup Azure OpenAI client if credentials are available."""
        if Config.AZURE_OPENAI_API_KEY and Config.AZURE_OPENAI_ENDPOINT:
            try:
                # Try minimal initialization to avoid compatibility issues
                import openai
                self.openai_client = AsyncAzureOpenAI(
                    api_key=Config.AZURE_OPENAI_API_KEY,
                    api_version=Config.AZURE_OPENAI_API_VERSION,
                    azure_endpoint=Config.AZURE_OPENAI_ENDPOINT
                )
                minimal_logger.log_execution_flow("Azure OpenAI client initialized successfully", "__init__", "RamcoMCPServer")
            except TypeError as te:
                # Handle specific proxies parameter issue
                minimal_logger.log_execution_flow(f"OpenAI client compatibility issue: {te}", "__init__", "RamcoMCPServer")
                try:
                    # Try alternative initialization without potential problematic parameters
                    self.openai_client = AsyncAzureOpenAI(
                        api_key=Config.AZURE_OPENAI_API_KEY,
                        azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
                        api_version=Config.AZURE_OPENAI_API_VERSION
                    )
                    minimal_logger.log_execution_flow("Azure OpenAI client initialized with alternative approach", "__init__", "RamcoMCPServer")
                except Exception as e2:
                    minimal_logger.log_execution_flow(f"OpenAI client initialization failed completely: {e2}", "__init__", "RamcoMCPServer")
                    self.openai_client = None
            except Exception as e:
                minimal_logger.log_execution_flow(f"OpenAI client initialization failed: {e}", "__init__", "RamcoMCPServer")
                self.openai_client = None
        
        # Initialize API service
        self.api_service = RamcoAPIService(Config)
        
        # Initialize NLP processor with OpenAI client
        self.nlp_processor = NaturalLanguageProcessor(Config, self.openai_client)
        
        # Initialize tool chaining manager
        if self.openai_client:
            # Create tool registry from enhanced tools for chaining
            tools_with_config = get_mcp_tools_with_api_config()
            self.tool_registry = {item["tool"].name: item for item in tools_with_config}
            self.tool_chain_manager = ToolChainManager(self.openai_client, self.tool_registry)
            minimal_logger.log_execution_flow("Tool chaining manager initialized", "__init__", "RamcoMCPServer")
        else:
            self.tool_chain_manager = None
            minimal_logger.log_execution_flow("Tool chaining manager not initialized - OpenAI client unavailable", "__init__", "RamcoMCPServer")
    
    async def execute_single_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single tool call. Used by both direct calls and tool chaining.
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Arguments for the tool
            
        Returns:
            Dict containing the tool execution result
        """
        try:
            # Validate arguments
            validate_tool_arguments(tool_name, arguments)
            
            # Execute API call
            async with self.api_service as api:
                result = await api.call_api(tool_name, arguments)
                return result
                
        except Exception as e:
            logger.error(f"Tool execution failed: {tool_name} - {e}")
            raise

    async def process_with_tool_chaining(self, user_query: str) -> Dict[str, Any]:
        """
        Process user query with centralized LLM logic in ToolChainManager.
        
        Args:
            user_query: Natural language query from user
            
        Returns:
            Dict containing the complete execution result
        """
        if not self.tool_chain_manager:
            return {
                "success": False,
                "error": "Tool chain manager not available - OpenAI client may be missing"
            }
        
        try:
            # Always delegate to centralized tool chain manager
            # It will decide: single tool, tool chain, or clarification
            result = await self.tool_chain_manager.process_user_query_with_chaining(
                user_query, 
                self.execute_single_tool
            )
            
            logger.info(f"Centralized query processing completed: {result.get('success', False)}")
            
            # Log to dashboard if available
            if DASHBOARD_LOGGING_ENABLED and dashboard_logger:
                try:
                    dashboard_logger.log_execution(
                        user_query=user_query,
                        strategy=result.get('type', 'unknown'),
                        tool_chain=result.get('tool_chain', []),
                        success=result.get('success', False),
                        execution_time_ms=result.get('execution_time_ms', 0),
                        error_message=result.get('error'),
                        steps_executed=result.get('steps_executed', []),
                        final_result=result.get('final_result')
                    )
                except Exception as e:
                    logger.warning(f"Dashboard logging failed: {e}")
            
            return result
            
        except Exception as e:
            logger.error(f"Centralized query processing failed: {e}")
            return {
                "success": False,
                "error": f"Query processing failed: {str(e)}",
                "user_query": user_query
            }

    def get_tools(self) -> List[Dict]:
        """Get all available tools"""
        return get_enhanced_tools()
    
    async def setup_http_app(self):
        """Setup the HTTP application with CORS"""
        app = web.Application()
        
        # Setup CORS - using defaults which allow all origins
        cors = cors_setup(app)
        
        # Add routes
        app.router.add_post('/mcp', self.handle_mcp_request)
        app.router.add_post('/tool-chain', self.handle_tool_chain_request)
        app.router.add_get('/health', self.handle_health)
        app.router.add_get('/tools', self.handle_tools)
        app.router.add_get('/', self.handle_info)
        
        # Add CORS to all routes
        for route in list(app.router.routes()):
            cors.add(route)
        
        self.app = app
        return app

    async def handle_tool_chain_request(self, request):
        """Handle direct tool chaining requests"""
        try:
            data = await request.json()
            user_query = data.get("query", "")
            
            if not user_query:
                return web.json_response({
                    "error": "Missing 'query' parameter"
                }, status=400)
            
            # Process with tool chaining
            result = await self.process_with_tool_chaining(user_query)
            
            return web.json_response(result)
            
        except Exception as e:
            logger.error(f"Tool chain request failed: {e}")
            return web.json_response({
                "error": f"Tool chain request failed: {str(e)}"
            }, status=500)
    
    async def handle_health(self, request):
        """Health check endpoint"""
        return web.json_response({
            "status": "healthy",
            "server": {
                "name": "RamcoMCPServer",
                "version": "1.0.0",
                "title": "Ramco Purchase API MCP Server"
            },
            "timestamp": datetime.now().isoformat()
        })
    
    async def handle_tools(self, request):
        """Tools listing endpoint"""
        response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "tools": self.get_tools()
            }
        }
        return web.json_response(response)
    
    async def handle_info(self, request):
        """Server information endpoint"""
        return web.json_response({
            "name": "Ramco MCP Server",
            "version": "1.0.0",
            "description": "Standalone MCP server for Ramco Purchase API integration",
            "endpoints": [
                "POST /mcp - MCP JSON-RPC protocol",
                "GET /health - Health check",
                "GET /tools - List available tools",
                "GET / - Server information"
            ],
            "tools_count": len(self.get_tools())
        })
    
    async def handle_mcp_request(self, request):
        """Handle MCP JSON-RPC requests with comprehensive logging and error handling"""
        request_start_time = time.time()
        request_id = None
        method = None
        
        try:
            # Parse JSON request
            try:
                data = await request.json()
            except json.JSONDecodeError as e:
                logger.error("JSON parse error", extra={
                    "error": str(e),
                    "client_ip": request.remote,
                    "content_type": request.content_type
                })
                return web.json_response({
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": JSONRPCError.PARSE_ERROR,
                        "message": "Parse error",
                        "data": f"Invalid JSON: {str(e)}"
                    }
                }, status=400)
            
            # Extract request details
            method = data.get("method")
            params = data.get("params", {})
            request_id = data.get("id")
            
            # Validate JSON-RPC structure
            if "jsonrpc" not in data or data["jsonrpc"] != "2.0":
                logger.error("Invalid JSON-RPC request", extra={
                    "request_data": data,
                    "client_ip": request.remote
                })
                return web.json_response({
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": JSONRPCError.INVALID_REQUEST,
                        "message": "Invalid Request",
                        "data": "Missing or invalid 'jsonrpc' field"
                    }
                }, status=400)
            
            if not method:
                logger.error("Missing method in request", extra={
                    "request_data": data,
                    "client_ip": request.remote
                })
                return web.json_response({
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": JSONRPCError.INVALID_REQUEST,
                        "message": "Invalid Request",
                        "data": "Missing 'method' field"
                    }
                }, status=400)
            
            # Log request details
            logger.info("MCP request received", extra={
                "method": method,
                "request_id": request_id,
                "params_size": len(json.dumps(params)) if params else 0,
                "client_ip": request.remote,
                "user_agent": request.headers.get("User-Agent")
            })
            
            minimal_logger.log_method_entry("handle_mcp_request", f"Method: {method}", "RamcoMCPServer")
            
            # Route request to appropriate handler
            response = None
            if method == "initialize":
                response = await self.handle_initialize(params)
            elif method == "notifications/initialized":
                response = None  # No response for notifications
            elif method == "tools/list":
                response = await self.handle_list_tools()
            elif method == "tools/call":
                response = await self.handle_call_tool(params, request_id)
            else:
                logger.warning("Unknown method requested", extra={
                    "method": method,
                    "request_id": request_id,
                    "client_ip": request.remote
                })
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": JSONRPCError.METHOD_NOT_FOUND,
                        "message": f"Method not found: {method}",
                        "data": {
                            "available_methods": ["initialize", "notifications/initialized", "tools/list", "tools/call"],
                            "requested_method": method
                        }
                    }
                }
            
            # Handle notification (no response)
            if response is None:
                logger.info("Notification processed", extra={
                    "method": method,
                    "request_id": request_id,
                    "processing_time": time.time() - request_start_time
                })
                return web.Response(text="", status=204)
            
            # Add request ID to response
            response["id"] = request_id
            
            # Log successful response
            processing_time = time.time() - request_start_time
            logger.info("MCP request processed successfully", extra={
                "method": method,
                "request_id": request_id,
                "processing_time": processing_time,
                "response_size": len(json.dumps(response)),
                "success": "error" not in response
            })
            
            minimal_logger.log_method_exit("handle_mcp_request", "Success", "RamcoMCPServer")
            return web.json_response(response)
            
        except Exception as e:
            # Log unexpected errors
            processing_time = time.time() - request_start_time
            logger.error("Unexpected error in MCP request handler", extra={
                "method": method,
                "request_id": request_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc(),
                "processing_time": processing_time,
                "client_ip": getattr(request, 'remote', 'unknown')
            })
            
            minimal_logger.log_execution_flow("handle_mcp_request", f"Error: {e}", "RamcoMCPServer")
            
            error_response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": JSONRPCError.INTERNAL_ERROR,
                    "message": "Internal error",
                    "data": {
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "method": method
                    }
                }
            }
            return web.json_response(error_response, status=500)
    
    async def handle_initialize(self, params):
        """Handle MCP initialize request"""
        return {
            "jsonrpc": "2.0",
            "result": {
                "protocolVersion": Config.MCP_PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {},
                    "resources": {},
                    "prompts": {}
                },
                "serverInfo": {
                    "name": "RamcoMCPServer",
                    "version": "1.0.0",
                    "title": "Ramco Purchase API MCP Server"
                },
                "instructions": "Welcome to Ramco Purchase API Server! Use tools/list to see available operations."
            }
        }
    
    async def handle_list_tools(self):
        """Handle tools/list request"""
        return {
            "jsonrpc": "2.0",
            "result": {
                "tools": self.get_tools()
            }
        }
    
    async def handle_call_tool(self, params, request_id=None):
        """Handle tools/call request with comprehensive logging and error handling"""
        tool_start_time = time.time()
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        # Validate required parameters
        if not tool_name:
            logger.error("Tool call missing name parameter", extra={
                "request_id": request_id,
                "params": params
            })
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": JSONRPCError.INVALID_PARAMS,
                    "message": "Invalid params",
                    "data": "Missing required parameter: 'name'"
                }
            }
        
        # Log tool execution start
        logger.info("Tool execution started", extra={
            "tool_name": tool_name,
            "request_id": request_id,
            "arguments": arguments,
            "arguments_size": len(json.dumps(arguments))
        })
        
        minimal_logger.log_execution_flow(f"Calling tool: {tool_name}", f"Arguments: {arguments}", "RamcoMCPServer")
        
        try:
            result = None
            tool_execution_time = None
            
            # Handle natural language query with real NLP processing
            if tool_name == "natural_language_query":
                query = arguments.get("query", "")
                
                if not query:
                    logger.warning("Natural language query missing query parameter", extra={
                        "tool_name": tool_name,
                        "request_id": request_id,
                        "arguments": arguments
                    })
                    return {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": JSONRPCError.INVALID_PARAMS,
                            "message": "Invalid params",
                            "data": "Missing required parameter: 'query' for natural_language_query"
                        }
                    }
                
                # Log NLP processing start
                logger.info("NLP processing started", extra={
                    "tool_name": tool_name,
                    "request_id": request_id,
                    "query": query,
                    "query_length": len(query)
                })
                
                nlp_start_time = time.time()
                
                # Use tool chaining for intelligent query processing
                result = await self.process_with_tool_chaining(query)
                tool_execution_time = time.time() - nlp_start_time
                
                logger.info("Query processing completed", extra={
                    "tool_name": tool_name,
                    "request_id": request_id,
                    "query": query,
                    "success": result.get("success", False) if isinstance(result, dict) else False,
                    "execution_time": tool_execution_time,
                    "result_type": result.get("type") if isinstance(result, dict) else type(result).__name__,
                    "tool_chain": result.get("tool_chain", []) if isinstance(result, dict) else []
                })
            else:
                # Direct tool call - validate arguments first
                api_start_time = time.time()
                
                logger.info("Direct tool call started", extra={
                    "tool_name": tool_name,
                    "request_id": request_id,
                    "arguments": arguments
                })
                
                try:
                    validate_tool_arguments(tool_name, arguments)
                except Exception as validation_error:
                    logger.warning("Tool argument validation failed", extra={
                        "tool_name": tool_name,
                        "request_id": request_id,
                        "arguments": arguments,
                        "validation_error": str(validation_error)
                    })
                    return {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": JSONRPCError.TOOL_VALIDATION_ERROR,
                            "message": "Tool argument validation failed",
                            "data": {
                                "tool": tool_name,
                                "arguments": arguments,
                                "validation_error": str(validation_error)
                            }
                        }
                    }
                
                # Execute API call
                try:
                    async with self.api_service as api:
                        result = await api.call_api(tool_name, arguments)
                        tool_execution_time = time.time() - api_start_time
                        
                        logger.info("Direct tool call completed", extra={
                            "tool_name": tool_name,
                            "request_id": request_id,
                            "arguments": arguments,
                            "execution_time": tool_execution_time,
                            "result_size": len(json.dumps(result)) if result else 0,
                            "success": True
                        })
                        
                except Exception as api_error:
                    tool_execution_time = time.time() - api_start_time
                    logger.error("API call failed", extra={
                        "tool_name": tool_name,
                        "request_id": request_id,
                        "arguments": arguments,
                        "execution_time": tool_execution_time,
                        "api_error": str(api_error),
                        "error_type": type(api_error).__name__
                    })
                    return {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": JSONRPCError.API_ERROR,
                            "message": "API call failed",
                            "data": {
                                "tool": tool_name,
                                "arguments": arguments,
                                "api_error": str(api_error),
                                "error_type": type(api_error).__name__
                            }
                        }
                    }
            
            # Log successful tool execution with truncated result for large responses
            total_execution_time = time.time() - tool_start_time
            result_size = len(json.dumps(result)) if result else 0
            
            # Create log entry with truncated result if it's large
            log_extra = {
                "tool_name": tool_name,
                "request_id": request_id,
                "total_execution_time": total_execution_time,
                "tool_execution_time": tool_execution_time,
                "result_size": result_size,
                "success": True
            }
            
            # Add truncated result for debugging (only if result exists and isn't too large)
            if result and result_size < Config.LOG_MAX_RESULT_SIZE * 2:  # Only log if reasonable size
                log_extra["result_preview"] = self.truncate_for_log(result)
            
            logger.info("Tool execution completed successfully", extra=log_extra)
            
            return {
                "jsonrpc": "2.0",
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2)
                        }
                    ]
                }
            }
            
        except Exception as e:
            # Log unexpected errors in tool execution
            total_execution_time = time.time() - tool_start_time
            logger.error("Unexpected error in tool execution", extra={
                "tool_name": tool_name,
                "request_id": request_id,
                "arguments": arguments,
                "total_execution_time": total_execution_time,
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc()
            })
            
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": JSONRPCError.INTERNAL_ERROR,
                    "message": "Tool execution failed",
                    "data": {
                        "tool": tool_name,
                        "arguments": arguments,
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                }
            }
    
    async def start_server(self):
        """Start the HTTP server"""
        minimal_logger.log_execution_flow("start_server", "Setting up HTTP application", "RamcoMCPServer")
        
        app = await self.setup_http_app()
        runner = web.AppRunner(app)
        await runner.setup()
        
        site = web.TCPSite(runner, Config.HTTP_HOST, Config.HTTP_PORT)
        await site.start()
        
        print(f"🚀 Ramco MCP Server started on http://{Config.HTTP_HOST}:{Config.HTTP_PORT}")
        print(f"📋 Available endpoints:")
        print(f"   - POST http://{Config.HTTP_HOST}:{Config.HTTP_PORT}/mcp (MCP JSON-RPC)")
        print(f"   - GET  http://{Config.HTTP_HOST}:{Config.HTTP_PORT}/health (Health check)")
        print(f"   - GET  http://{Config.HTTP_HOST}:{Config.HTTP_PORT}/tools (List tools)")
        print(f"   - GET  http://{Config.HTTP_HOST}:{Config.HTTP_PORT}/ (Server info)")
        print(f"🔧 Loaded {len(self.get_tools())} tools")
        
        minimal_logger.log_method_exit("start_server", "HTTP server started", "RamcoMCPServer")
        
        # Keep the server running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Shutting down server...")
            await runner.cleanup()
            minimal_logger.log_execution_flow("start_server", "HTTP server stopped", "RamcoMCPServer")
    
    async def run(self):
        """Run the MCP server"""
        print("Starting Ramco MCP Server...")
        
        # Validate environment first
        try:
            Config.validate_environment()
            print("✅ Environment validation passed")
        except ValueError as e:
            print(f"❌ Environment validation failed: {e}")
            print("\n💡 Please check your .env file or environment variables:")
            print("   - RAMCO_BASE_URL: Your Ramco API base URL")
            print("   - RAMCO_AUTH_TOKEN: Your Ramco API authentication token")
            return
        
        # Start the HTTP server
        await self.start_server()

async def main():
    """Main function"""
    server = RamcoMCPServer()
    await server.run()

if __name__ == "__main__":
    asyncio.run(main())