#!/usr/bin/env python3
"""
Simple Demo of Multi-Tool Agent (Minimal Version)
=================================================

This is a simplified version that works without external MCP dependencies,
demonstrating the core agent logic and LLM integration.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import uuid

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class SimpleAgentConfig:
    """Simplified configuration"""
    max_tool_chain_length: int = 5
    execution_timeout: int = 120

@dataclass
class ToolExecution:
    """Represents a single tool execution"""
    tool_name: str
    parameters: Dict[str, Any]
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None
    timestamp: Optional[str] = None

class SimpleMultiToolAgent:
    """
    Simplified Multi-Tool Agent that demonstrates the core concepts
    without requiring external MCP dependencies
    """
    
    def __init__(self, config: SimpleAgentConfig = None):
        self.config = config or SimpleAgentConfig()
        self.available_tools = self._get_simulated_tools()
        
    def _get_simulated_tools(self) -> List[Dict[str, Any]]:
        """Simulated tools for demonstration"""
        return [
            {
                "name": "view_purchase_order",
                "description": "Retrieve purchase order information",
                "parameters": ["po_number", "amendment_no"]
            },
            {
                "name": "view_purchase_request", 
                "description": "Get purchase requisition details",
                "parameters": ["pr_number"]
            },
            {
                "name": "search_purchase_orders",
                "description": "Search for purchase orders",
                "parameters": ["pr_no_from", "pr_no_to", "po_no_from", "po_no_to"]
            },
            {
                "name": "help_on_receipt_document",
                "description": "Search receipt documents",
                "parameters": ["ref_doc_no_from", "ref_doc_no_to"]
            },
            {
                "name": "view_movement_details",
                "description": "Get stock movement details",
                "parameters": ["receipt_no"]
            },
            {
                "name": "view_inspection_details",
                "description": "Get inspection results",
                "parameters": ["receipt_no"]
            }
        ]
    
    async def analyze_query(self, user_query: str) -> Dict[str, Any]:
        """
        Simple query analysis without LLM (for demo purposes)
        In the full version, this would use Azure OpenAI
        """
        query_lower = user_query.lower()
        
        # Intelligent query analysis - detect intent beyond explicit keywords
        if "purchase order" in query_lower or any(x in query_lower for x in ["po", "order"]) or self._has_po_pattern(user_query):
            # Check if user wants comprehensive information or just basic details
            if self._needs_comprehensive_po_analysis(user_query):
                return {
                    "strategy": "tool_chain",
                    "reasoning": "Query suggests need for comprehensive PO analysis including movement tracking",
                    "tool_chain": [
                        {
                            "tool_name": "view_purchase_order",
                            "parameters": {"po_number": self._extract_po_number(user_query)},
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
                    "strategy": "single_tool",
                    "reasoning": "Simple PO lookup based on query context",
                    "tool_name": "view_purchase_order",
                    "parameters": {"po_number": self._extract_po_number(user_query)}
                }
        
        elif "purchase request" in query_lower or "pr" in query_lower or self._has_pr_pattern(user_query):
            # Intelligently decide if user wants full PR-to-PO analysis
            if self._needs_comprehensive_pr_analysis(user_query):
                return {
                    "strategy": "tool_chain",
                    "reasoning": "Query suggests need for full PR lifecycle analysis including related PO",
                    "tool_chain": [
                        {
                            "tool_name": "view_purchase_request",
                            "parameters": {"pr_number": self._extract_pr_number(user_query)},
                            "output_fields": ["PrNo"]
                        },
                        {
                            "tool_name": "search_purchase_orders",
                            "parameters": {"pr_no_from": "{{PrNo}}", "pr_no_to": "{{PrNo}}"},
                            "output_fields": ["PoNo"]
                        },
                        {
                            "tool_name": "view_purchase_order",
                            "parameters": {"po_number": "{{PoNo}}"},
                            "output_fields": []
                        }
                    ]
                }
            else:
                return {
                    "strategy": "single_tool", 
                    "reasoning": "Basic PR lookup based on query simplicity",
                    "tool_name": "view_purchase_request",
                    "parameters": {"pr_number": self._extract_pr_number(user_query)}
                }
        
        elif any(x in query_lower for x in ["inspection", "quality", "qc"]):
            # Quality inspection workflow chain
            receipt_no = self._extract_receipt_number(user_query)
            return {
                "strategy": "tool_chain",
                "reasoning": "Quality inspection requires both movement and inspection details",
                "tool_chain": [
                    {
                        "tool_name": "view_movement_details",
                        "parameters": {"receipt_no": receipt_no},
                        "output_fields": ["ReceiptNo"]
                    },
                    {
                        "tool_name": "view_inspection_details",
                        "parameters": {"receipt_no": "{{ReceiptNo}}"},
                        "output_fields": []
                    }
                ]
            }
        
        else:
            return {
                "strategy": "clarification",
                "reasoning": "Query unclear",
                "clarification_message": "Could you specify what document or information you're looking for?",
                "suggestions": ["View purchase order", "View purchase request", "Trace movement flow", "Check quality inspection"]
            }
    
    def _extract_po_number(self, query: str) -> str:
        """Extract PO number from query (simple pattern matching)"""
        import re
        po_match = re.search(r'(PO\w+|\w*\d+\w*)', query, re.IGNORECASE)
        return po_match.group(1) if po_match else "PO123"
    
    def _extract_pr_number(self, query: str) -> str:
        """Extract PR number from query"""
        import re
        pr_match = re.search(r'(PR\w+|REQ\w+|\w*\d+\w*)', query, re.IGNORECASE)
        return pr_match.group(1) if pr_match else "PR123"
    
    def _extract_receipt_number(self, query: str) -> str:
        """Extract receipt number from query"""
        import re
        receipt_match = re.search(r'(GR\w+|REC\w+|\d+)', query, re.IGNORECASE)
        return receipt_match.group(1) if receipt_match else "GR1041"
    
    def _has_po_pattern(self, query: str) -> bool:
        """Check if query has PO-related patterns even without explicit 'purchase order'"""
        import re
        return bool(re.search(r'\b(PO\w+|order\s+\w+)', query, re.IGNORECASE))
    
    def _has_pr_pattern(self, query: str) -> bool:
        """Check if query has PR-related patterns"""
        import re
        return bool(re.search(r'\b(PR\w+|REQ\w+|request\s+\w+)', query, re.IGNORECASE))
    
    def _needs_comprehensive_po_analysis(self, query: str) -> bool:
        """
        Intelligently determine if PO query needs comprehensive analysis
        Based on question words, context clues, and business logic
        """
        query_lower = query.lower()
        
        # Explicit comprehensive keywords
        comprehensive_keywords = [
            "movement", "trace", "flow", "track", "follow", "where", "location",
            "status", "history", "lifecycle", "end-to-end", "complete", "full"
        ]
        
        # Question patterns that suggest comprehensive analysis
        question_patterns = [
            "where is", "what happened", "how did", "show me everything",
            "what's the status", "track this", "follow up"
        ]
        
        # Business context clues
        business_clues = [
            "received", "delivery", "warehouse", "receipt", "goods",
            "inventory", "stock", "shipment"
        ]
        
        # If any comprehensive indicators are present
        if any(keyword in query_lower for keyword in comprehensive_keywords):
            return True
            
        if any(pattern in query_lower for pattern in question_patterns):
            return True
            
        if any(clue in query_lower for clue in business_clues):
            return True
            
        # If query is longer and more descriptive, likely needs comprehensive analysis
        if len(query.split()) > 6:
            return True
            
        return False
    
    def _needs_comprehensive_pr_analysis(self, query: str) -> bool:
        """
        Determine if PR query needs full lifecycle analysis
        """
        query_lower = query.lower()
        
        # Keywords suggesting need for PR-to-PO analysis
        comprehensive_keywords = [
            "complete", "full", "details", "search", "find", "related",
            "associated", "linked", "converted", "generated", "created",
            "status", "lifecycle", "end-to-end", "follow"
        ]
        
        # Question patterns
        question_patterns = [
            "show me", "find all", "get everything", "what happened",
            "track this", "follow this"
        ]
        
        return (
            any(keyword in query_lower for keyword in comprehensive_keywords) or
            any(pattern in query_lower for pattern in question_patterns) or
            len(query.split()) > 5  # Longer queries likely need more detail
        )
    
    async def simulate_tool_call(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate tool execution with realistic responses"""
        await asyncio.sleep(0.3)  # Simulate processing time
        
        if tool_name == "view_purchase_order":
            return {
                "PoNo": parameters.get("po_number", "PO123"),
                "SupplierName": "Acme Supplies Ltd",
                "PoAmount": 25000.00,
                "PoStatus": "Approved",
                "PoDate": "2024-11-01",
                "LineItems": [
                    {"ItemCode": "ITEM001", "Description": "Office Supplies", "Quantity": 50, "UnitPrice": 500.00}
                ]
            }
        elif tool_name == "view_purchase_request":
            return {
                "PrNo": parameters.get("pr_number", "PR123"),
                "RequesterName": "John Smith",
                "Department": "Operations",
                "PrStatus": "Approved",
                "TotalAmount": 25000.00,
                "RequestDate": "2024-10-25"
            }
        elif tool_name == "search_purchase_orders":
            return [
                {
                    "PoNo": "PO-" + parameters.get("pr_no_from", "PR123").replace("PR", ""),
                    "PrNo": parameters.get("pr_no_from", "PR123"),
                    "SupplierName": "Global Industries Inc",
                    "PoAmount": 25000.00,
                    "PoDate": "2024-10-28",
                    "PoStatus": "Active"
                }
            ]
        elif tool_name == "help_on_receipt_document":
            return [
                {
                    "ReceiptNo": "GR1041",
                    "RefDocNo": parameters.get("ref_doc_no_from", "PO123"),
                    "ReceivedDate": "2024-11-05",
                    "ReceivedQty": 50,
                    "AcceptedQty": 50,
                    "RejectedQty": 0
                }
            ]
        elif tool_name == "view_movement_details":
            return {
                "ReceiptNo": parameters.get("receipt_no", "GR1041"),
                "MovementHistory": [
                    {
                        "Date": "2024-11-05T10:00:00",
                        "FromLocation": "Receiving Dock",
                        "ToLocation": "Warehouse A-1",
                        "Quantity": 50,
                        "MovementType": "Goods Receipt"
                    },
                    {
                        "Date": "2024-11-05T14:30:00", 
                        "FromLocation": "Warehouse A-1",
                        "ToLocation": "Quality Control",
                        "Quantity": 50,
                        "MovementType": "QC Transfer"
                    }
                ],
                "CurrentLocation": "Quality Control",
                "CurrentStock": 50
            }
        elif tool_name == "view_inspection_details":
            return {
                "ReceiptNo": parameters.get("receipt_no", "GR1041"),
                "InspectionDate": "2024-11-05T16:00:00",
                "Inspector": "Jane Doe",
                "InspectionResult": "Pass",
                "QualityGrade": "A",
                "DefectCount": 0,
                "SampleSize": 5
            }
        else:
            return {
                "message": f"Simulated result for {tool_name}",
                "parameters": parameters,
                "timestamp": datetime.now().isoformat()
            }
    
    def resolve_parameters(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve parameter placeholders using context"""
        resolved = {}
        for key, value in parameters.items():
            if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
                placeholder = value[2:-2]
                if placeholder in context:
                    resolved[key] = context[placeholder]
                else:
                    logger.warning(f"Placeholder '{placeholder}' not found in context")
                    resolved[key] = value
            else:
                resolved[key] = value
        return resolved
    
    async def execute_single_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single tool"""
        logger.info(f"🔧 Executing single tool: {tool_name}")
        result = await self.simulate_tool_call(tool_name, parameters)
        
        return {
            "type": "single_tool_result",
            "tool_name": tool_name,
            "parameters": parameters,
            "result": result
        }
    
    async def execute_tool_chain(self, tool_chain: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute a chain of tools with parameter mapping"""
        context = {}
        chain_results = []
        
        logger.info(f"⛓️  Executing tool chain with {len(tool_chain)} steps")
        
        for i, step in enumerate(tool_chain):
            tool_name = step.get("tool_name")
            parameters = step.get("parameters", {})
            
            # Resolve parameter placeholders
            resolved_params = self.resolve_parameters(parameters, context)
            
            logger.info(f"🔧 Chain step {i+1}/{len(tool_chain)}: {tool_name}")
            result = await self.simulate_tool_call(tool_name, resolved_params)
            
            # Store result in context for next steps
            context[f"step_{i}_result"] = result
            
            # Store output fields if specified
            output_fields = step.get("output_fields", [])
            for field in output_fields:
                if isinstance(result, dict) and field in result:
                    context[field] = result[field]
                elif isinstance(result, list) and result:
                    if isinstance(result[0], dict) and field in result[0]:
                        context[field] = result[0][field]
            
            chain_results.append({
                "step": i + 1,
                "tool_name": tool_name,
                "parameters": resolved_params,
                "result": result
            })
        
        return {
            "type": "tool_chain_result",
            "chain_results": chain_results,
            "final_context": context
        }
    
    async def process_request(self, user_query: str) -> Dict[str, Any]:
        """Main request processing method"""
        session_id = str(uuid.uuid4())
        start_time = asyncio.get_event_loop().time()
        
        logger.info(f"🎯 Processing request [Session: {session_id[:8]}]: {user_query}")
        
        try:
            # Analyze execution strategy
            strategy = await self.analyze_query(user_query)
            
            if strategy.get("strategy") == "clarification":
                result = {
                    "session_id": session_id,
                    "user_query": user_query,
                    "strategy": "clarification",
                    "success": True,
                    "result": {
                        "type": "clarification",
                        "message": strategy.get("clarification_message"),
                        "suggestions": strategy.get("suggestions", [])
                    }
                }
            elif strategy.get("strategy") == "single_tool":
                result_data = await self.execute_single_tool(
                    strategy.get("tool_name"),
                    strategy.get("parameters", {})
                )
                result = {
                    "session_id": session_id,
                    "user_query": user_query,
                    "strategy": "single_tool",
                    "success": True,
                    "result": result_data
                }
            elif strategy.get("strategy") == "tool_chain":
                result_data = await self.execute_tool_chain(strategy.get("tool_chain", []))
                result = {
                    "session_id": session_id,
                    "user_query": user_query,
                    "strategy": "tool_chain", 
                    "success": True,
                    "result": result_data
                }
            else:
                result = {
                    "session_id": session_id,
                    "user_query": user_query,
                    "strategy": "error",
                    "success": False,
                    "error": f"Unknown strategy: {strategy.get('strategy')}"
                }
            
        except Exception as e:
            logger.error(f"❌ Error processing request: {e}")
            result = {
                "session_id": session_id,
                "user_query": user_query,
                "strategy": "error",
                "success": False,
                "error": str(e)
            }
        
        result["execution_time"] = asyncio.get_event_loop().time() - start_time
        logger.info(f"✅ Request completed [Session: {session_id[:8]}] - Success: {result['success']}")
        
        return result

async def demo():
    """Run demonstration of the agent"""
    print("\n" + "="*70)
    print("🚀 Simple Multi-Tool Agent Demo")
    print("="*70)
    
    agent = SimpleMultiToolAgent()
    
    # Test queries - mix of explicit and implicit tool chaining needs
    test_queries = [
        "Show me details of purchase order PO12345",  # Simple - single tool
        "Where is my order JSLTEST46 right now?",  # Implicit comprehensive - tool chain
        "Find purchase request PR789 details",  # Simple - single tool
        "Show me everything about purchase request REQ456",  # Implicit comprehensive - tool chain  
        "Check quality inspection for receipt GR2024",  # QC chain
        "PO12345",  # Minimal query - single tool
        "What happened to order ABC123 after it was received?",  # Implicit comprehensive - tool chain
        "What's the status?"  # Should trigger clarification
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n📝 Test Query {i}: {query}")
        print("-" * 50)
        
        result = await agent.process_request(query)
        
        print(f"🎯 Strategy: {result['strategy']}")
        print(f"✅ Success: {result['success']}")
        print(f"⏱️  Execution Time: {result['execution_time']:.2f}s")
        
        if result['success']:
            if result['strategy'] == 'clarification':
                print(f"💬 Message: {result['result']['message']}")
                print(f"💡 Suggestions: {', '.join(result['result']['suggestions'])}")
            elif result['strategy'] == 'single_tool':
                print(f"🔧 Tool: {result['result']['tool_name']}")
                print(f"📊 Result Preview: {str(result['result']['result'])[:100]}...")
            elif result['strategy'] == 'tool_chain':
                chain_results = result['result']['chain_results']
                print(f"⛓️  Tool Chain ({len(chain_results)} steps):")
                for step in chain_results:
                    print(f"   Step {step['step']}: {step['tool_name']}")
        else:
            print(f"❌ Error: {result['error']}")
    
    print(f"\n{'='*70}")
    print("🎉 Demo completed successfully!")
    print("="*70)

if __name__ == "__main__":
    asyncio.run(demo())