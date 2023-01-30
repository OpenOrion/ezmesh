

from setuptools import setup

setup(
   name='ezmesh',
   version='1.0',
   description='the open source parametric CFD mesh generator',
   author='Afshawn Lotfi',
   author_email='',
   packages=['ezmesh'],
   install_requires=[
    "numpy",
    "gmsh"
   ]
)