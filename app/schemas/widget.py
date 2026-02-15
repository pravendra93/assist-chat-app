from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from uuid import UUID

class WidgetConfigResponse(BaseModel):
    tenant_id: UUID
    chat_title: str = "Chat with us"
    primary_color: str = "#000000"
    welcome_message: str = "Hello! How can we help you today?"
    bot_name: str = "Support AI"
    logo_url: Optional[str] = None
    background_color: Optional[str] = None
    position: Optional[str] = "bottom-right"
    suggested_questions: List[str] = []
    # Add other config fields as needed

class WidgetChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = {}

class WidgetChatResponse(BaseModel):
    response: str = Field(..., alias="answer") # Align with chat.py 'answer' but keep 'response' for widget if preferred
    session_id: str
    metadata: Dict[str, Any] = {}

    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }
