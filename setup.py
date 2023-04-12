

from setuptools import setup

setup(
   name='ezmesh',
   version='3.1',
   description='the open source parametric CFD mesh generator',
   author='Afshawn Lotfi',
   author_email='',
   packages=['ezmesh', 'ezmesh.utils'],
   install_requires=[
    "numpy",
    "gmsh",
    "ipywidgets==7.6",
    "pythreejs",
    "su2fmt @ git+https://github.com/Turbodesigner/su2fmt.git"
   ]
)