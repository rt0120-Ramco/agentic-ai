import asyncio
from policy_aware_mcp_agent import PolicyAwareMCPAgent, PolicyAgentConfig
import os

async def test_ai_integration():
    config = PolicyAgentConfig()
    config.enable_ai_analysis = True
    agent = PolicyAwareMCPAgent(config)
    
    print("🤖 AI Client Available:", agent.openai_client is not None)
    
    result = await agent.analyze_with_policy_awareness('Find suppliers for a ₹300,000 electronics purchase')
    print("🎯 Strategy:", result.get('strategy', 'unknown'))
    print("🎲 Confidence:", f"{result.get('confidence', 0)*100:.0f}%")
    
    if result.get('ai_reasoning'):
        print("🧠 AI Reasoning:", result['ai_reasoning'][:150] + "...")
    if result.get('query_intent'):
        print("💭 Query Intent:", result['query_intent'])
    
    print("\n" + "="*50)
    print("✅ AI Integration Test Complete!")

if __name__ == "__main__":
    asyncio.run(test_ai_integration())