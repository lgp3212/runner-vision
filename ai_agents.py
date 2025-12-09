import openai
import os
from dotenv import load_dotenv
from typing import List, Dict

load_dotenv()

# to be called in main


class SafetyAnalysisAgent:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in .env file")
        self.client = openai.OpenAI(api_key=api_key)

    def make_call_to_llm(self, metadata):
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """You are a running safety expert analyzing route options for runners in NYC. 
                Safety scores are calculated based on comparing danger data to averages in that area.
                There are several segments per route. Additional information is included for dangerous segments. 
                Route length accuracy must also be considered in recommendation. 
                Focus on practical advice that helps runners make informed decisions.""",
                },
                {"role": "user", "content": str(metadata)},
            ],
            temperature=0.3,
            max_tokens=800,
        )
        print(response)
        return response
