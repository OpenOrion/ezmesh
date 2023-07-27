from typing import Protocol
from ezmesh.geometry.entity import MeshContext, GeoEntity


class Field(Protocol):
    def after_sync(self, ctx: MeshContext, entity: GeoEntity):
        "completes transaction after syncronization and returns tag."
        ...
