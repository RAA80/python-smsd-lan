#! /usr/bin/env python3

from setuptools import setup

setup(name="python-smsd-lan",
      version="0.0.3",
      description="SMSD LAN-series controller library",
      url="https://github.com/RAA80/python-smsd-lan",
      author="Alexey Ryadno",
      author_email="aryadno@mail.ru",
      license="MIT",
      packages=["smsd"],
      install_requires=["pyserial >= 3.4"],
      platforms=["Linux", "Windows"],
      classifiers=["Development Status :: 3 - Alpha",
                   "Intended Audience :: Science/Research",
                   "Intended Audience :: Developers",
                   "License :: OSI Approved :: MIT License",
                   "Operating System :: Microsoft :: Windows",
                   "Operating System :: POSIX :: Linux",
                   "Operating System :: POSIX",
                   "Programming Language :: Python :: 3",
                   "Programming Language :: Python :: 3.8",
                   "Programming Language :: Python :: 3.9",
                   "Programming Language :: Python :: 3.10",
                   "Programming Language :: Python :: 3.11",
                  ],
     )
