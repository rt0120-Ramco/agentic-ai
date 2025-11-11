import asyncio
import os
from dotenv import load_dotenv
from openai import AsyncAzureOpenAI

# Load environment variables
load_dotenv()

async def main():
    # Get Azure OpenAI configuration from environment
    api_key = os.getenv('OPENAI_API_KEY')
    endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
    deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-5-mini')
    api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-08-01-preview')
    
    if not api_key or not endpoint:
        print("❌ Azure OpenAI credentials not found in environment variables")
        print("💡 Check your .env file for OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT")
        return
    
    try:
        # Initialize Azure OpenAI client with API key
        client = AsyncAzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version
        )
        
        print(f"🤖 Azure OpenAI initialized successfully with API key!")
        print(f"📍 Endpoint: {endpoint}")
        print(f"🧠 Model: {deployment}")
        print()
        
        # Create chat completion (using default parameters for gpt-5-mini)
        response = await client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": "You are good at telling jokes."},
                {"role": "user", "content": "Tell me a joke about a pirate."}
            ],
            max_completion_tokens=500
            # Note: temperature removed as gpt-5-mini only supports default (1.0)
        )
        
        print("🏴‍☠️ Pirate Joke:")
        print(response.choices[0].message.content)
        
        # Close the client
        await client.close()
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        print("💡 Check your Azure OpenAI configuration and API key")

if __name__ == "__main__":
    asyncio.run(main())