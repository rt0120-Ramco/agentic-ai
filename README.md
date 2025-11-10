# 🚀 Agent Onboarding System

A comprehensive **agent onboarding and management platform** that allows you to register and execute specialized AI agents with their own business policies, MCP tools, and LLM-powered workflows.

## ✨ Key Features

- **🤖 Agent Registry & Management**: YAML-based agent configuration with automatic validation and registration
- **📋 Policy-Aware Execution**: Business policy integration with rule-based decision making 
- **🔧 MCP Tool Integration**: 14 production-ready tools for complete procurement workflows
- **⛓️ Workflow Orchestration**: LLM-driven strategy determination and step-by-step execution
- **🎯 Context Mapping**: Seamless data flow between workflow steps with parameter validation
- **📊 Real-time Monitoring**: Complete execution tracking with comprehensive logging and analytics

## 🎯 What's New

✅ **Complete Agent Onboarding System** - Register agents from YAML configurations  
✅ **Context Mapping Fixes** - All supplier_codes, item_codes, items warnings resolved  
✅ **Production-Ready MCP Tools** - 14 tools for procurement workflow automation  
✅ **Policy-Aware Agents** - Business rule integration with natural language processing  
✅ **Azure OpenAI Integration** - gpt-5-mini for intelligent workflow strategy determination

## 📚 Documentation

**Complete documentation is available in the [docs/](docs/) folder:**

- 📖 **[Documentation Index](docs/README.md)** - Complete documentation overview
- 🚀 **[Agent Onboarding Guide](docs/guides/AGENT_ONBOARDING_SYSTEM.md)** - ⭐ **START HERE** - Main system guide
- ⚙️ **[Setup Instructions](docs/setup/HOW_TO_RUN.md)** - Installation and configuration
- 🏗️ **[Architecture Overview](docs/architecture/DYNAMIC_AGENT_SOLUTION.md)** - System design
- 🔧 **[Troubleshooting](docs/troubleshooting/ISSUES_RESOLVED.md)** - Solutions and fixes

## 🚀 Quick Start

### 1. Installation
```bash
git clone <repository-url>
cd agentic-ai
pip install -r requirements.txt
```

### 2. Configuration  
```bash
# Copy environment template
cp .env.example .env
# Edit .env with your Azure OpenAI credentials
```

### 3. Run Agent Onboarding System
```bash
python enhanced_agent_onboarding.py
```

### 4. Register Your Own Agents
```bash
# Copy and modify the sample agent configuration
cp supplier-filter-agent.yml my-agent.yml
# Edit my-agent.yml with your agent policies and tools
```

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   User Query    │────│  MultiTool Agent │────│  FastMCP Server │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │ LLM Orchestrator │
                       └──────────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
        ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
        │Single Tool  │ │Tool Chain   │ │Clarification│
        │Execution    │ │Execution    │ │Request      │
        └─────────────┘ └─────────────┘ └─────────────┘
```

## 🛠️ Components

### 1. **Multi-Tool Agent** (`multi_tool_agent.py`)
- Main orchestrator that coordinates all components
- Handles FastMCP server setup and request routing
- Manages execution sessions and monitoring

### 2. **LLM Orchestrator** (`MultiToolOrchestrator` class)
- Analyzes user queries using Azure OpenAI
- Determines execution strategies (single tool, tool chain, clarification)
- Generates tool execution plans with parameter mapping

### 3. **Agent Client** (`agent_client.py`)
- Demonstrates how to interact with the agent
- Provides both demo and interactive modes
- Shows proper MCP protocol usage

### 4. **Startup Script** (`start.py`)
- Easy startup with multiple execution modes
- Environment setup and configuration checking
- Built-in help and testing capabilities

## 📋 Installation & Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
# Copy example configuration
cp .env.example .env

# Edit .env file with your settings
# At minimum, configure Azure OpenAI for LLM capabilities
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key-here
AZURE_OPENAI_DEPLOYMENT=gpt-4
```

### 3. Start the Agent
```bash
# Start agent server
python start.py server

# Or run tests
python start.py test

# Or run interactive client
python start.py interactive
```

## 🎯 Usage Examples

### Single Tool Queries
```
Query: "Show me details of purchase order JSLTEST46"
→ Strategy: single_tool
→ Tool: view_purchase_order
→ Parameters: {"po_number": "JSLTEST46"}
```

### Tool Chain Queries  
```
Query: "Trace complete movement flow for purchase request PR123"
→ Strategy: tool_chain
→ Chain: 
  1. view_purchase_request(pr_number="PR123")
  2. search_purchase_orders(pr_no_from="PR123")
  3. help_on_receipt_document(ref_doc_no_from="{{PoNo}}")
  4. view_movement_details(receipt_no="{{ReceiptNo}}")
```

