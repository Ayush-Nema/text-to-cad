from typing import List

from pydantic import BaseModel


class DesignInstructions(BaseModel):
    object_name: str
    summary: str
    design_instructions: List[str]
