from setuptools import setup, find_packages

# Distribute: python setup.py sdist upload

setup(
    name='pywmi',
    version='0.2.24',
    description='Essential tools and interfaces for WMI',
    url='http://github.com/samuelkolb/pywmi',
    author='Samuel Kolb',
    author_email='samuel.kolb@me.com',
    license='MIT',
    packages=find_packages(),
    zip_safe=False,
    install_requires=['pysmt', 'numpy', 'future', 'typing', 'matplotlib', 'pillow', 'polytope', 'tabulate', 'problog',
                      'graphviz'],
    setup_requires=['pytest-runner'],
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "pywmi-install = pywmi.install:main"
        ]
    }
)
