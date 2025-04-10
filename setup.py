import os
from setuptools import find_packages, setup


def read(file_path):
    with open(
        os.path.join(os.path.dirname(__file__), file_path),
        "r",
        encoding="utf-8",
    ) as f:
        return f.read()


setup(
    name="supersetapiplus",
    version="0.5.0",
    description="A framework to simplify access to Superset API endpoints and automate dashboard configuration.",
    long_description=read("README.md"),  # Reads directly from the README.md file
    long_description_content_type="text/markdown",
    author="Jailton Paiva",
    author_email="jailtoncarlos@gmail.com",
    url="https://github.com/jailtoncarlos/superset-api-plus",
    keywords=[
        "superset",
        "superset api",
        "apache superset",
        "superset dashboard automation",
        "supersetapiplus",
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Software Development :: Libraries",
    ],
    python_requires=">=3.7",
    install_requires=read("requirements/requirements-packaging.txt"),
    packages=find_packages(exclude=["tests*"]),
    include_package_data=True,
)
