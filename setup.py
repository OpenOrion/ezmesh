

from setuptools import setup

setup(
   name='meshql',
   version='3.6',
   description='the open source parametric CFD mesh generator',
   author='Afshawn Lotfi',
   author_email='',
   packages=['meshql', 'meshql.utils'],
   install_requires=[
    "numpy",
    "gmsh",
    "ipywidgets==7.6",
    "ipython_genutils",
    "pythreejs",
    "su2fmt @ git+https://github.com/Turbodesigner/su2fmt.git",
    "shapely",
    "scipy",
    "jupyter_cadquery"
   ]
)