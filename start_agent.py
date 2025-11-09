#!/usr/bin/env python3
"""
Multi-Tool Agent Startup Script
===============================

This script provides different modes for running the Multi-Tool Agent:
1. Server mode - Run the full FastMCP server (requires all dependencies)
2. Simple mode - Run simplified demo (no external dependencies needed)
3. Test mode - Run basic tests
"""

import asyncio
import sys
import os

def check_dependencies():
    """Check if required dependencies are available"""
    try:
        import fastmcp
        import openai
        return True, "All dependencies available"
    except ImportError as e:
        return False, f"Missing dependencies: {e}"

async def run_simple_demo():
    """Run the simplified demo"""
    from simple_demo import demo
    await demo()

async def run_dynamic_demo():
    """Run the dynamic MCP agent demo"""
    from dynamic_mcp_agent import demo
    await demo()

async def run_full_server():
    """Run the full FastMCP server"""
    try:
        from multi_tool_agent import MultiToolAgent, AgentConfig
        config = AgentConfig()
        agent = MultiToolAgent(config)
        await agent.run_server()
    except ImportError as e:
        print(f"❌ Cannot run full server: {e}")
        print("💡 Try running in simple mode: python start_agent.py simple")
        return False
    return True

async def run_tests():
    """Run basic tests"""
    print("🧪 Running basic tests...")
    from simple_demo import SimpleMultiToolAgent
    
    agent = SimpleMultiToolAgent()
    
    # Test single tool execution
    result = await agent.process_request("Show me purchase order PO123")
    assert result['success'], "Single tool test failed"
    
    # Test tool chain execution  
    result = await agent.process_request("Trace movement for purchase order TEST123")
    assert result['success'], "Tool chain test failed"
    
    # Test clarification
    result = await agent.process_request("What?")
    assert result['success'] and result['strategy'] == 'clarification', "Clarification test failed"
    
    print("✅ All tests passed!")

def show_help():
    """Show usage information"""
    print("""
🤖 Multi-Tool Agent Startup Script

Usage:
    python start_agent.py [mode]

Modes:
    server   - Run full FastMCP server (requires all dependencies)
    simple   - Run simplified demo (no external dependencies)
    dynamic  - Run dynamic MCP tool pool agent (LLM-driven orchestration)
    test     - Run basic functionality tests
    check    - Check dependency status
    help     - Show this help message

Examples:
    python start_agent.py simple    # Run simplified demo
    python start_agent.py dynamic   # Run dynamic MCP agent
    python start_agent.py server    # Run full server
    python start_agent.py test      # Run tests
    """)

async def main():
    """Main entry point"""
    mode = sys.argv[1] if len(sys.argv) > 1 else "simple"
    
    if mode == "help":
        show_help()
        return
    
    elif mode == "check":
        has_deps, msg = check_dependencies()
        print(f"Dependencies: {'✅ ' + msg if has_deps else '❌ ' + msg}")
        return
    
    elif mode == "simple":
        print("🚀 Starting Simple Multi-Tool Agent Demo...")
        await run_simple_demo()
    
    elif mode == "dynamic":
        print("🚀 Starting Dynamic MCP Tool Pool Agent...")
        await run_dynamic_demo()
        
    elif mode == "server":
        has_deps, msg = check_dependencies()
        if not has_deps:
            print(f"❌ Cannot run server mode: {msg}")
            print("💡 Try: python start_agent.py simple")
            return
        
        print("🚀 Starting Full Multi-Tool Agent Server...")
        await run_full_server()
        
    elif mode == "test":
        print("🧪 Running Agent Tests...")
        await run_tests()
        
    else:
        print(f"❌ Unknown mode: {mode}")
        show_help()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Agent stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)