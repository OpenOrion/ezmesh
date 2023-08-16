from dataclasses import dataclass
from typing import Literal, Optional, Protocol, Union
import uuid

@dataclass
class Transaction:
    def __post_init__(self):
        self.is_commited: bool = False
        self.is_generated: bool = False
        self.id = uuid.uuid4()
    
    def before_gen(self):
        "completes transaction before mesh generation."
        ...

    def after_gen(self):
        "completes transaction after mesh generation."
        ...

    def __hash__(self) -> int:
        return self.id.__hash__()

    def __eq__(self, __value: object) -> bool:
        return self.id.__eq__(__value)