from langchain_core.language_models import LanguageModelInput
from langchain_openai.chat_models.base import _DictOrPydantic
from langchain_core.runnables import Runnable
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

def get_llm()->ChatOpenAI:
    return ChatOpenAI(
        base_url = os.getenv("OPENAI_BASE_URL"),
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        api_key=os.getenv("OPENAI_API_KEY")
    )    

def get_vision_ll() -> ChatOpenAI:
    return ChatOpenAI(
        base_url = os.getenv("OPENAI_BASE_URL"),
        model=os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini"),
        api_key=os.getenv("OPENAI_API_KEY")
    )

def get_vision_llm_with_structured_output(schema: BaseModel)->Runnable[LanguageModelInput]:
    return get_vision_ll().with_structured_output(schema) 

def get_llm_with_structured_output(schema: BaseModel)->Runnable[LanguageModelInput]:
    return get_llm().with_structured_output(schema) 