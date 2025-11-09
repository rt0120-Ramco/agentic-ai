"""
Multi-Tool Agent Client Example
==============================

This client demonstrates how to interact with the Multi-Tool Orchestrator Agent
using FastMCP protocol. It shows various types of queries and how the agent
intelligently handles them.
"""

import asyncio
import json
import logging
from typing import Dict, Any
import aiohttp
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AgentClient:
    """Client for interacting with the Multi-Tool Agent"""
    
    def __init__(self, agent_url: str = "http://localhost:8001"):
        self.agent_url = agent_url
        self.session = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def send_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send MCP request to the agent"""
        request_data = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params
        }
        
        try:
            async with self.session.post(
                f"{self.agent_url}/mcp",
                json=request_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("result", {})
                else:
                    error_text = await response.text()
                    raise Exception(f"HTTP {response.status}: {error_text}")
        except Exception as e:
            logger.error(f"❌ Request failed: {e}")
            raise
    
    async def process_agent_request(self, query: str) -> Dict[str, Any]:
        """Send a query to the agent for processing"""
        return await self.send_request("tools/call", {
            "name": "process_agent_request",
            "arguments": {"query": query}
        })
    
    async def get_agent_capabilities(self) -> Dict[str, Any]:
        """Get agent capabilities"""
        return await self.send_request("tools/call", {
            "name": "get_agent_capabilities",
            "arguments": {}
        })
    
    async def get_execution_status(self) -> Dict[str, Any]:
        """Get execution status"""
        return await self.send_request("tools/call", {
            "name": "get_execution_status", 
            "arguments": {}
        })

async def run_demo():
    """Run demonstration of the Multi-Tool Agent"""
    
    print("🤖 Multi-Tool Agent Client Demo")
    print("=" * 50)
    
    async with AgentClient() as client:
        
        # Test 1: Get agent capabilities
        print("\n📋 Getting Agent Capabilities...")
        try:
            capabilities = await client.get_agent_capabilities()
            print(f"✅ Capabilities: {json.dumps(capabilities, indent=2)}")
        except Exception as e:
            print(f"❌ Failed to get capabilities: {e}")
        
        # Test 2: Get execution status
        print("\n📊 Getting Execution Status...")
        try:
            status = await client.get_execution_status()
            print(f"✅ Status: {json.dumps(status, indent=2)}")
        except Exception as e:
            print(f"❌ Failed to get status: {e}")
        
        # Test queries for different scenarios
        test_scenarios = [
            {
                "name": "Single Tool Query",
                "query": "Show me details of purchase order JSLTEST46",
                "expected": "Should use single tool strategy"
            },
            {
                "name": "Tool Chain Query", 
                "query": "I need to trace the complete movement flow for purchase request PR123",
                "expected": "Should use tool chain strategy"
            },
            {
                "name": "Complex Workflow",
                "query": "Find all receipts for PO JSLTEST46 and show their movement and inspection details",
                "expected": "Should use multi-step tool chain"
            },
            {
                "name": "Ambiguous Query",
                "query": "Show me something about purchases",
                "expected": "Should request clarification"
            },
            {
                "name": "Movement Trace Query",
                "query": "Trace all movements for receipt GR001 including inspection results",
                "expected": "Should chain movement and inspection tools"
            }
        ]
        
        # Execute test scenarios
        for i, scenario in enumerate(test_scenarios, 1):
            print(f"\n🎯 Test {i}: {scenario['name']}")
            print(f"Query: '{scenario['query']}'")
            print(f"Expected: {scenario['expected']}")
            print("-" * 60)
            
            try:
                result = await client.process_agent_request(scenario['query'])
                
                # Parse the result (it comes wrapped in content)
                if 'content' in result and result['content']:
                    content = result['content'][0].get('text', '{}')
                    parsed_result = json.loads(content)
                    
                    # Display key information
                    print(f"✅ Strategy: {parsed_result.get('strategy', 'unknown')}")
                    print(f"📊 Success: {parsed_result.get('success', False)}")
                    print(f"⏱️  Execution Time: {parsed_result.get('total_execution_time', 0):.3f}s")
                    
                    # Show tool executions
                    tool_executions = parsed_result.get('tool_executions', [])
                    if tool_executions:
                        print(f"🔧 Tools Used: {len(tool_executions)}")
                        for j, exec in enumerate(tool_executions, 1):
                            tool_name = exec.get('tool_name', 'unknown')
                            exec_time = exec.get('execution_time', 0)
                            success = 'error' not in exec or exec['error'] is None
                            print(f"   {j}. {tool_name} ({exec_time:.3f}s) - {'✅' if success else '❌'}")
                    
                    # Show final result type
                    final_result = parsed_result.get('final_result', {})
                    if final_result:
                        result_type = final_result.get('type', 'unknown')
                        print(f"📄 Result Type: {result_type}")
                        
                        if result_type == 'clarification':
                            print(f"💬 Clarification: {final_result.get('message', '')}")
                            suggestions = final_result.get('suggestions', [])
                            if suggestions:
                                print(f"💡 Suggestions: {', '.join(suggestions)}")
                    
                    # Show any errors
                    if parsed_result.get('error_message'):
                        print(f"❌ Error: {parsed_result['error_message']}")
                        
                else:
                    print(f"📄 Raw Result: {json.dumps(result, indent=2)}")
                    
            except Exception as e:
                print(f"❌ Test failed: {e}")
            
            print()  # Add spacing between tests
        
        print("🎉 Demo completed!")

async def interactive_mode():
    """Run interactive mode for testing queries"""
    
    print("🤖 Multi-Tool Agent - Interactive Mode")
    print("Type 'quit' to exit, 'help' for commands")
    print("=" * 50)
    
    async with AgentClient() as client:
        
        while True:
            try:
                query = input("\n🎯 Enter your query: ").strip()
                
                if query.lower() in ['quit', 'exit', 'q']:
                    print("👋 Goodbye!")
                    break
                
                if query.lower() in ['help', 'h']:
                    print("\n📋 Available commands:")
                    print("  - Any natural language query (e.g., 'show PO details for JSLTEST46')")
                    print("  - 'capabilities' - Show agent capabilities")
                    print("  - 'status' - Show execution status") 
                    print("  - 'help' or 'h' - Show this help")
                    print("  - 'quit' or 'q' - Exit")
                    continue
                
                if query.lower() == 'capabilities':
                    result = await client.get_agent_capabilities()
                    print(f"📋 Agent Capabilities:\n{json.dumps(result, indent=2)}")
                    continue
                
                if query.lower() == 'status':
                    result = await client.get_execution_status()
                    print(f"📊 Execution Status:\n{json.dumps(result, indent=2)}")
                    continue
                
                if not query:
                    continue
                
                print(f"\n🔄 Processing: '{query}'")
                start_time = datetime.now()
                
                result = await client.process_agent_request(query)
                
                processing_time = (datetime.now() - start_time).total_seconds()
                print(f"⏱️  Client Processing Time: {processing_time:.3f}s")
                
                # Parse and display result
                if 'content' in result and result['content']:
                    content = result['content'][0].get('text', '{}')
                    parsed_result = json.loads(content)
                    
                    print(f"\n📊 Strategy: {parsed_result.get('strategy', 'unknown')}")
                    print(f"✅ Success: {parsed_result.get('success', False)}")
                    
                    final_result = parsed_result.get('final_result', {})
                    if final_result:
                        print(f"📄 Result: {json.dumps(final_result, indent=2)}")
                else:
                    print(f"📄 Raw Result: {json.dumps(result, indent=2)}")
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "interactive":
        asyncio.run(interactive_mode())
    else:
        asyncio.run(run_demo())