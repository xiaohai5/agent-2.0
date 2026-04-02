from pydantic import BaseModel


class UploadResponse(BaseModel):
    filename: str
    message: str


class DocumentItem(BaseModel):
    id: int
    filename: str
    status: str
