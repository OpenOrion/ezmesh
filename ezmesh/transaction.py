from dataclasses import dataclass
from typing import Literal, Optional, Protocol, Union

@dataclass
class Transaction:
    def __post_init__(self):
        self.is_commited: bool = False
        self.is_generated: bool = False

    def before_gen(self):
        "completes transaction before mesh generation."
        ...

    def after_gen(self):
        "completes transaction after mesh generation."
        ...
