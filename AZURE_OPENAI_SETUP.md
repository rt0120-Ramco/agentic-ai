# Azure OpenAI Setup Guide 🔧

## Your Azure OpenAI Configuration

Based on your Azure AI Foundry setup, here's how to configure your Dynamic MCP Agent:

### 📋 Your Azure Details
- **Resource Name**: `jsk-ai-v2-resource`
- **Endpoint**: `https://jsk-ai-v2-resource.openai.azure.com/`
- **Region**: South India (S0)

### 🔑 Steps to Complete Setup

#### 1. Get Your API Key
In your Azure AI Foundry portal:
1. Click the **copy** button (📋) next to the API Key (currently showing as dots)
2. Copy the full API key

#### 2. Update Your .env File
Replace `your-azure-openai-api-key` in the `.env` file with your actual key:
```bash
OPENAI_API_KEY=your-actual-azure-key-here
```

#### 3. Check Your Model Deployments
In Azure AI Foundry, go to **Model catalog** to see which models you have deployed:
- Common deployments: `gpt-4o`, `gpt-35-turbo`, `gpt-4`
- Update the `OPENAI_MODEL` in `.env` to match your deployment name

#### 4. Test the Configuration
```powershell
cd c:\github\agentic-ai
.venv\Scripts\Activate.ps1
python dynamic_mcp_agent.py
```

### 🎯 Expected Results

With Azure OpenAI configured, you should see:
```
🤖 Sending query to gpt-4o for analysis...
🧠 AI Model Response Length: 450 chars
✅ AI Analysis Complete - Strategy: tool_chain
```

Instead of:
```
⚠️ OpenAI not available - using simulation mode
```

### 🔧 Azure-Specific Configuration

Your `.env` file is already configured for Azure:
```bash
USE_AI_MODEL=True
OPENAI_API_KEY=your-azure-openai-api-key
OPENAI_BASE_URL=https://jsk-ai-v2-resource.openai.azure.com/
OPENAI_MODEL=gpt-4o
```

### 🛠️ Troubleshooting

#### If you get authentication errors:
1. **Check API Key**: Make sure you copied the full key from Azure
2. **Check Model Name**: Ensure the model name matches your Azure deployment
3. **Check Endpoint**: Verify the endpoint URL is correct

#### Common Azure Model Names:
- `gpt-4o` (most common)
- `gpt-35-turbo` (cheaper)
- `gpt-4` (if deployed)

#### Model Availability Check:
In Azure AI Foundry → **Model catalog** → Check which models are deployed in your resource.

### 💰 Azure OpenAI Benefits

✅ **Enterprise Security**: Your data stays in Azure  
✅ **Compliance**: Meets enterprise compliance requirements  
✅ **SLA**: Service Level Agreements  
✅ **Regional Control**: Data processed in South India region  
✅ **Cost Control**: Better cost management and budgeting  

### 🚀 Next Steps

1. Copy your API key from Azure portal
2. Update the `.env` file with the real key
3. Run the test to see real AI analysis in action!

Your Azure OpenAI setup is enterprise-grade and perfect for production use! 🎉