from pydantic import BaseModel
from datetime import datetime

class ImageResponse(BaseModel):
    image_id: int
    title: str | None
    file_path: str
    uploaded_at: datetime
    username: str

class UserResponse(BaseModel):
    user_id: int
    username: str
    role: str

class ErrorResponse(BaseModel):
    error: str