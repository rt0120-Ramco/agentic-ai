#!/usr/bin/env python3
"""
Policy-Aware Dynamic MCP Agent
=============================

Enhanced version of the dynamic MCP agent that incorporates business policies
for intelligent decision-making. This agent can process policies (like supplier
selection rules) and apply them during tool orchestration.

Key Features:
- Policy integration and parsing (Plain English → JSON rules)
- Policy-aware tool orchestration  
- Business rule validation during execution
- Dynamic policy application to tool chains
- Supplier selection, procurement policies, etc.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime
import uuid
import inspect
import os
from dotenv import load_dotenv
import re

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
    from openai import AsyncAzureOpenAI
    OPENAI_AVAILABLE = True
    logger.info("✅ OpenAI package available for LLM integration")
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("⚠️ OpenAI package not available - falling back to simulation mode")

@dataclass
class BusinessPolicy:
    """Represents a business policy with rules and conditions"""
    policy_id: str
    name: str
    description: str
    plain_english: str
    json_rules: Dict[str, Any]
    priority: int = 1
    active: bool = True
    created_date: Optional[datetime] = None

@dataclass 
class PolicyRule:
    """Individual rule within a policy"""
    rule_id: int
    condition: str
    action: str
    priority: int
    parameters: Dict[str, Any] = field(default_factory=dict)

@dataclass
class MCPTool:
    """Represents a registered MCP tool with its metadata"""
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable
    tags: List[str] = field(default_factory=list)
    
class PolicyEngine:
    """Engine for managing and applying business policies"""
    
    def __init__(self):
        self.policies: Dict[str, BusinessPolicy] = {}
        self.policy_cache: Dict[str, Any] = {}
        
    def add_policy(self, policy: BusinessPolicy):
        """Register a new business policy"""
        self.policies[policy.policy_id] = policy
        logger.info(f"📋 Registered policy: {policy.name}")
        
    def parse_plain_english_policy(self, plain_text: str) -> Dict[str, Any]:
        """Parse plain English policy into structured JSON rules"""
        
        # Example parsing for supplier selection policy
        rules = []
        rule_id = 1
        
        # Extract conditions and actions using pattern matching
        text_lower = plain_text.lower()
        
        # Pattern 1: Rating conditions
        if "rating >=" in text_lower or "rating ≥" in text_lower:
            rating_match = re.search(r'rating\s*>=?\s*(\d+)', text_lower)
            if rating_match:
                rating_value = int(rating_match.group(1))
                rules.append({
                    "id": rule_id,
                    "condition": f"supplier.rating >= {rating_value}",
                    "action": "include",
                    "priority": rule_id
                })
                rule_id += 1
                
        # Pattern 2: Lead time conditions  
        if "lead time" in text_lower and "days" in text_lower:
            leadtime_match = re.search(r'lead time\s*<=?\s*(\d+)\s*days', text_lower)
            if leadtime_match:
                days_value = int(leadtime_match.group(1))
                rules.append({
                    "id": rule_id,
                    "condition": f"supplier.leadTime <= {days_value}",
                    "action": "include", 
                    "priority": rule_id
                })
                rule_id += 1
                
        # Pattern 3: Cost optimization
        if "lowest" in text_lower and ("cost" in text_lower or "price" in text_lower):
            rules.append({
                "id": rule_id,
                "condition": "true",
                "action": "sort_by_lowest_cost",
                "priority": rule_id
            })
            rule_id += 1
            
        # Pattern 4: Escalation rules
        if "escalate" in text_lower and "po >" in text_lower:
            po_match = re.search(r'po\s*>\s*[₹$]?(\d+(?:,\d+)*)', text_lower)
            if po_match:
                amount_str = po_match.group(1).replace(',', '')
                amount = int(amount_str)
                rules.append({
                    "id": rule_id,
                    "condition": f"po.value > {amount}",
                    "action": "escalate",
                    "priority": rule_id,
                    "parameters": {"escalation_level": "manager_approval"}
                })
                rule_id += 1
                
        return {
            "agentId": "supplier_selection",
            "version": "v1.0",
            "rules": rules
        }
        
    def apply_supplier_selection_policy(self, suppliers: List[Dict], po_amount: float = 0) -> Dict[str, Any]:
        """Apply supplier selection policy to filter and rank suppliers"""
        
        if not suppliers:
            return {"filtered_suppliers": [], "policy_actions": []}
            
        filtered_suppliers = []
        policy_actions = []
        
        # Get supplier selection policy
        supplier_policy = self.policies.get("supplier_selection")
        if not supplier_policy:
            logger.warning("⚠️ No supplier selection policy found")
            return {"filtered_suppliers": suppliers, "policy_actions": []}
            
        # Apply each rule in the policy
        for rule in supplier_policy.json_rules.get("rules", []):
            condition = rule.get("condition", "")
            action = rule.get("action", "")
            
            if action == "include":
                # Apply inclusion filters
                if "rating >=" in condition:
                    rating_threshold = int(re.search(r'(\d+)', condition).group(1))
                    before_count = len(filtered_suppliers) if filtered_suppliers else len(suppliers)
                    source_list = filtered_suppliers if filtered_suppliers else suppliers
                    filtered_suppliers = [s for s in source_list if s.get('rating', 0) >= rating_threshold]
                    policy_actions.append(f"✅ Applied rating filter (>= {rating_threshold}): {before_count} → {len(filtered_suppliers)} suppliers")
                    
                elif "leadTime <=" in condition:
                    days_threshold = int(re.search(r'(\d+)', condition).group(1))
                    before_count = len(filtered_suppliers) if filtered_suppliers else len(suppliers)
                    source_list = filtered_suppliers if filtered_suppliers else suppliers
                    filtered_suppliers = [s for s in source_list if s.get('leadTime', 999) <= days_threshold]
                    policy_actions.append(f"⏱️ Applied lead time filter (<= {days_threshold} days): {before_count} → {len(filtered_suppliers)} suppliers")
                    
            elif action == "sort_by_lowest_cost":
                # Sort by cost (ascending)
                if filtered_suppliers:
                    filtered_suppliers.sort(key=lambda x: x.get('cost', float('inf')))
                    policy_actions.append(f"💰 Sorted suppliers by lowest cost")
                    
            elif action == "escalate":
                # Check escalation conditions
                if "po.value >" in condition:
                    threshold = int(re.search(r'(\d+)', condition).group(1))
                    if po_amount > threshold:
                        policy_actions.append(f"🚨 ESCALATION: PO amount ₹{po_amount:,} exceeds threshold ₹{threshold:,} - Manager approval required")
                        
        # If no suppliers passed filters, use original list but note policy violations
        if not filtered_suppliers and suppliers:
            filtered_suppliers = suppliers
            policy_actions.append("⚠️ No suppliers met all policy criteria - showing all suppliers with warnings")
            
        return {
            "filtered_suppliers": filtered_suppliers,
            "policy_actions": policy_actions,
            "policy_applied": supplier_policy.name
        }

class PolicyAwareMCPAgent:
    """Enhanced MCP Agent with business policy integration"""
    
    def __init__(self, config=None):
        self.config = config or PolicyAgentConfig()
        self.tool_pool = MCPToolPool()
        self.policy_engine = PolicyEngine()
        self.openai_client = None
        self.execution_history = []
        
        # Initialize Azure OpenAI client if available and configured
        self._initialize_openai_client()
        
        # Initialize built-in policies
        self._initialize_default_policies()
        
    def _initialize_openai_client(self):
        """Initialize Azure OpenAI client for LLM-powered policy analysis"""
        if not OPENAI_AVAILABLE:
            logger.info("🔄 OpenAI not available - using pattern-based policy analysis")
            return
            
        # Get configuration from environment or config
        api_key = os.getenv("OPENAI_API_KEY") or self.config.azure_openai_api_key
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT") or self.config.azure_openai_endpoint
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT") or self.config.azure_openai_deployment
        
        if not api_key or not endpoint:
            logger.info("🔄 Azure OpenAI credentials not provided - using pattern-based analysis")
            return
            
        try:
            self.openai_client = AsyncAzureOpenAI(
                api_key=api_key,
                azure_endpoint=endpoint,
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
            )
            logger.info(f"🤖 Azure OpenAI client initialized - Deployment: {deployment}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to initialize Azure OpenAI client: {e}")
            self.openai_client = None
        
    def _initialize_default_policies(self):
        """Initialize default business policies"""
        
        # Supplier Selection Policy (from the screenshot)
        supplier_policy_text = """
        Prefer local suppliers with rating >= 4 and lead time <= 7 days;
        tie-breaker lowest landed cost; escalate if PO > ₹500,000.
        """
        
        supplier_policy = BusinessPolicy(
            policy_id="supplier_selection",
            name="Supplier Selection Agent",
            description="Policy for intelligent supplier selection and procurement decisions",
            plain_english=supplier_policy_text,
            json_rules=self.policy_engine.parse_plain_english_policy(supplier_policy_text),
            priority=1,
            created_date=datetime.now()
        )
        
        self.policy_engine.add_policy(supplier_policy)
        
        # Procurement Approval Policy
        approval_policy_text = """
        PO amounts under ₹100,000 auto-approve; ₹100,000-₹500,000 require manager approval;
        above ₹500,000 require director approval and three quotes.
        """
        
        approval_policy = BusinessPolicy(
            policy_id="procurement_approval",
            name="Procurement Approval Policy", 
            description="Multi-level approval workflow for purchase orders",
            plain_english=approval_policy_text,
            json_rules=self.policy_engine.parse_plain_english_policy(approval_policy_text),
            priority=2,
            created_date=datetime.now()
        )
        
        self.policy_engine.add_policy(approval_policy)
        
    async def analyze_with_policy_awareness(self, user_query: str) -> Dict[str, Any]:
        """Analyze user query and determine policy-aware tool execution plan"""
        
        # Use LLM analysis if available, otherwise fall back to pattern matching
        if self.openai_client and self.config.enable_ai_analysis:
            return await self._llm_powered_policy_analysis(user_query)
        else:
            return await self._pattern_based_policy_analysis(user_query)
            
    async def _llm_powered_policy_analysis(self, user_query: str) -> Dict[str, Any]:
        """Use Azure OpenAI to analyze query with policy awareness"""
        
        # Get available policies for context
        policy_context = self._build_policy_context()
        
        # Build AI prompt for policy-aware analysis (simplified for gpt-5-mini)
        system_prompt = """Analyze business queries for policy compliance. Available policies:

