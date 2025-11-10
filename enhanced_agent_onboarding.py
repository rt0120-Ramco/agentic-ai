#!/usr/bin/env python3
"""
Enhanced Agent Onboarding System
================================

Complete system for onboarding specialized agents like supplier-filter-agent
with comprehensive policy management, MCP tool orchestration, and LLM-powered execution.

Features:
- YAML-based agent configuration
- Policy-aware workflow execution  
- MCP tool pool management
- Azure OpenAI integration
- Real-time agent registration and execution
"""

import asyncio
import json
import logging
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

# Import our components
from agent_registry_system import AgentRegistry, SpecializedAgent
from supplier_agent_parser import SupplierAgentParser
from policy_aware_mcp_agent import PolicyAwareMCPAgent

logger = logging.getLogger(__name__)

class EnhancedAgentOnboardingSystem:
    """Enhanced system for agent onboarding and management"""
    
    def __init__(self):
        self.agent_registry = AgentRegistry()
        self.supplier_parser = SupplierAgentParser()
        self.policy_engine = None
        self.onboarded_agents = {}
        
        # Initialize policy engine
        self._initialize_policy_engine()
        
    def _initialize_policy_engine(self):
        """Initialize the policy-aware MCP agent for enhanced capabilities"""
        try:
            self.policy_engine = PolicyAwareMCPAgent()
            logger.info("✅ Policy engine initialized for enhanced agent capabilities")
        except Exception as e:
            logger.warning(f"⚠️ Policy engine initialization failed: {e}")
            
    async def onboard_supplier_agent(self, yaml_path: str) -> Dict[str, Any]:
        """Onboard a supplier agent from YAML configuration"""
        
        onboard_id = f"onboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"🚀 Starting agent onboarding [ID: {onboard_id}]")
        
        try:
            # Step 1: Parse YAML configuration
            logger.info("📋 Step 1: Parsing YAML configuration...")
            agent_def = self.supplier_parser.parse_yaml_file(yaml_path)
            
            # Step 2: Validate agent configuration
            logger.info("✅ Step 2: Validating agent configuration...")
            validation_result = await self._validate_agent_config(agent_def)
            
            if not validation_result['valid']:
                raise ValueError(f"Agent validation failed: {validation_result['errors']}")
                
            # Step 3: Register agent in registry
            logger.info("🔧 Step 3: Registering agent in system...")
            self.agent_registry.agents[agent_def.agent_id] = agent_def
            
            # Step 4: Initialize specialized agent instance
            logger.info("⚙️ Step 4: Initializing agent instance...")
            specialized_agent = SpecializedAgent(agent_def, self.agent_registry.openai_client)
            await specialized_agent.initialize()
            
            # Step 5: Register active agent
            self.agent_registry.active_agents[agent_def.agent_id] = specialized_agent
            self.onboarded_agents[agent_def.agent_id] = {
                "agent_def": agent_def,
                "specialized_agent": specialized_agent,
                "onboard_date": datetime.now(),
                "onboard_id": onboard_id
            }
            
            # Step 6: Test agent capabilities  
            logger.info("🧪 Step 5: Testing agent capabilities...")
            test_results = await self._test_agent_capabilities(agent_def.agent_id)
            
            onboard_result = {
                "onboard_id": onboard_id,
                "agent_id": agent_def.agent_id,
                "agent_name": agent_def.name,
                "status": "success",
                "validation": validation_result,
                "test_results": test_results,
                "policies_count": len(agent_def.policies),
                "tools_count": len(agent_def.tools),
                "workflow_steps_count": len(agent_def.workflow_steps),
                "capabilities": self._analyze_agent_capabilities(agent_def),
                "onboard_timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"🎉 Agent onboarding completed successfully [ID: {onboard_id}]")
            return onboard_result
            
        except Exception as e:
            logger.error(f"❌ Agent onboarding failed [ID: {onboard_id}]: {e}")
            return {
                "onboard_id": onboard_id,
                "status": "failed",
                "error": str(e),
                "onboard_timestamp": datetime.now().isoformat()
            }
            
    async def _validate_agent_config(self, agent_def) -> Dict[str, Any]:
        """Validate agent configuration"""
        
        errors = []
        warnings = []
        
        # Check required fields
        if not agent_def.agent_id:
            errors.append("Missing agent_id")
        if not agent_def.name:
            errors.append("Missing agent name")
        if not agent_def.policies:
            warnings.append("No policies defined")
        if not agent_def.tools:
            warnings.append("No tools defined")
        if not agent_def.workflow_steps:
            errors.append("No workflow steps defined")
            
        # Validate policies
        active_policies = [p for p in agent_def.policies if p.active]
        if not active_policies:
            warnings.append("No active policies found")
            
        # Validate tool availability
        missing_tools = []
        for step in agent_def.workflow_steps:
            tool_available = any(tool.name == step.tool_name for tool in agent_def.tools)
            if not tool_available:
                missing_tools.append(step.tool_name)
                
        if missing_tools:
            warnings.append(f"Missing tool definitions: {', '.join(missing_tools)}")
            
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "policies_validated": len(agent_def.policies),
            "tools_validated": len(agent_def.tools),
            "steps_validated": len(agent_def.workflow_steps)
        }
        
    async def _test_agent_capabilities(self, agent_id: str) -> Dict[str, Any]:
        """Test agent capabilities with sample workitem"""
        
        test_workitem = {
            "purchase_request_id": "PR-TEST-001",
            "user_id": "test.user@company.com",
            "ou": "US_CENTRAL",
            "buyer": "test_buyer",
            "test_mode": True,
            "notification_recipients": ["test.user@company.com"]
        }
        
        try:
            result = await self.agent_registry.execute_agent_workflow(agent_id, test_workitem)
            
            return {
                "test_status": "success",
                "execution_id": result.get("execution_id"),
                "steps_executed": len(result.get("results", [])),
                "strategy_analysis": result.get("strategy", {}).get("analysis", "")[:100] + "...",
                "execution_time": result.get("execution_time")
            }
            
        except Exception as e:
            return {
                "test_status": "failed",
                "error": str(e)
            }
            
    def _analyze_agent_capabilities(self, agent_def) -> Dict[str, Any]:
        """Analyze agent capabilities and features"""
        
        capabilities = {
            "policy_management": len(agent_def.policies) > 0,
            "multi_policy_support": len(agent_def.policies) > 1,
            "llm_integration": bool(agent_def.llm_prompt_template),
            "workflow_automation": len(agent_def.workflow_steps) > 0,
            "mcp_tool_integration": len(agent_def.tools) > 0,
            "notification_support": any("notification" in step.name.lower() for step in agent_def.workflow_steps),
            "po_creation": any("po" in step.name.lower() for step in agent_def.workflow_steps),
            "supplier_evaluation": any("evaluation" in step.name.lower() for step in agent_def.workflow_steps)
        }
        
        # Policy analysis
        policy_features = []
        for policy in agent_def.policies:
            if "rating" in policy.description.lower():
                policy_features.append("rating_based_selection")
            if "lead time" in policy.description.lower():
                policy_features.append("lead_time_optimization")
            if "quality" in policy.description.lower():
                policy_features.append("quality_assurance")
            if "delivery" in policy.description.lower():
                policy_features.append("delivery_performance")
                
        capabilities["policy_features"] = list(set(policy_features))
        
        # Workflow analysis
        workflow_patterns = []
        step_names = [step.name.lower() for step in agent_def.workflow_steps]
        
        if any("supplier" in name and "mapping" in name for name in step_names):
            workflow_patterns.append("supplier_discovery")
        if any("rating" in name for name in step_names):
            workflow_patterns.append("supplier_rating")
        if any("evaluation" in name for name in step_names):
            workflow_patterns.append("intelligent_selection")
        if any("po" in name for name in step_names):
            workflow_patterns.append("order_automation")
        if any("notification" in name for name in step_names):
            workflow_patterns.append("stakeholder_communication")
            
        capabilities["workflow_patterns"] = workflow_patterns
        
        return capabilities
        
    async def execute_onboarded_agent(self, agent_id: str, workitem: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a workitem using an onboarded agent"""
        
        if agent_id not in self.onboarded_agents:
            raise ValueError(f"Agent {agent_id} not found in onboarded agents")
            
        logger.info(f"🎯 Executing onboarded agent: {agent_id}")
        
        # Execute using the agent registry
        result = await self.agent_registry.execute_agent_workflow(agent_id, workitem)
        
        # Add onboarding metadata
        result["onboard_info"] = {
            "onboard_id": self.onboarded_agents[agent_id]["onboard_id"],
            "onboard_date": self.onboarded_agents[agent_id]["onboard_date"].isoformat()
        }
        
        return result
        
    async def list_onboarded_agents(self) -> List[Dict[str, Any]]:
        """List all onboarded agents with their status"""
        
        agents_list = []
        
        for agent_id, agent_info in self.onboarded_agents.items():
            agent_def = agent_info["agent_def"]
            
            # Check if agent is still active
            is_active = agent_id in self.agent_registry.active_agents
            
            agents_list.append({
                "agent_id": agent_id,
                "name": agent_def.name,
                "description": agent_def.description,
                "version": agent_def.version,
                "status": "active" if is_active else "inactive",
                "onboard_date": agent_info["onboard_date"].isoformat(),
                "onboard_id": agent_info["onboard_id"],
                "policies": [{"name": p.name, "active": p.active} for p in agent_def.policies],
                "tools_count": len(agent_def.tools),
                "workflow_steps_count": len(agent_def.workflow_steps),
                "capabilities": self._analyze_agent_capabilities(agent_def)
            })
            
        return agents_list
        
    async def get_agent_policy_details(self, agent_id: str) -> Dict[str, Any]:
        """Get detailed policy information for an agent"""
        
        if agent_id not in self.onboarded_agents:
            raise ValueError(f"Agent {agent_id} not found")
            
        agent_def = self.onboarded_agents[agent_id]["agent_def"]
        
        policy_details = []
        for policy in agent_def.policies:
            # Get workflow steps for this policy
            policy_steps = [step for step in agent_def.workflow_steps if policy.policy_id in step.step_id]
            
            policy_details.append({
                "policy_id": policy.policy_id,
                "name": policy.name,
                "description": policy.description,
                "active": policy.active,
                "priority": policy.priority,
                "rules_count": len(policy.rules),
                "rules": policy.rules,
                "workflow_steps": [
                    {
                        "step_name": step.name,
                        "tool_name": step.tool_name,
                        "description": step.description,
                        "required": step.required
                    }
                    for step in policy_steps
                ],
                "steps_count": len(policy_steps)
            })
            
        return {
            "agent_id": agent_id,
            "agent_name": agent_def.name,
            "policies": policy_details,
            "total_policies": len(policy_details),
            "active_policies": len([p for p in policy_details if p["active"]])
        }

# Demo function
async def demo_enhanced_onboarding():
    """Demonstrate the enhanced agent onboarding system"""
    
    print("🚀 Enhanced Agent Onboarding System Demo")
    print("=" * 70)
    
    # Initialize the onboarding system
    onboarding_system = EnhancedAgentOnboardingSystem()
    
    print(f"🤖 Azure OpenAI: {'✅ Connected' if onboarding_system.agent_registry.openai_client else '❌ Simulation Mode'}")
    print(f"📋 Policy Engine: {'✅ Available' if onboarding_system.policy_engine else '❌ Not Available'}")
    print()
    
    # Onboard the supplier-filter-agent
    print("📋 Onboarding supplier-filter-agent.yml...")
    print("-" * 50)
    
    try:
        onboard_result = await onboarding_system.onboard_supplier_agent("supplier-filter-agent.yml")
        
        if onboard_result["status"] == "success":
            print(f"✅ Onboarding successful [ID: {onboard_result['onboard_id']}]")
            print(f"🏷️ Agent: {onboard_result['agent_name']}")
            print(f"📋 Policies: {onboard_result['policies_count']}")
            print(f"🔧 Tools: {onboard_result['tools_count']}")
            print(f"⚙️ Workflow Steps: {onboard_result['workflow_steps_count']}")
            
            # Show capabilities
            capabilities = onboard_result['capabilities']
            print(f"\n🎯 Capabilities:")
            for feature, enabled in capabilities.items():
                if isinstance(enabled, bool):
                    status = "✅" if enabled else "❌"
                    print(f"   {status} {feature.replace('_', ' ').title()}")
                elif isinstance(enabled, list) and enabled:
                    print(f"   📋 {feature.replace('_', ' ').title()}: {', '.join(enabled)}")
                    
            # Show validation results
            validation = onboard_result['validation']
            if validation['warnings']:
                print(f"\n⚠️ Warnings: {len(validation['warnings'])}")
                for warning in validation['warnings']:
                    print(f"   • {warning}")
                    
            # Show test results
            test_results = onboard_result['test_results']
            print(f"\n🧪 Test Results:")
            print(f"   Status: {'✅ Passed' if test_results['test_status'] == 'success' else '❌ Failed'}")
            if test_results['test_status'] == 'success':
                print(f"   Execution ID: {test_results.get('execution_id', 'N/A')}")
                print(f"   Steps Executed: {test_results.get('steps_executed', 0)}")
                print(f"   Strategy: {test_results.get('strategy_analysis', 'N/A')}")
                
        else:
            print(f"❌ Onboarding failed: {onboard_result['error']}")
            return
            
    except Exception as e:
        print(f"❌ Onboarding error: {e}")
        return
        
    # List onboarded agents
    print(f"\n📋 Onboarded Agents:")
    print("-" * 30)
    agents = await onboarding_system.list_onboarded_agents()
    
    for agent in agents:
        print(f"🤖 {agent['name']} ({agent['status']})")
        print(f"   ID: {agent['agent_id']}")
        print(f"   Onboarded: {agent['onboard_date']}")
        print(f"   Policies: {len(agent['policies'])} ({len([p for p in agent['policies'] if p['active']])} active)")
        print()
        
    # Show policy details for the first agent
    if agents:
        agent_id = agents[0]['agent_id']
        print(f"📋 Policy Details for {agents[0]['name']}:")
        print("-" * 50)
        
        policy_details = await onboarding_system.get_agent_policy_details(agent_id)
        
        for policy in policy_details['policies']:
            status = "✅ Active" if policy['active'] else "❌ Inactive"
            print(f"\n🏷️ {policy['name']} ({status})")
            print(f"   Description: {policy['description'][:100]}...")
            print(f"   Rules: {policy['rules_count']}")
            print(f"   Workflow Steps: {policy['steps_count']}")
            
            # Show first few steps
            for i, step in enumerate(policy['workflow_steps'][:3]):
                print(f"      {i+1}. {step['step_name']} → {step['tool_name']}")
            if len(policy['workflow_steps']) > 3:
                print(f"      ... and {len(policy['workflow_steps']) - 3} more steps")
                
    # Execute a sample workitem
    if agents:
        print(f"\n🎯 Executing Sample Workitem:")
        print("-" * 40)
        
        sample_workitem = {
            "purchase_request_id": "PR-DEMO-001",
            "user_id": "demo.user@company.com",
            "ou": "US_CENTRAL",
            "buyer": "demo_procurement_team",
            "category": "electronics",
            "priority": "high",
            "notification_recipients": ["demo.user@company.com", "procurement@company.com"]
        }
        
        print(f"📋 Workitem: {sample_workitem}")
        
        try:
            execution_result = await onboarding_system.execute_onboarded_agent(agent_id, sample_workitem)
            
            print(f"\n✅ Execution completed!")
            print(f"   Execution ID: {execution_result['execution_id']}")
            print(f"   Agent: {execution_result['agent_name']}")
            print(f"   Strategy: {execution_result['strategy'].get('analysis', 'N/A')[:80]}...")
            print(f"   Steps Executed: {len(execution_result['results'])}")
            
            # Show step results
            for i, step_result in enumerate(execution_result['results'][:3]):
                status = "✅" if step_result['status'] == 'success' else "❌"
                print(f"      {i+1}. {status} {step_result['step_name']}")
            if len(execution_result['results']) > 3:
                print(f"      ... and {len(execution_result['results']) - 3} more steps")
                
        except Exception as e:
            print(f"❌ Execution failed: {e}")

if __name__ == "__main__":
    asyncio.run(demo_enhanced_onboarding())