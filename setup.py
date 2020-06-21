import os

from setuptools import setup

readme = os.path.join(os.path.dirname(__file__), 'README.rst')

setup(
    name='zimports',
    version="0.2.1",
    description="yet another import fixing tool",
    long_description=open(readme).read(),
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 3',
    ],
    author='Mike Bayer',
    author_email='mike_mp@zzzcomputing.com',
    url='https://github.com/sqlalchemyorg/zimports',
    license='BSD',
    py_modules=('zimports', 'tests'),
    zip_safe=False,
    install_requires=['pyflakes', 'flake8-import-order'],
    tests_require=['mock'],
    entry_points={
        'console_scripts': ['zimports = zimports:main'],
    }
)
