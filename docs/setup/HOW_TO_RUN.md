# 🚀 How to Run the Dynamic MCP Agent

## Overview
The Dynamic MCP Agent is an intelligent system that uses Azure OpenAI to orchestrate multiple tools in complex business workflows. It can handle single tool calls or multi-step chains automatically.

## 📋 Prerequisites

### 1. Python Environment
```powershell
# Ensure Python 3.8+ is installed
python --version

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. Required Dependencies
```powershell
# Install required packages
pip install openai httpx python-dotenv asyncio logging
```

### 3. Azure OpenAI Configuration
Create a `.env` file in the project root:
```env
AZURE_OPENAI_API_KEY=your_api_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-5-mini
AZURE_OPENAI_API_VERSION=2024-08-01-preview
```

## 🎯 Running the System

### Basic Execution
```powershell
# Navigate to project directory
cd c:\github\agentic-ai

# Activate virtual environment
.venv\Scripts\Activate.ps1

# Run the dynamic agent
python dynamic_mcp_agent.py
```

### With Specific Encoding (Recommended)
```powershell
# Set UTF-8 encoding for better output
$env:PYTHONIOENCODING="utf-8"
python dynamic_mcp_agent.py
```

## 📊 Understanding the Output

### Execution Flow
The system processes 5 different test queries automatically:

1. **Simple PO Lookup**: `"Show me PO12345"`
2. **Location Tracking**: `"Where is my order DYN456 right now?"`  
3. **Complete PR Analysis**: `"Get me everything about purchase request PR789"`
4. **Quality Inspection**: `"Check quality inspection for receipt GR2024"`
5. **Post-Delivery Status**: `"What happened to order ABC999 after delivery?"`

### Log Output Format
```
2025-11-10 06:02:57,119 - __main__ - INFO - 🎯 Processing dynamic request [Session: 7c031102]: Show me PO12345
2025-11-10 06:02:57,120 - __main__ - INFO - 🤖 Sending query to gpt-5-mini for analysis...
2025-11-10 06:03:01,265 - __main__ - INFO - ✅ AI Analysis Complete - Strategy: single_tool
2025-11-10 06:03:01,266 - __main__ - INFO - 🔧 Step 1/1: Executing view_purchase_order
2025-11-10 06:03:01,475 - __main__ - INFO - ✅ Dynamic execution completed [Session: 7c031102] - 1 tools used
```

### Key Indicators
- 🎯 **Request Processing**: Shows the user query being analyzed
- 🤖 **AI Analysis**: Azure OpenAI processing the request
- ✅ **Strategy Selection**: Single tool vs multi-step chain
- 🔧 **Tool Execution**: Each step in the workflow
- ✅ **Completion**: Final results with tool count

## 🔍 Monitoring and Debugging

### Check for Issues
```powershell
# Look for any warnings or errors
python dynamic_mcp_agent.py 2>&1 | Select-String -Pattern "warning|error|failed"

# Check parameter resolution (should be clean now)
python dynamic_mcp_agent.py 2>&1 | Select-String -Pattern "Placeholder not found|Parameter"
```

### Verbose Output
```powershell
# See detailed HTTP requests
python dynamic_mcp_agent.py 2>&1 | Select-String -Pattern "HTTP Request|AI Model Response"
```

## 📈 Expected Performance

### Success Metrics
- **Single Tool Queries**: Complete in ~4-6 seconds
- **3-Step Chains**: Complete in ~12-15 seconds  
- **6-Step Chains**: Complete in ~25-30 seconds
- **Zero Warnings**: No placeholder or parameter resolution issues

### Tool Chain Examples

#### Simple Query (1 tool)
```
Query: "Show me PO12345"
→ view_purchase_order(po_number="PO12345")
Result: PO details displayed
```

#### Complex Chain (3 tools)  
```
Query: "Where is my order DYN456 right now?"
→ view_purchase_order(po_number="DYN456")
→ help_on_receipt_document(po_reference="DYN456") 
→ view_movement_details(receipt_no="found_receipt")
Result: Current location and movement history
```

#### Comprehensive Analysis (6 tools)
```
Query: "Get me everything about purchase request PR789"
→ view_purchase_request(pr_number="PR789")
→ search_purchase_orders(pr_reference="PR789")
→ view_purchase_order(po_number="found_po")
→ help_on_receipt_document(po_reference="found_po")
→ view_movement_details(receipt_no="found_receipt")
→ view_inspection_details(receipt_no="found_receipt")
Result: Complete PR-to-inspection workflow
```

## 🛠️ Troubleshooting

### Common Issues

#### 1. Azure OpenAI Connection
```powershell
# Test connection
python -c "from openai import AsyncAzureOpenAI; print('OpenAI package available')"
```

#### 2. Environment Variables
```powershell
# Check .env file loading
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(f'Endpoint: {os.getenv(\"AZURE_OPENAI_ENDPOINT\")}')"
```

#### 3. Virtual Environment
```powershell
# Verify activation
Get-Command python
# Should show path to .venv\Scripts\python.exe
```

## 🎯 Customization

### Modify Test Queries
Edit the `test_queries` list in `dynamic_mcp_agent.py`:
```python
test_queries = [
    "Your custom query here",
    "Another business question",
    # Add more as needed
]
```

### Adjust Logging Level
```python
# In dynamic_mcp_agent.py
logging.basicConfig(level=logging.DEBUG)  # More verbose
logging.basicConfig(level=logging.WARNING)  # Less verbose
```

## 📞 Support

If you encounter issues:
1. Check the console output for specific error messages
2. Verify Azure OpenAI credentials and deployment name
3. Ensure all dependencies are installed
4. Confirm virtual environment is activated

---
*Last Updated: November 10, 2025 | Production Ready*