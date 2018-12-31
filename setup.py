import os

from setuptools import setup

readme = os.path.join(os.path.dirname(__file__), 'README.rst')

setup(
    name='zimports',
    version="0.1.0",
    description="yet another import fixing tool",
    long_description=open(readme).read(),
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
    ],
    author='Mike Bayer',
    author_email='mike_mp@zzzcomputing.com',
    url='http://bitbucket.org/zzzeek/zimports',
    license='BSD',
    py_modules=('zimports', ),
    zip_safe=False,
    install_requires=['pyflakes'],
    entry_points={
        'console_scripts': ['zimports = zimports:main'],
    }
)
