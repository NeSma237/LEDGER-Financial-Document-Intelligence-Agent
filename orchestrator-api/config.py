import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    AGENT_SERVICE_URL: str = os.getenv("AGENT_SERVICE_URL", "http://localhost:8003")
    VALIDATOR_SERVICE_URL: str = os.getenv("VALIDATOR_SERVICE_URL", "http://localhost:8005")
    DOC_PROCESSOR_URL: str = os.getenv("DOC_PROCESSOR_URL", "http://localhost:8001")
    RETRIEVAL_SERVICE_URL: str = os.getenv("RETRIEVAL_SERVICE_URL", "http://localhost:8002")
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
    ORCHESTRATOR_PORT: int = int(os.getenv("ORCHESTRATOR_PORT", "8000"))


settings = Settings()
