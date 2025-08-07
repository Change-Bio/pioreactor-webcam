# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

setup(
    name="webcam_recorder",
    version="1.0.0",
    license_files = ('LICENSE.txt',),
    description="Webcam recorder plugin for continuous video recording with HLS streaming support",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author_email="noah@changebio.uk",
    author="Noah",
    url="https://github.com/pioreactor/pioreactor-webcam",
    packages=find_packages(),
    include_package_data=True,
    install_requires=["pioreactor>=23.6.0"],
    entry_points={
        "pioreactor.plugins": ["webcam_recorder = webcam_recorder"]
    },
)