### Clarification Requests
```
Query: "Show me something about purchases"
→ Strategy: clarification
→ Response: "What specific information do you need?"
→ Suggestions: ["View specific PO", "Search orders", "Check status"]
```

## 🔧 Configuration Options

### Agent Configuration (`AgentConfig`)
- `max_tool_chain_length`: Maximum tools in a chain (default: 5)
- `execution_timeout`: Timeout for operations (default: 120s)
- `mcp_host/port`: Server binding configuration

### Azure OpenAI Settings
- `AZURE_OPENAI_ENDPOINT`: Your Azure OpenAI endpoint
- `AZURE_OPENAI_API_KEY`: API key for authentication
- `AZURE_OPENAI_DEPLOYMENT`: Model deployment name (e.g., "gpt-4")

## 📊 Execution Monitoring

The agent provides detailed execution metrics:

```json
{
  "session_id": "uuid-here",
  "user_query": "original query",
  "strategy": "tool_chain",
  "tool_executions": [
    {
      "tool_name": "search_purchase_orders", 
      "parameters": {"pr_no_from": "PR123"},
      "result": {...},
      "execution_time": 0.5,
      "timestamp": "2024-11-09T10:30:00"
    }
  ],
  "total_execution_time": 2.3,
  "success": true
}
```

## 🚀 Running the Agent

### Server Mode
```bash
python start.py server
# Starts FastMCP server on localhost:8001
```

### Test Mode
```bash
python start.py test
# Runs predefined test scenarios
```

### Interactive Mode
```bash
python start.py interactive
# Start interactive query session
```

### Client Demo
```bash
python start.py client
# Runs client demonstration
```

## 🔍 Example Interactions

### Purchase Order Flow
```bash
🎯 Query: "Find all receipts for PO JSLTEST46 and show movement details"

📊 Strategy: tool_chain
✅ Success: true
⏱️ Execution Time: 1.245s

🔧 Tools Used: 3
   1. view_purchase_order (0.234s) - ✅
   2. help_on_receipt_document (0.456s) - ✅  
   3. view_movement_details (0.555s) - ✅

📄 Result Type: tool_chain_result
```

### Clarification Example
```bash
🎯 Query: "What's the status?"

📊 Strategy: clarification
✅ Success: true

💬 Clarification: "What specific status information do you need?"
💡 Suggestions: View PO status, Check PR approval, Review receipt status
```

## 🧪 Testing & Development

The agent includes comprehensive testing capabilities:

- **Unit Tests**: Test individual components
- **Integration Tests**: Test complete workflows
- **Performance Tests**: Monitor execution timing
- **Error Scenarios**: Test error handling and recovery

## 🔒 Security & Best Practices

- **Environment Variables**: Sensitive data stored in .env files
- **Input Validation**: All user inputs validated and sanitized
- **Error Isolation**: Failures in one tool don't affect others
- **Timeout Protection**: Prevents runaway executions
- **Logging**: Comprehensive audit trail

## 🤝 Integration with Existing Systems

The agent is designed to integrate with:

- **Ramco ERP APIs**: Direct integration with purchase/procurement systems
- **Custom Tools**: Easy addition of new tools via FastMCP
- **External LLMs**: Support for different LLM providers
- **Monitoring Systems**: JSON-structured logging for analysis

## 📈 Performance Characteristics

- **Startup Time**: < 2 seconds
- **Query Processing**: 0.5-3 seconds (depending on chain complexity)
- **Memory Usage**: ~50-100MB base, scales with concurrent requests
- **Concurrent Requests**: Supports multiple simultaneous users

## 🛣️ Future Enhancements

- **Tool Discovery**: Automatic discovery of available tools
- **Learning Capabilities**: Learn from successful query patterns
- **Multi-Modal Support**: Handle images, documents, and other formats
- **Workflow Persistence**: Save and resume complex workflows
- **Advanced Analytics**: Detailed performance and usage analytics

## 📞 Support & Troubleshooting

### Common Issues

1. **LLM Not Available**
   - Check Azure OpenAI configuration in `.env`
   - Verify API key and endpoint

2. **Tool Execution Failures**
   - Check tool availability and parameters
   - Review execution logs for details

3. **Timeout Errors**
   - Increase `execution_timeout` in configuration
   - Simplify complex queries

### Getting Help

- Check logs in console output
- Use `python start.py test` to verify setup
- Review configuration in `.env` file

---

**Built with ❤️ using FastMCP, Azure OpenAI, and modern async Python**