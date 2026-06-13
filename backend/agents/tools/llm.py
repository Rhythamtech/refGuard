from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

def get_llm()->ChatOpenAI:
    return ChatOpenAI(
        model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.2")),
        api_key=os.getenv("OPENAI_API_KEY")
    )   


def get_llm_with_structured_output(schema: BaseModel):
    return get_llm().with_structured_output(schema) 