1. Supplier Selection: rating >= 4, lead time <= 7 days, lowest cost, escalate if PO > ₹500,000
2. Procurement Approval: auto-approve <= ₹100,000, manager approval ₹100,000-₹500,000, director approval > ₹500,000

Respond with JSON only:"""

        user_prompt = f"User Query: {user_query}"
        
        try:
            logger.info("🤖 Sending query to Azure OpenAI for policy analysis...")
            
            response = await self.openai_client.chat.completions.create(
                model=self.config.azure_openai_deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_completion_tokens=2000
            )
            
            ai_content = response.choices[0].message.content if response.choices else None
            logger.info(f"🧠 AI Policy Analysis Length: {len(ai_content) if ai_content else 0} chars")
            
            if not ai_content or ai_content.strip() == "":
                logger.warning("⚠️ AI response is empty, falling back to pattern analysis")
                return await self._pattern_based_policy_analysis(user_query)
            
            # Parse AI response - handle flexible JSON structure
            try:
                ai_raw_analysis = json.loads(ai_content)
                
                # Transform AI response to our expected format
                ai_analysis = self._transform_ai_response(ai_raw_analysis, user_query)
                
                # Execute policy-aware strategy based on AI analysis
                return await self._execute_policy_strategy(user_query, ai_analysis)
                
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ AI response not valid JSON: {e}, falling back to pattern analysis")
                return await self._pattern_based_policy_analysis(user_query)
                
        except Exception as e:
            logger.error(f"❌ Azure OpenAI policy analysis failed: {e}")
            return await self._pattern_based_policy_analysis(user_query)
            
    def _build_policy_context(self) -> str:
        """Build policy context for AI analysis"""
        
        context_lines = []
        
        for policy_id, policy in self.policy_engine.policies.items():
            context_lines.append(f"**{policy.name}** (ID: {policy_id})")
            context_lines.append(f"   Description: {policy.description}")
            context_lines.append(f"   Rules: {policy.plain_english}")
            context_lines.append(f"   JSON Rules: {json.dumps(policy.json_rules, indent=2)}")
            context_lines.append("")
            
        return "\n".join(context_lines)
        
    def _transform_ai_response(self, ai_raw: Dict[str, Any], user_query: str) -> Dict[str, Any]:
        """Transform AI response to expected format"""
        
        # Detect strategy based on AI response content
        strategy = "standard_orchestration"
        
        query_lower = user_query.lower()
        if any(word in query_lower for word in ["supplier", "vendor", "quote"]) or \
           "supplier_selection_criteria" in ai_raw:
            strategy = "supplier_selection"
        elif "approval" in ai_raw.get("procurement_approval_required", {}) or \
             any(word in query_lower for word in ["approval", "approve"]):
            strategy = "approval_workflow"
        elif any(word in query_lower for word in ["policy", "rule"]):
            strategy = "policy_information"
            
        # Extract key information
        purchase_amount = ai_raw.get("purchase_amount", 0)
        escalation_needed = ai_raw.get("escalation_required", False)
        
        # Build standardized response
        return {
            "query_intent": f"Purchase request for ₹{purchase_amount:,} {ai_raw.get('category', 'items')}",
            "applicable_policies": ["supplier_selection", "procurement_approval"],
            "policy_reasoning": f"Amount ₹{purchase_amount:,} requires policy compliance for supplier selection and approval workflow",
            "strategy": strategy,
            "required_actions": ai_raw.get("recommended_actions", []),
            "confidence": 0.95,
            "escalation_needed": escalation_needed,
            "compliance_requirements": ai_raw.get("documents_to_attach", []),
            "raw_ai_analysis": ai_raw  # Keep original for reference
        }
        
    async def _execute_policy_strategy(self, user_query: str, ai_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the strategy determined by AI analysis"""
        
        strategy = ai_analysis.get("strategy", "standard_orchestration")
        applicable_policies = ai_analysis.get("applicable_policies", [])
        
        logger.info(f"🎯 AI determined strategy: {strategy}")
        logger.info(f"📋 Applicable policies: {applicable_policies}")
        
        if strategy == "supplier_selection":
            return await self._ai_enhanced_supplier_selection(user_query, ai_analysis)
            
        elif strategy == "approval_workflow":
            return await self._ai_enhanced_approval_workflow(user_query, ai_analysis)
            
        elif strategy == "policy_information":
            return await self._ai_enhanced_policy_information(user_query, ai_analysis)
            
        else:  # standard_orchestration
            return await self._ai_enhanced_standard_orchestration(user_query, ai_analysis)
            
    async def _ai_enhanced_supplier_selection(self, user_query: str, ai_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """AI-enhanced supplier selection with policy compliance"""
        
        # Extract PO amount using AI reasoning
        po_amount = self._extract_amount_from_query(user_query)
        
        # Get sample suppliers (in production, this would call real APIs)
        sample_suppliers = [
            {"name": "Local Tech Solutions", "rating": 4.5, "leadTime": 5, "cost": 45000, "location": "local"},
            {"name": "Global Parts Inc", "rating": 3.8, "leadTime": 12, "cost": 42000, "location": "international"},
            {"name": "Premium Supplies Co", "rating": 4.8, "leadTime": 3, "cost": 48000, "location": "local"},
            {"name": "Budget Components", "rating": 3.2, "leadTime": 15, "cost": 38000, "location": "local"},
            {"name": "Fast Delivery Ltd", "rating": 4.2, "leadTime": 2, "cost": 52000, "location": "local"}
        ]
        
        # Apply policy with AI reasoning
        policy_result = self.policy_engine.apply_supplier_selection_policy(sample_suppliers, po_amount)
        
        return {
            "query": user_query,
            "strategy": "ai_enhanced_supplier_selection",
            "ai_reasoning": ai_analysis.get("policy_reasoning", ""),
            "query_intent": ai_analysis.get("query_intent", ""),
            "original_suppliers": len(sample_suppliers),
            "filtered_suppliers": policy_result["filtered_suppliers"],
            "policy_actions": policy_result["policy_actions"],
            "policy_applied": policy_result.get("policy_applied", "supplier_selection"),
            "recommendations": self._generate_supplier_recommendations(policy_result["filtered_suppliers"]),
            "compliance_requirements": ai_analysis.get("compliance_requirements", []),
            "escalation_needed": ai_analysis.get("escalation_needed", False),
            "confidence": ai_analysis.get("confidence", 0.95)
        }
        
    async def _ai_enhanced_approval_workflow(self, user_query: str, ai_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """AI-enhanced approval workflow"""
        
        # Extract amount using AI reasoning  
        amount = self._extract_amount_from_query(user_query)
        
        # Determine approval level
        approval_level = "auto"
        required_approvers = []
        
        if amount <= 100000:
            approval_level = "auto_approve"
            required_approvers = ["system"]
        elif amount <= 500000:
            approval_level = "manager_approval"
            required_approvers = ["manager"]
        else:
            approval_level = "director_approval"
            required_approvers = ["manager", "director"]
            
        return {
            "query": user_query,
            "strategy": "ai_enhanced_approval_workflow",
            "ai_reasoning": ai_analysis.get("policy_reasoning", ""),
            "query_intent": ai_analysis.get("query_intent", ""),
            "amount": amount,
            "approval_level": approval_level,
            "required_approvers": required_approvers,
            "policy_applied": "procurement_approval",
            "next_actions": self._generate_approval_actions(approval_level, amount),
            "compliance_requirements": ai_analysis.get("compliance_requirements", []),
            "escalation_needed": ai_analysis.get("escalation_needed", False),
            "confidence": ai_analysis.get("confidence", 0.92)
        }
        
    async def _ai_enhanced_policy_information(self, user_query: str, ai_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """AI-enhanced policy information"""
        
        policies_info = []
        for policy_id, policy in self.policy_engine.policies.items():
            policies_info.append({
                "id": policy_id,
                "name": policy.name,
                "description": policy.description,
                "rules_count": len(policy.json_rules.get("rules", [])),
                "active": policy.active
            })
            
        return {
            "query": user_query,
            "strategy": "ai_enhanced_policy_information",
            "ai_reasoning": ai_analysis.get("policy_reasoning", ""),
            "query_intent": ai_analysis.get("query_intent", ""),
            "available_policies": policies_info,
            "total_policies": len(policies_info),
            "applicable_policies": ai_analysis.get("applicable_policies", []),
            "compliance_requirements": ai_analysis.get("compliance_requirements", []),
            "confidence": ai_analysis.get("confidence", 0.88)
        }
        
    async def _ai_enhanced_standard_orchestration(self, user_query: str, ai_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """AI-enhanced standard tool orchestration"""
        
        return {
            "query": user_query,
            "strategy": "ai_enhanced_standard_orchestration",
            "ai_reasoning": ai_analysis.get("policy_reasoning", ""),
            "query_intent": ai_analysis.get("query_intent", ""),
            "message": "AI-powered tool orchestration with policy awareness",
            "applicable_policies": ai_analysis.get("applicable_policies", []),
            "required_actions": ai_analysis.get("required_actions", []),
            "compliance_requirements": ai_analysis.get("compliance_requirements", []),
            "escalation_needed": ai_analysis.get("escalation_needed", False),
            "confidence": ai_analysis.get("confidence", 0.75)
        }
        
    def _extract_amount_from_query(self, query: str) -> float:
        """Extract monetary amount from query"""
        po_match = re.search(r'[₹$](\d+(?:,\d+)*)', query)
        if po_match:
            return float(po_match.group(1).replace(',', ''))
        return 0
        
    async def _pattern_based_policy_analysis(self, user_query: str) -> Dict[str, Any]:
        """Fallback to pattern-based analysis when LLM not available"""
        
        logger.info("🔄 Using pattern-based policy analysis")
        
        query_lower = user_query.lower()
        
        # Detect policy-relevant queries
        if any(word in query_lower for word in ["supplier", "vendor", "quote", "selection"]):
            return await self._handle_supplier_selection_query(user_query)
            
        elif any(word in query_lower for word in ["approve", "approval", "authorize", "escalate"]):
            return await self._handle_approval_query(user_query)
            
        elif any(word in query_lower for word in ["policy", "rule", "compliance", "validate"]):
            return await self._handle_policy_query(user_query)
            
        else:
            # Fall back to standard tool orchestration
            return await self._handle_standard_query(user_query)
            
    async def _handle_supplier_selection_query(self, query: str) -> Dict[str, Any]:
        """Handle supplier selection with policy application"""
        
        # Simulate supplier data (in real implementation, this would come from API)
        sample_suppliers = [
            {"name": "Local Tech Solutions", "rating": 4.5, "leadTime": 5, "cost": 45000, "location": "local"},
            {"name": "Global Parts Inc", "rating": 3.8, "leadTime": 12, "cost": 42000, "location": "international"},
            {"name": "Premium Supplies Co", "rating": 4.8, "leadTime": 3, "cost": 48000, "location": "local"},
            {"name": "Budget Components", "rating": 3.2, "leadTime": 15, "cost": 38000, "location": "local"},
            {"name": "Fast Delivery Ltd", "rating": 4.2, "leadTime": 2, "cost": 52000, "location": "local"}
        ]
        
        # Extract PO amount from query if mentioned
        po_amount = 0
        po_match = re.search(r'[₹$](\d+(?:,\d+)*)', query)
        if po_match:
            po_amount = float(po_match.group(1).replace(',', ''))
            
        # Apply supplier selection policy
        policy_result = self.policy_engine.apply_supplier_selection_policy(sample_suppliers, po_amount)
        
        return {
            "query": query,
            "strategy": "policy_aware_supplier_selection",
            "original_suppliers": len(sample_suppliers),
            "filtered_suppliers": policy_result["filtered_suppliers"],
            "policy_actions": policy_result["policy_actions"],
            "policy_applied": policy_result.get("policy_applied", "supplier_selection"),
            "recommendations": self._generate_supplier_recommendations(policy_result["filtered_suppliers"]),
            "confidence": 0.95
        }
        
    async def _handle_approval_query(self, query: str) -> Dict[str, Any]:
        """Handle approval workflow queries"""
        
        # Extract amount from query
        amount_match = re.search(r'[₹$](\d+(?:,\d+)*)', query)
        amount = float(amount_match.group(1).replace(',', '')) if amount_match else 0
        
        # Determine approval level based on amount
        approval_level = "auto"
        required_approvers = []
        
        if amount <= 100000:
            approval_level = "auto_approve"
            required_approvers = ["system"]
        elif amount <= 500000:
            approval_level = "manager_approval"
            required_approvers = ["manager"]
        else:
            approval_level = "director_approval"
            required_approvers = ["manager", "director"]
            
        return {
            "query": query,
            "strategy": "policy_aware_approval",
            "amount": amount,
            "approval_level": approval_level,
            "required_approvers": required_approvers,
            "policy_applied": "procurement_approval",
            "next_actions": self._generate_approval_actions(approval_level, amount),
            "confidence": 0.92
        }
        
    async def _handle_policy_query(self, query: str) -> Dict[str, Any]:
        """Handle policy-related queries"""
        
        policies_info = []
        for policy_id, policy in self.policy_engine.policies.items():
            policies_info.append({
                "id": policy_id,
                "name": policy.name,
                "description": policy.description,
                "rules_count": len(policy.json_rules.get("rules", [])),
                "active": policy.active
            })
            
        return {
            "query": query,
            "strategy": "policy_information",
            "available_policies": policies_info,
            "total_policies": len(policies_info),
            "confidence": 0.88
        }
        
    async def _handle_standard_query(self, query: str) -> Dict[str, Any]:
        """Handle standard queries without specific policy requirements"""
        
        # This would integrate with the original dynamic_mcp_agent logic
        return {
            "query": query,
            "strategy": "standard_tool_orchestration",
            "message": "Standard MCP tool orchestration - no specific policy requirements detected",
            "confidence": 0.75
        }
        
    def _generate_supplier_recommendations(self, suppliers: List[Dict]) -> List[str]:
        """Generate human-readable supplier recommendations"""
        
        if not suppliers:
            return ["⚠️ No suppliers meet the current policy criteria"]
            
        recommendations = []
        
        # Top supplier recommendation
        top_supplier = suppliers[0]
        recommendations.append(f"🏆 **Recommended**: {top_supplier['name']} - Rating: {top_supplier['rating']}, Lead Time: {top_supplier['leadTime']} days, Cost: ₹{top_supplier['cost']:,}")
        
        # Alternative options
        if len(suppliers) > 1:
            recommendations.append(f"🔄 **Alternative**: {suppliers[1]['name']} - Rating: {suppliers[1]['rating']}, Cost: ₹{suppliers[1]['cost']:,}")
            
        # Cost comparison
        costs = [s['cost'] for s in suppliers]
        if len(costs) > 1:
            savings = max(costs) - min(costs)
            recommendations.append(f"💰 **Potential Savings**: ₹{savings:,} between highest and lowest cost options")
            
        return recommendations
        
    def _generate_approval_actions(self, approval_level: str, amount: float) -> List[str]:
        """Generate next actions for approval workflow"""
        
        actions = []
        
        if approval_level == "auto_approve":
            actions.append("✅ **Auto-approved** - Amount within auto-approval limit")
            actions.append("📋 Create PO and notify requestor")
            
        elif approval_level == "manager_approval":
            actions.append("📨 **Send to Manager** for approval")
            actions.append("⏰ Expected approval time: 1-2 business days")
            actions.append("📧 Notify requestor of pending approval")
            
        else:  # director_approval
            actions.append("🚨 **High-value PO** - Requires director approval")
            actions.append("📋 **Three quotes required** - Verify competitive pricing")
            actions.append("📨 Route to Manager → Director approval chain")
            actions.append("⏰ Expected approval time: 3-5 business days")
            
        return actions

@dataclass
class PolicyAgentConfig:
    """Configuration for policy-aware agent"""
    enable_ai_analysis: bool = True
    max_tool_chain_length: int = 6
    execution_timeout: int = 120
    policy_validation: bool = True
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = "gpt-5-mini"

class MCPToolPool:
    """Simplified tool pool for policy demo"""
    
    def __init__(self):
        self.tools = {}
        self._register_demo_tools()
        
    def _register_demo_tools(self):
        """Register demonstration tools"""
        
        # Supplier tools
        self.tools["search_suppliers"] = MCPTool(
            name="search_suppliers",
            description="Search for suppliers based on criteria",
            parameters={"criteria": "str", "location": "str"},
            handler=self._mock_search_suppliers
        )
        
        self.tools["get_supplier_details"] = MCPTool(
            name="get_supplier_details", 
            description="Get detailed information about a specific supplier",
            parameters={"supplier_id": "str"},
            handler=self._mock_supplier_details
        )
        
    async def _mock_search_suppliers(self, criteria: str = "", location: str = "") -> Dict:
        """Mock supplier search"""
        return {
            "suppliers_found": 5,
            "criteria": criteria,
            "location_filter": location,
            "execution_time": "0.3s"
        }
        
    async def _mock_supplier_details(self, supplier_id: str) -> Dict:
        """Mock supplier details"""
        return {
            "supplier_id": supplier_id,
            "rating": 4.2,
            "lead_time": 6,
            "certifications": ["ISO9001", "ISO14001"]
        }

async def demo_policy_aware_agent():
    """Demonstration of policy-aware MCP agent"""
    
    print("🏛️ Policy-Aware Dynamic MCP Agent Demo")
    print("=" * 60)
    
    # Initialize agent
    agent = PolicyAwareMCPAgent()
    
    print(f"✅ Agent initialized with {len(agent.policy_engine.policies)} business policies")
    print()
    
    # Test scenarios
    test_scenarios = [
        "Find the best suppliers for a ₹250,000 electronics purchase",
        "I need approval for a ₹750,000 software license purchase", 
        "What policies do we have for supplier selection?",
        "Show me suppliers with good ratings and fast delivery"
    ]
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"📝 Test Scenario {i}: {scenario}")
        print("-" * 50)
        
        try:
            result = await agent.analyze_with_policy_awareness(scenario)
            
            print(f"🎯 Strategy: {result['strategy']}")
            print(f"🎲 Confidence: {result.get('confidence', 0.0)*100:.0f}%")
            
            if result['strategy'] == 'policy_aware_supplier_selection':
                print(f"📊 Original suppliers: {result['original_suppliers']}")
                print(f"✅ Filtered suppliers: {len(result['filtered_suppliers'])}")
                print(f"📋 Policy applied: {result['policy_applied']}")
                
                print("\n🔍 Policy Actions:")
                for action in result['policy_actions']:
                    print(f"   {action}")
                    
                print("\n💡 Recommendations:")
                for rec in result['recommendations']:
                    print(f"   {rec}")
                    
            elif result['strategy'] == 'policy_aware_approval':
                print(f"💰 Amount: ₹{result['amount']:,}")
                print(f"📊 Approval Level: {result['approval_level']}")
                print(f"👥 Required Approvers: {', '.join(result['required_approvers'])}")
                
                print("\n📋 Next Actions:")
                for action in result['next_actions']:
                    print(f"   {action}")
                    
            elif result['strategy'] == 'policy_information':
                print(f"📚 Available Policies: {result['total_policies']}")
                
                print("\n📋 Policy Details:")
                for policy in result['available_policies']:
                    print(f"   • {policy['name']}: {policy['rules_count']} rules ({'Active' if policy['active'] else 'Inactive'})")
                    
        except Exception as e:
            print(f"❌ Error: {e}")
            
        print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    # Initialize configuration with environment variables
    config = PolicyAgentConfig()
    config.enable_ai_analysis = bool(os.getenv("USE_AI_MODEL", "True").lower() in ["true", "1", "yes"])
    config.azure_openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    config.azure_openai_api_key = os.getenv("OPENAI_API_KEY", "")
    config.azure_openai_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5-mini")
    
    # Create agent with configuration
    async def demo_with_config():
        agent = PolicyAwareMCPAgent(config)
        
        print("🏛️ Policy-Aware Dynamic MCP Agent Demo")
        print("=" * 60)
        print(f"🤖 AI Analysis: {'Enabled' if config.enable_ai_analysis else 'Disabled (Simulation Mode)'}")
        print(f"✅ Agent initialized with {len(agent.policy_engine.policies)} business policies")
        print()
        
        # Test scenarios
        test_scenarios = [
            "Find the best suppliers for a ₹250,000 electronics purchase",
            "I need approval for a ₹750,000 software license purchase", 
            "What policies do we have for supplier selection?",
            "Show me suppliers with good ratings and fast delivery"
        ]
        
        for i, scenario in enumerate(test_scenarios, 1):
            print(f"📝 Test Scenario {i}: {scenario}")
            print("-" * 50)
            
            try:
                result = await agent.analyze_with_policy_awareness(scenario)
                
                print(f"🎯 Strategy: {result['strategy']}")
                print(f"🎲 Confidence: {result.get('confidence', 0.0)*100:.0f}%")
                
                # Show AI reasoning if available
                if result.get('ai_reasoning'):
                    print(f"🧠 AI Reasoning: {result['ai_reasoning']}")
                if result.get('query_intent'):
                    print(f"💭 Query Intent: {result['query_intent']}")
                
                if 'supplier_selection' in result['strategy']:
                    print(f"📊 Original suppliers: {result['original_suppliers']}")
                    print(f"✅ Filtered suppliers: {len(result['filtered_suppliers'])}")
                    print(f"📋 Policy applied: {result['policy_applied']}")
                    
                    print("\n🔍 Policy Actions:")
                    for action in result['policy_actions']:
                        print(f"   {action}")
                        
                    print("\n💡 Recommendations:")
                    for rec in result['recommendations']:
                        print(f"   {rec}")
                        
                elif 'approval' in result['strategy']:
                    print(f"💰 Amount: ₹{result['amount']:,}")
                    print(f"📊 Approval Level: {result['approval_level']}")
                    print(f"👥 Required Approvers: {', '.join(result['required_approvers'])}")
                    
                    print("\n📋 Next Actions:")
                    for action in result['next_actions']:
                        print(f"   {action}")
                        
                elif 'policy_information' in result['strategy']:
                    print(f"📚 Available Policies: {result['total_policies']}")
                    
                    print("\n📋 Policy Details:")
                    for policy in result['available_policies']:
                        print(f"   • {policy['name']}: {policy['rules_count']} rules ({'Active' if policy['active'] else 'Inactive'})")
                
                # Show compliance requirements if available
                if result.get('compliance_requirements'):
                    print(f"\n⚖️ Compliance Requirements:")
                    for req in result['compliance_requirements']:
                        print(f"   • {req}")
                        
                if result.get('escalation_needed'):
                    print("🚨 Escalation Required!")
                        
            except Exception as e:
                print(f"❌ Error: {e}")
                
            print("\n" + "="*60 + "\n")
    
    asyncio.run(demo_with_config())