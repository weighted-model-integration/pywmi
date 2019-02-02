from setuptools import setup, find_packages
from os import path

# Distribute: python setup.py sdist upload
# python setup.py sdist bdist_wheel
# twine upload dist/*

setup_dir = path.abspath(path.dirname(__file__))
with open(path.join(setup_dir, "README.md")) as ref:
    long_description = ref.read()

setup(
    name='pywmi',
    version='0.3.24',
    description='Essential tools and interfaces for WMI',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='http://github.com/samuelkolb/pywmi',
    author='Samuel Kolb',
    author_email='samuel.kolb@me.com',
    license='MIT',
    packages=find_packages(),
    zip_safe=False,
    install_requires=['pysmt<0.8', 'numpy', 'future', 'typing', 'matplotlib', 'pillow', 'polytope', 'tabulate',
                      'graphviz', 'sympy', 'scipy', 'autodora', 'deprecated'],
    extras_require={
        'sdd': ["pysdd"]
    },
    setup_requires=['pytest-runner'],
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "pywmi-install = pywmi.install:main",
            "pywmi-cli = pywmi.__main__:parse"
        ]
    }
)
