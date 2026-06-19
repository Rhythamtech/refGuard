from typing import Any
from langchain_core.language_models import LanguageModelInput
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from keymesh import SchedulerStrategy, OpenAIHandler, AsyncOpenAIHandler
from dotenv import load_dotenv
import os

load_dotenv()

def get_llm()->ChatOpenAI:
    raw_keys = os.getenv("OPENAI_API_KEYS")
    api_keys = [k.strip() for k in raw_keys.split(",") if k.strip()] if raw_keys else []
    return ChatOpenAI(
        base_url = os.getenv("OPENAI_BASE_URL"),
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        api_key="dummy",
        max_retries=6,
        temperature=0.0,
        http_client=OpenAIHandler(keys=api_keys, strategy=SchedulerStrategy.ROUND_ROBIN),
        http_async_client=AsyncOpenAIHandler(keys=api_keys, strategy=SchedulerStrategy.ROUND_ROBIN)
    )    

def get_vision_llm() -> ChatOpenAI:
    raw_keys = os.getenv("OPENAI_API_KEYS")
    api_keys = [k.strip() for k in raw_keys.split(",") if k.strip()] if raw_keys else []
    return ChatOpenAI(
        base_url = os.getenv("OPENAI_BASE_URL"),
        model=os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini"),
        api_key="dummy",
        max_retries=6,
        temperature=0.0,
        http_client=OpenAIHandler(keys=api_keys, strategy=SchedulerStrategy.ROUND_ROBIN),
        http_async_client=AsyncOpenAIHandler(keys=api_keys, strategy=SchedulerStrategy.ROUND_ROBIN)
    )

def get_vision_llm_with_structured_output(schema: BaseModel)->Runnable[LanguageModelInput, Any]:
    return get_vision_llm().with_structured_output(schema) 

def get_llm_with_structured_output(schema: BaseModel)->Runnable[LanguageModelInput, Any]:
    return get_llm().with_structured_output(schema) 