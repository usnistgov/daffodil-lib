from setuptools import setup, find_packages

setup(
    name='daffodillib',
    version='1.0.0',    
    description='Library for the Daffodil prototyping system',
    url='https://github.com/osamayousuf/example', # Replace with public URL
    author='Osama Yousuf', # Replace
    author_email='osamayousuf@gwu.edu', # Replace
    license='BSD 2-clause',
    # packages=['daffodillib'],
    packages=find_packages(),
    install_requires=[
                      'numpy', 
                      'matplotlib',
                      'pandas',               
                      ],

    # complete list from https://pypi.org/pypi?%3Aaction=list_classifiers
    # useful when uploading to pypi
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: BSD License',  
        'Operating System :: POSIX :: Linux',        
        'Programming Language :: Python :: 3'
    ],
)