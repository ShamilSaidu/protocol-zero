#!/usr/bin/env python3
"""Quick verification script for the Groq API configuration."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq


def test_groq() -> int:
    load_dotenv()

    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key or api_key == "your_groq_api_key_here":
        print("ERROR: GROQ_API_KEY not set in .env file")
        return 1

    llm = ChatGroq(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        temperature=0.1,
        api_key=api_key,
    )
    response = llm.invoke("Reply with exactly: 'Protocol Zero is ready.'")
    print(f"Groq response: {response.content}")

    if "Protocol Zero" not in response.content:
        print("ERROR: Groq API test failed")
        return 1

    print("SUCCESS: Groq API is working!")
    return 0


if __name__ == "__main__":
    raise SystemExit(test_groq())
