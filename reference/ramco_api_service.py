"""
Ramco API Service Layer
======================

Dedicated business logic layer for Ramco Purchase API integration.
Separated from MCP protocol implementation for better architecture.
"""

import asyncio
import json
import logging
import ssl
from datetime import datetime
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import aiohttp
from minimal_logger import minimal_logger as debug_logger, minimal_debug_method

logger = logging.getLogger(__name__)


class RamcoAPIService:
    """
    Business logic service for Ramco Purchase API operations.
    Handles all API communication independent of MCP protocol.
    """
    
    def __init__(self, config):
        debug_logger.log_method_entry("__init__", {"base_url": config.RAMCO_BASE_URL}, "RamcoAPIService")
        
        self.config = config
        self.base_url = config.RAMCO_BASE_URL
        self.auth_token = config.RAMCO_AUTH_TOKEN
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Load tool configuration from unified MCP schema
        try:
            from mcp_tools_schema_enhanced import get_all_api_configs
            self.tool_config = get_all_api_configs()
            debug_logger.log_decision(
                "Dynamic Config Loading",
                f"Loaded {len(self.tool_config)} API configurations from MCP schema",
                "RamcoAPIService"
            )
        except (ImportError, AttributeError) as e:
            debug_logger.log_error(
                e,
                "dynamic config loading - falling back to empty config",
                "RamcoAPIService"
            )
            # No fallback - all configuration should come from schema
            self.tool_config = {}
            raise ValueError("Unable to load API configurations from mcp_tools_schema_enhanced. All configurations must be defined in the schema.")
        
        debug_logger.log_method_exit("__init__", f"Service initialized with {len(self.tool_config)} operations", "RamcoAPIService")
    
    async def __aenter__(self):
        """Async context manager entry"""
        debug_logger.log_method_entry("__aenter__", {}, "RamcoAPIService")
        
        # Create SSL context that doesn't verify certificates for dev environment
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # Create connector with enhanced connection options
        connector = aiohttp.TCPConnector(
            ssl=ssl_context,
            limit=100,
            limit_per_host=30,
            ttl_dns_cache=300,
            use_dns_cache=True,
            keepalive_timeout=30,
            enable_cleanup_closed=True,
            force_close=False,
            family=0  # Allow both IPv4 and IPv6
        )
        
        # Create session with timeout settings
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout
        )
        
        debug_logger.log_method_exit("__aenter__", "Session created", "RamcoAPIService")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        debug_logger.log_method_entry("__aexit__", {"exc_type": exc_type}, "RamcoAPIService")
        
        if self.session:
            await self.session.close()
            debug_logger.log_execution_flow("Session closed", "Service cleanup completed")
        
        debug_logger.log_method_exit("__aexit__", "Cleanup completed", "RamcoAPIService")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get standard headers for API requests"""
        return {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json",
            "context-lang-id": str(self.config.DEFAULT_LANG_ID),
            "context-ou-id": str(self.config.DEFAULT_OU_ID), 
            "context-role-name": self.config.DEFAULT_ROLE_NAME
        }
    
    def _normalize_parameters(self, operation: str, raw_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize and map parameters for API call using dynamic configuration.
        
        Args:
            operation: The operation name (e.g., 'view_purchase_order')
            raw_params: Raw parameters from MCP call
            
        Returns:
            Normalized parameters ready for API call
        """
        debug_logger.log_method_entry("_normalize_parameters", {"operation": operation, "raw_params": raw_params}, "RamcoAPIService")
        
        if operation not in self.tool_config:
            raise ValueError(f"Unknown operation: {operation}")
        
        tool_config = self.tool_config[operation]
        api_params = {}
        
        # Get parameter normalization rules from schema
        try:
            from mcp_tools_schema_enhanced import get_parameter_normalization
            normalization_rules = get_parameter_normalization(operation)
        except (ImportError, AttributeError):
            # No dynamic normalization available
            normalization_rules = {}
        
        for param_name, param_value in raw_params.items():
            if param_name in tool_config["param_map"]:
                # Apply normalization rules from schema
                if param_name in normalization_rules:
                    rule = normalization_rules[param_name]
                    if rule == "uppercase":
                        normalized_value = str(param_value).upper()
                        if str(param_value) != normalized_value:
                            logger.info(f"📝 Normalized {param_name}: '{param_value}' → '{normalized_value}'")
                    elif rule == "lowercase":
                        normalized_value = str(param_value).lower()
                    elif rule == "strip":
                        normalized_value = str(param_value).strip()
                    elif rule == "numeric":
                        normalized_value = str(param_value).replace("-", "").replace(" ", "")
                    else:
                        normalized_value = param_value
                else:
                    normalized_value = param_value
                
                api_params[tool_config["param_map"][param_name]] = normalized_value
        
        debug_logger.log_method_exit("_normalize_parameters", api_params, "RamcoAPIService")
        return api_params
    
    def _apply_runtime_defaults(self, operation: str, original_params: Dict[str, Any], api_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply runtime defaults for missing parameters.
        Enhanced to use both runtime_defaults and schema_defaults.
        
        Args:
            operation: The operation name
            original_params: Original parameters from user
            api_params: Normalized API parameters
            
        Returns:
            API parameters with runtime defaults applied
        """
        from datetime import datetime
        
        debug_logger.log_method_entry("_apply_runtime_defaults", {"operation": operation, "original_params": original_params}, "RamcoAPIService")
        
        tool_config = self.tool_config[operation]
        runtime_defaults = tool_config.get("runtime_defaults", {})
        schema_defaults = tool_config.get("schema_defaults", {})
        param_map = tool_config["param_map"]
        final_params = api_params.copy()
        
        # First apply schema defaults (from JSON schema)
        for user_param, default_value in schema_defaults.items():
            # Check if user provided this parameter
            if user_param not in original_params:
                api_param_name = param_map.get(user_param)
                if api_param_name:
                    final_params[api_param_name] = default_value
                    debug_logger.log_decision(
                        "Schema Default Applied",
                        f"{user_param} → {api_param_name} = {default_value} (from schema)",
                        "RamcoAPIService"
                    )
        
        # Then apply runtime defaults (can override schema defaults)
        for user_param, default_value in runtime_defaults.items():
            # Check if user provided this parameter
            if user_param not in original_params:
                api_param_name = param_map.get(user_param)
                if api_param_name:
                    # Apply runtime default
                    if default_value == "CURRENT_DATE":
                        # Generate current date in YYYY-MM-DD format
                        current_date = datetime.now().strftime("%Y-%m-%d")
                        final_params[api_param_name] = current_date
                        debug_logger.log_decision(
                            "Runtime Default Applied",
                            f"{user_param} → {api_param_name} = {current_date} (CURRENT_DATE)",
                            "RamcoAPIService"
                        )
                    elif default_value == "CURRENT_TIMESTAMP":
                        # Generate current Unix timestamp
                        current_timestamp = int(datetime.now().timestamp())
                        final_params[api_param_name] = current_timestamp
                        debug_logger.log_decision(
                            "Runtime Default Applied",
                            f"{user_param} → {api_param_name} = {current_timestamp} (CURRENT_TIMESTAMP)",
                            "RamcoAPIService"
                        )
                    else:
                        # Static default value
                        final_params[api_param_name] = default_value
                        debug_logger.log_decision(
                            "Runtime Default Applied",
                            f"{user_param} → {api_param_name} = {default_value} (static)",
                            "RamcoAPIService"
                        )
        
        debug_logger.log_method_exit("_apply_runtime_defaults", final_params, "RamcoAPIService")
        return final_params
    
    async def call_api(self, operation: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make API call for specified operation.
        
        Args:
            operation: The operation name (e.g., 'view_purchase_order')
            parameters: Parameters for the operation
            
        Returns:
            API response data
            
        Raises:
            ValueError: For invalid operations or parameters
            ConnectionError: For network/connection issues
            aiohttp.ClientError: For HTTP errors
        """
        debug_logger.log_method_entry("call_api", {"operation": operation, "parameters": parameters}, "RamcoAPIService")
        
        if not self.session:
            error_msg = "Session not initialized. Use async context manager."
            debug_logger.log_error(RuntimeError(error_msg), "call_api")
            raise RuntimeError(error_msg)
        
        # Get operation configuration
        if operation not in self.tool_config:
            raise ValueError(f"Unknown operation: {operation}")
        
        tool_config = self.tool_config[operation]
        original_params = parameters.copy()  # Store original parameters for runtime defaults
        
        # Normalize parameters
        api_params = self._normalize_parameters(operation, parameters)
        
        # Apply runtime defaults for missing parameters
        api_params = self._apply_runtime_defaults(operation, original_params, api_params)
        
        debug_logger.log_decision(
            "Parameter Processing Complete",
            f"Raw params {parameters} processed to {api_params}",
            "RamcoAPIService"
        )
        
        if not api_params:
            debug_logger.log_error(
                ValueError(f"Parameter normalization failed for {operation}"),
                "parameter validation",
                "RamcoAPIService"
            )
            raise ValueError(f"Missing required parameters for {operation}")
        
        # Construct full URL
        service_path = tool_config["service_path"]
        endpoint = tool_config["endpoint"]
        full_url = f"{self.base_url.rstrip('/')}{service_path}{endpoint}"
        
        headers = self._get_headers()
        
        debug_logger.log_decision(
            "URL Construction", 
            f"Base: {self.base_url} + Service: {service_path} + Endpoint: {endpoint} = {full_url}",
            "RamcoAPIService"
        )
        
        debug_logger.log_execution_flow("Constructed API call", f"URL: {full_url}")
        debug_logger.log_api_request(full_url, api_params, headers)
        
        logger.info(f"📡 Calling Ramco API: {full_url}")
        logger.info(f"📋 Parameters: {api_params}")
        
        # Determine HTTP method and prepare request
        http_method = tool_config.get("http_method", "GET").upper()
        request_body = None
        
        if http_method == "POST":
            # Handle POST requests with request body
            request_body_template = tool_config.get("request_body_template")
            if request_body_template:
                request_body = self._build_request_body(request_body_template, original_params, api_params)
                debug_logger.log_decision(
                    "POST Request Body Built",
                    f"Template: {request_body_template} → Body: {request_body}",
                    "RamcoAPIService"
                )
            else:
                # No template, use api_params as JSON body
                request_body = api_params
                api_params = {}  # Clear params for POST (they go in body)
        
        try:
            debug_logger.log_execution_flow(f"Making HTTP {http_method} request", "Sending to Ramco API")
            
            # Retry logic for network connectivity issues
            max_retries = 3
            retry_delay = 1.0
            
            for attempt in range(max_retries):
                try:
                    # Make HTTP request based on method
                    if http_method == "POST":
                        async with self.session.post(full_url, headers=headers, json=request_body) as response:
                            return await self._process_response(response, operation, api_params, original_params)
                    else:  # GET and other methods
                        async with self.session.get(full_url, headers=headers, params=api_params) as response:
                            return await self._process_response(response, operation, api_params, original_params)
                            
                except (aiohttp.ClientConnectorError, aiohttp.ClientSSLError, OSError) as conn_error:
                    if attempt < max_retries - 1:
                        debug_logger.log_execution_flow(
                            f"Connection attempt {attempt + 1} failed, retrying in {retry_delay}s",
                            f"Error: {str(conn_error)}",
                            "RamcoAPIService"
                        )
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        continue
                    else:
                        # Last attempt failed, re-raise the error
                        raise conn_error
        
        except Exception as e:
            # Handle API errors
            debug_logger.log_error(e, f"call_api for {operation}", "RamcoAPIService")
            return await self._handle_api_error(e, operation, full_url, api_params)
    
    def _build_request_body(self, template: Dict[str, Any], original_params: Dict[str, Any], api_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build request body from template by substituting parameter values.
        
        Args:
            template: Request body template with {{parameter}} placeholders
            original_params: Original user parameters
            api_params: Normalized API parameters
            
        Returns:
            Request body with substituted values
        """
        debug_logger.log_method_entry("_build_request_body", {"template": template, "original_params": original_params}, "RamcoAPIService")
        
        # Convert template to JSON string for easier substitution
        template_str = json.dumps(template)
        
        # Create combined parameter map for substitution
        # Use both original parameter names and API parameter names
        all_params = original_params.copy()
        
        # Add API parameters (normalized) to allow both {{po_number}} and {{Ponomlt}} to work
        all_params.update(api_params)
        
        # Add mapping for user-friendly parameter names to work in templates
        user_to_api_mapping = {
            "po_number": api_params.get("Ponomlt"),
            "approval_date": api_params.get("Approvaldate"), 
            "mode_flag": api_params.get("Modeflag"),
            "timestamp": api_params.get("Timestampnew"),
            "remarks": api_params.get("Remarksml", ""),
            "flag": api_params.get("Flag", "Y")
        }
        
        # Add user-friendly mappings
        all_params.update(user_to_api_mapping)
        
        # Substitute parameters in template
        for param_name, param_value in all_params.items():
            if param_value is not None:
                placeholder = f"{{{{{param_name}}}}}"
                # Properly escape the value for JSON substitution
                # Convert to JSON string and remove quotes to get escaped value
                escaped_value = json.dumps(str(param_value))[1:-1]  # Remove surrounding quotes
                template_str = template_str.replace(placeholder, escaped_value)
        
        # Convert back to dict
        request_body = json.loads(template_str)
        
        debug_logger.log_method_exit("_build_request_body", request_body, "RamcoAPIService")
        return request_body
    
    async def _process_response(self, response, operation: str, api_params: Dict[str, Any], original_params: Dict[str, Any]) -> Dict[str, Any]:
        """Process HTTP response and handle status codes."""
        debug_logger.log_execution_flow("Received HTTP response", f"Status: {response.status}")
        
        logger.info(f"📊 Response Status: {response.status}")
        logger.info(f"🌐 Final URL: {response.url}")
        
        # Handle specific HTTP status codes
        if response.status == 204:
            error_msg = f"No data available for the specified parameters. Please verify the document number and try again."
            raise aiohttp.ClientResponseError(
                request_info=response.request_info,
                history=response.history,
                status=response.status,
                message=error_msg
            )
        elif response.status == 400:
            error_detail = await response.text()
            error_msg = f"Invalid request parameters. Please check your input and try again. Details: {error_detail}"
            raise aiohttp.ClientResponseError(
                request_info=response.request_info,
                history=response.history,
                status=response.status,
                message=error_msg
            )
        elif response.status == 401:
            error_msg = "Authentication failed. Please check your RAMCO_AUTH_TOKEN configuration."
            raise aiohttp.ClientResponseError(
                request_info=response.request_info,
                history=response.history,
                status=response.status,
                message=error_msg
            )
        elif response.status == 404:
            error_msg = "Document not found. Please verify the document number exists and try again."
            raise aiohttp.ClientResponseError(
                request_info=response.request_info,
                history=response.history,
                status=response.status,
                message=error_msg
            )
        elif response.status == 500:
            error_detail = await response.text()
            error_msg = f"Server error occurred. This usually means the document was not found or has invalid parameters. Response: {error_detail}"
            raise aiohttp.ClientResponseError(
                request_info=response.request_info,
                history=response.history,
                status=response.status,
                message=error_msg
            )
        elif response.status in [200, 201]:
            # Success - parse response
            response_data = await response.json()
            logger.info(f"✅ API Success: {len(str(response_data))} chars")
            
            # Validate response has data
            if not response_data or (isinstance(response_data, dict) and not any(response_data.values())):
                logger.warning(f"⚠️ Empty response data")
                raise ValueError("No data returned from API. The document may not exist or may be empty.")
            
            debug_logger.log_method_exit("_process_response", f"Success: {len(str(response_data))} chars", "RamcoAPIService")
            return response_data
        else:
            # Other HTTP errors
            response.raise_for_status()
    
    async def _handle_api_error(self, error: Exception, operation: str, full_url: str, api_params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle API errors consistently."""
        if isinstance(error, aiohttp.ClientConnectorError):
            logger.error(f"❌ Connection failed: {error}")
            error_msg = f"Cannot connect to Ramco API server at {full_url}. Please check your RAMCO_BASE_URL configuration and network connectivity."
            debug_logger.log_error(error, "call_api", "RamcoAPIService")
            raise ConnectionError(error_msg)
        elif isinstance(error, aiohttp.ClientResponseError):
            logger.error(f"❌ API response error: {error}")
            debug_logger.log_error(error, "call_api", "RamcoAPIService")
            raise error  # Re-raise with original message
        elif isinstance(error, aiohttp.ClientError):
            logger.error(f"❌ API client error: {error}")
            error_msg = f"API request failed: {str(error)}. Please check your configuration and try again."
            debug_logger.log_error(error, "call_api", "RamcoAPIService")
            raise ConnectionError(error_msg)
        elif isinstance(error, json.JSONDecodeError):
            logger.error(f"❌ Invalid JSON response: {error}")
            error_msg = "Invalid response format from API. The service may be unavailable."
            debug_logger.log_error(error, "call_api", "RamcoAPIService")
            raise ValueError(error_msg)
        else:
            logger.error(f"❌ Unexpected error: {error}")
            error_msg = f"Unexpected error occurred: {str(error)}"
            debug_logger.log_error(error, "call_api", "RamcoAPIService")
            raise ConnectionError(error_msg)
