

from setuptools import setup

setup(
   name='ezmesh',
   version='3.6.5',
   description='the open source parametric CFD mesh generator',
   author='Afshawn Lotfi',
   author_email='',
   packages=['ezmesh', 'ezmesh.utils'],
   install_requires=[
    "numpy",
    "gmsh",
    "ipywidgets",
    "pythreejs",
    "su2fmt @ git+https://github.com/OpenOrion/su2fmt.git",
    "shapely",
    "scipy"
   ]
)
