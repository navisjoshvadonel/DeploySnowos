from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4
from typing import Optional

class Role(str, Enum):
    ADMIN = "admin"
    DEVELOPER = "developer"
    VIEWER = "viewer"
    SYSTEM = "system"

@dataclass
class User:
    user_id: UUID
    username: str
    role: Role
    public_key: Optional[str] = None
    status: str = "active"
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

    def to_dict(self):
        return {
            "user_id": str(self.user_id),
            "username": self.username,
            "role": self.role.value,
            "public_key": self.public_key,
            "status": self.status,
            "created_at": self.created_at.isoformat()
        }
