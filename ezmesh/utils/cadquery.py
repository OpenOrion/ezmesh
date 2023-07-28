import cadquery as cq
from jupyter_cadquery.viewer import show
import numpy as np


class ExtendedWorkplane(cq.Workplane):

    def addPhysicalGroup(self, name: str):
        pass


# Create a simple CAD model
s = cq.Workplane("XY")
sPnts = [
    (2.75, 1.5),
    (2.5, 1.75),
    (2.0, 1.5),
    (1.5, 1.0),
    (1.0, 1.25),
    (0.5, 1.0),
    (0, 1.0)
]
r = s.lineTo(3.0, 0).lineTo(3.0, 1.0).spline(sPnts, includeCurrent=True).close()
result = r.extrude(0.5)

# Export the CAD model to STEP format
cq.exporters.export(result, "result.step")

import gmsh






# Iterate over the faces and label them with their indexes
print("Faces:")
selected_faces = result.faces(">Y")
for i, face in enumerate(selected_faces.vals()):
    center_of_mass =  tuple(round(x, 5) for x in face.centerOfMass(face).toTuple())
    gmsh_surface_tag = gmsh_surface_tags[center_of_mass]


show(selected_faces)





# %%
