import asyncio
import os
from openai import AsyncOpenAI

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

async def main():
    api_key = os.getenv("OPEN_API_KEY")
    client = AsyncOpenAI(api_key=api_key)
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "hello"}],
            max_tokens=10
        )
        print("Success:", response.choices[0].message.content)
    except Exception as e:
        print("Error:", type(e), str(e))

if __name__ == "__main__":
    asyncio.run(main())
