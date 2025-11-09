"""
Standalone Demo for Multi-Tool Agent
====================================

This demo runs the agent in standalone mode without external dependencies,
showing how the LLM orchestrator analyzes queries and plans tool execution.
"""

import asyncio
import json
from datetime import datetime
from multi_tool_agent import MultiToolAgent, AgentConfig

async def demo_agent_analysis():
    """Demonstrate agent query analysis without running the full server"""
    
    print("🤖 Multi-Tool Agent - Standalone Demo")
    print("=" * 50)
    
    # Create agent configuration
    config = AgentConfig()
    config.azure_openai_endpoint = ""  # Disable LLM for demo
    config.azure_openai_api_key = ""
    
    # Initialize agent
    agent = MultiToolAgent(config)
    await agent.initialize()
    
    print(f"✅ Agent initialized with {len(agent.available_tools)} tools")
    
    # Test scenarios without LLM (simulated responses)
    test_scenarios = [
        {
            "query": "Show me details of purchase order JSLTEST46",
            "expected_strategy": "single_tool",
            "expected_tool": "view_purchase_order"
        },
        {
            "query": "Trace movement flow for purchase request PR123", 
            "expected_strategy": "tool_chain",
            "expected_tools": ["view_purchase_request", "search_purchase_orders", "help_on_receipt_document", "view_movement_details"]
        },
        {
            "query": "What is happening?",
            "expected_strategy": "clarification",
            "expected_response": "Please provide more specific information"
        }
    ]
    
    print(f"\n🧪 Testing {len(test_scenarios)} scenarios...")
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n📋 Test {i}: {scenario['query']}")
        print("-" * 40)
        
        # Simulate strategy analysis (without LLM)
        simulated_strategy = simulate_strategy_analysis(scenario)
        
        print(f"🎯 Expected Strategy: {scenario['expected_strategy']}")
        print(f"🤖 Simulated Strategy: {simulated_strategy.get('strategy', 'unknown')}")
        
        if simulated_strategy.get('strategy') == 'single_tool':
            print(f"🔧 Tool: {simulated_strategy.get('tool_name', 'N/A')}")
            print(f"📝 Parameters: {simulated_strategy.get('parameters', {})}")
        
        elif simulated_strategy.get('strategy') == 'tool_chain':
            chain = simulated_strategy.get('tool_chain', [])
            print(f"⛓️  Tool Chain ({len(chain)} steps):")
            for j, step in enumerate(chain, 1):
                print(f"   {j}. {step.get('tool_name', 'unknown')}")
        
        elif simulated_strategy.get('strategy') == 'clarification':
            print(f"💬 Message: {simulated_strategy.get('clarification_message', 'N/A')}")
        
        # Simulate execution
        print(f"⏱️  Simulated execution time: 0.{i}s")
        print("✅ Simulation successful")

def simulate_strategy_analysis(scenario):
    """Simulate LLM strategy analysis based on query patterns"""
    query = scenario['query'].lower()
    
    # Simple pattern matching for demonstration
    if 'details of purchase order' in query or 'show po' in query:
        # Extract PO number (simplified)
        words = scenario['query'].split()
        po_number = None
        for word in words:
            if word.upper().startswith(('PO', 'JSL', 'ORD')):
                po_number = word
                break
        
        return {
            "strategy": "single_tool",
            "reasoning": "Query requests specific PO details",
            "confidence": 0.9,
            "tool_name": "view_purchase_order", 
            "parameters": {"po_number": po_number or "JSLTEST46"}
        }
    
    elif any(word in query for word in ['trace', 'movement', 'flow', 'complete']):
        return {
            "strategy": "tool_chain",
            "reasoning": "Query requires tracing through multiple steps",
            "confidence": 0.85,
            "tool_chain": [
                {
                    "tool_name": "view_purchase_request",
                    "parameters": {"pr_number": "PR123"},
                    "output_fields": ["PrNo"]
                },
                {
                    "tool_name": "search_purchase_orders", 
                    "parameters": {"pr_no_from": "{{PrNo}}"},
                    "output_fields": ["PoNo"]
                },
                {
                    "tool_name": "help_on_receipt_document",
                    "parameters": {"ref_doc_no_from": "{{PoNo}}"},
                    "output_fields": ["ReceiptNo"]
                },
                {
                    "tool_name": "view_movement_details",
                    "parameters": {"receipt_no": "{{ReceiptNo}}"},
                    "output_fields": []
                }
            ]
        }
    
    else:
        return {
            "strategy": "clarification",
            "reasoning": "Query is too vague or ambiguous",
            "confidence": 0.6,
            "clarification_message": "Could you please provide more specific information about what you're looking for?",
            "suggestions": [
                "View specific purchase order details",
                "Search for purchase orders",
                "Trace document flow"
            ]
        }

async def demo_tool_execution():
    """Demonstrate tool execution simulation"""
    
    print(f"\n🔧 Tool Execution Demo")
    print("=" * 30)
    
    # Simulate single tool execution
    print("📋 Single Tool Execution:")
    result = {
        "tool_name": "view_purchase_order",
        "parameters": {"po_number": "JSLTEST46"},
        "result": {
            "PoNo": "JSLTEST46",
            "SupplierName": "Demo Supplier Ltd",
            "PoAmount": 25000.00,
            "PoStatus": "Approved",
            "LineItems": [
                {"ItemCode": "ITEM001", "Quantity": 50, "UnitPrice": 500.00}
            ]
        },
        "execution_time": 0.5,
        "success": True
    }
    
    print(f"   Tool: {result['tool_name']}")
    print(f"   Parameters: {result['parameters']}")
    print(f"   Result: {json.dumps(result['result'], indent=4)}")
    print(f"   Time: {result['execution_time']}s")
    
    # Simulate tool chain execution
    print(f"\n⛓️  Tool Chain Execution:")
    chain_results = [
        {"step": 1, "tool": "view_purchase_request", "time": 0.3},
        {"step": 2, "tool": "search_purchase_orders", "time": 0.4}, 
        {"step": 3, "tool": "help_on_receipt_document", "time": 0.6},
        {"step": 4, "tool": "view_movement_details", "time": 0.5}
    ]
    
    total_time = sum(r['time'] for r in chain_results)
    
    for result in chain_results:
        print(f"   Step {result['step']}: {result['tool']} ({result['time']}s) ✅")
    
    print(f"   Total Chain Time: {total_time}s")

async def main():
    """Main demo function"""
    
    print("🚀 Starting Multi-Tool Agent Demo")
    print("This demo shows agent capabilities without external dependencies")
    print()
    
    # Demo 1: Agent Analysis
    await demo_agent_analysis()
    
    # Demo 2: Tool Execution
    await demo_tool_execution()
    
    print(f"\n🎉 Demo Complete!")
    print("\nNext Steps:")
    print("1. Configure Azure OpenAI in .env file for LLM capabilities")
    print("2. Run 'python start.py server' to start the full agent")
    print("3. Use 'python start.py interactive' for interactive queries")

if __name__ == "__main__":
    asyncio.run(main())