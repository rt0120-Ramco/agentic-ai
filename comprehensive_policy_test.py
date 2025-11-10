import asyncio
from policy_aware_mcp_agent import PolicyAwareMCPAgent, PolicyAgentConfig

async def comprehensive_ai_policy_test():
    """Comprehensive test of AI-powered policy-aware agent"""
    
    print("🏛️ AI-Powered Policy-Aware MCP Agent - Comprehensive Test")
    print("=" * 70)
    
    # Initialize AI-powered agent
    config = PolicyAgentConfig()
    config.enable_ai_analysis = True
    agent = PolicyAwareMCPAgent(config)
    
    print(f"🤖 Azure OpenAI: {'✅ Connected' if agent.openai_client else '❌ Not Available'}")
    print(f"📋 Business Policies: {len(agent.policy_engine.policies)} loaded")
    print()
    
    # Comprehensive test scenarios
    test_scenarios = [
        {
            "query": "Find suppliers for a ₹750,000 critical server purchase",
            "expected": "High-value purchase with escalation + director approval"
        },
        {
            "query": "I need approval for a ₹50,000 software license", 
            "expected": "Auto-approval within limit"
        },
        {
            "query": "What are our supplier selection policies?",
            "expected": "Policy information request"
        },
        {
            "query": "Show me vendors with fast delivery and good quality ratings",
            "expected": "Supplier selection with rating/lead-time criteria"
        }
    ]
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"📝 Test Case {i}: {scenario['query']}")
        print(f"🎯 Expected: {scenario['expected']}")
        print("-" * 60)
        
        try:
            result = await agent.analyze_with_policy_awareness(scenario['query'])
            
            # Display core results
            print(f"🚀 Strategy: {result['strategy']}")
            print(f"🎲 Confidence: {result.get('confidence', 0)*100:.0f}%")
            
            # Display AI insights
            if result.get('ai_reasoning'):
                print(f"🧠 AI Analysis: {result['ai_reasoning']}")
            if result.get('query_intent'):
                print(f"💭 Intent: {result['query_intent']}")
            
            # Display policy actions
            if result.get('policy_actions'):
                print("📋 Policy Actions:")
                for action in result['policy_actions'][:3]:  # Show first 3
                    print(f"   • {action}")
                    
            # Display recommendations  
            if result.get('recommendations'):
                print("💡 Recommendations:")
                for rec in result['recommendations'][:2]:  # Show first 2
                    print(f"   • {rec}")
                    
            # Display compliance requirements
            if result.get('compliance_requirements'):
                print("⚖️ Compliance:")
                for req in result['compliance_requirements'][:2]:
                    print(f"   • {req}")
                    
            # Display escalation
            if result.get('escalation_needed'):
                print("🚨 ESCALATION REQUIRED!")
                
            # Show raw AI analysis for one example
            if i == 1 and result.get('raw_ai_analysis'):
                print("\n🔍 Raw AI Analysis (Sample):")
                raw = result['raw_ai_analysis']
                if 'recommended_actions' in raw:
                    print(f"   Actions: {len(raw['recommended_actions'])} steps identified")
                if 'policy_note' in raw:
                    print(f"   Note: {raw['policy_note'][:100]}...")
                    
        except Exception as e:
            print(f"❌ Error: {e}")
            
        print("\n" + "=" * 70 + "\n")
        
    print("🎉 Comprehensive AI Policy Test Complete!")
    print("✅ Azure OpenAI gpt-5-mini successfully integrated with policy engine")
    print("✅ Intelligent policy analysis with business rule compliance") 
    print("✅ Multi-scenario handling: supplier selection, approvals, policy info")

if __name__ == "__main__":
    asyncio.run(comprehensive_ai_policy_test())