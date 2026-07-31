#! /usr/bin/env python3

from setuptools import find_packages, setup

setup(name="python-smsd-lan",
      version="0.0.9",
      description="SMSD LAN-series controller library",
      url="https://github.com/RAA80/python-smsd-lan",
      author="Alexey Ryadno",
      author_email="aryadno@mail.ru",
      license="MIT",
      packages=find_packages(),
      install_requires=["pymodbus >= 3.0, < 3.9", "pyserial >= 3.5"],
      platforms=["Linux", "Windows"],
      classifiers=["Development Status :: 3 - Alpha",
                   "Intended Audience :: Science/Research",
                   "Intended Audience :: Developers",
                   "License :: OSI Approved :: MIT License",
                   "Operating System :: Microsoft :: Windows",
                   "Operating System :: POSIX :: Linux",
                   "Operating System :: POSIX",
                   "Programming Language :: Python :: 3",
                   "Programming Language :: Python :: 3.9",
                   "Programming Language :: Python :: 3.10",
                   "Programming Language :: Python :: 3.11",
                  ],
     )
