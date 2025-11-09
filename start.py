#!/usr/bin/env python3
"""
Multi-Tool Agent Startup Script
==============================

This script provides easy startup options for the Multi-Tool Orchestrator Agent.
"""

import asyncio
import sys
import os
import logging
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

def setup_environment():
    """Setup environment and check requirements"""
    
    # Check if .env file exists, if not create from example
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if not env_file.exists() and env_example.exists():
        print("📋 Creating .env file from example...")
        env_file.write_text(env_example.read_text())
        print("✅ Created .env file. Please configure your settings.")
        return False
    
    # Load environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ Environment variables loaded")
        return True
    except ImportError:
        print("❌ python-dotenv not found. Run: pip install -r requirements.txt")
        return False

def check_azure_openai_config():
    """Check if Azure OpenAI is configured"""
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    
    if not endpoint or not api_key:
        print("⚠️  Azure OpenAI not configured. Agent will run in simulation mode only.")
        print("   Configure AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY in .env file")
        return False
    
    print("✅ Azure OpenAI configuration found")
    return True

async def run_agent_server():
    """Run the agent server"""
    try:
        from multi_tool_agent import MultiToolAgent, AgentConfig
        
        config = AgentConfig()
        agent = MultiToolAgent(config)
        
        print("🚀 Starting Multi-Tool Orchestrator Agent...")
        await agent.run_server()
        
    except ImportError as e:
        print(f"❌ Missing dependencies: {e}")
        print("Run: pip install -r requirements.txt")
    except Exception as e:
        print(f"❌ Error starting agent: {e}")

async def run_agent_test():
    """Run agent tests"""
    try:
        from multi_tool_agent import main
        print("🧪 Running agent tests...")
        await main()
    except Exception as e:
        print(f"❌ Test error: {e}")

async def run_client_demo():
    """Run client demo"""
    try:
        from agent_client import run_demo
        print("🤖 Running client demo...")
        await run_demo()
    except Exception as e:
        print(f"❌ Client demo error: {e}")

async def run_interactive_client():
    """Run interactive client"""
    try:
        from agent_client import interactive_mode
        print("💬 Starting interactive client...")
        await interactive_mode()
    except Exception as e:
        print(f"❌ Interactive client error: {e}")

def print_help():
    """Print help information"""
    print("""
🤖 Multi-Tool Orchestrator Agent
===============================

Usage: python start.py [command]

Commands:
  server      - Start the agent server (default)
  test        - Run agent tests
  client      - Run client demo
  interactive - Run interactive client
  help        - Show this help

Examples:
  python start.py server       # Start agent server
  python start.py test         # Run tests
  python start.py client       # Demo client interactions
  python start.py interactive  # Interactive query mode

Configuration:
  - Copy .env.example to .env and configure your settings
  - Install requirements: pip install -r requirements.txt
  - Configure Azure OpenAI for LLM capabilities (optional)
""")

async def main():
    """Main entry point"""
    
    # Parse command line arguments
    command = sys.argv[1] if len(sys.argv) > 1 else "server"
    
    if command == "help":
        print_help()
        return
    
    print("🤖 Multi-Tool Orchestrator Agent")
    print("=" * 40)
    
    # Setup environment
    if not setup_environment():
        return
    
    # Check configuration
    check_azure_openai_config()
    
    print()
    
    # Route to appropriate command
    if command == "server":
        await run_agent_server()
    elif command == "test":
        await run_agent_test()
    elif command == "client":
        await run_client_demo()
    elif command == "interactive":
        await run_interactive_client()
    else:
        print(f"❌ Unknown command: {command}")
        print("Use 'python start.py help' for usage information")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
    except Exception as e:
        print(f"❌ Startup error: {e}")