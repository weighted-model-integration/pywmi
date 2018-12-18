from setuptools import setup, find_packages

# Distribute: python setup.py sdist upload

setup(
    name='pywmi',
    version='0.2.18',
    description='Essential tools and interfaces for WMI',
    url='http://github.com/samuelkolb/pywmi',
    author='Samuel Kolb',
    author_email='samuel.kolb@me.com',
    license='MIT',
    packages=find_packages(),
    zip_safe=False,
    install_requires=['pysmt', 'numpy', 'future', 'typing', 'matplotlib', 'pillow', 'polytope', 'tabulate', 'problog'],
    setup_requires=['pytest-runner'],
    tests_require=["pytest"],
)
