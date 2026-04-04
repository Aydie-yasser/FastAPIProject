from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    full_name: str = Field(max_length=255)
    email: EmailStr = Field(max_length=320)
    password: str = Field(max_length=255)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str = Field(max_length=255)
    email: EmailStr = Field(max_length=320)
