import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


async def main() -> None:
    api_key = os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")
    model = os.getenv("OPENAI_MODEL", "deepseek-v4-flash")

    print(f"OPENAI_API_KEY={'configured' if api_key else 'missing'}")
    print(f"OPENAI_BASE_URL={base_url}")
    print(f"OPENAI_MODEL={model}")

    client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=30)
    response = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "只回复 OK"}],
        temperature=0,
    )
    print(response.choices[0].message.content)


if __name__ == "__main__":
    asyncio.run(main())
