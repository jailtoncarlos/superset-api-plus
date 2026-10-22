import os

from setuptools import find_packages, setup


def read(file_path):
    with open(
        os.path.join(os.path.dirname(__file__), file_path),
        encoding="utf-8",
    ) as f:
        return f.read()


setup(
    name="supersetapiclient",
    version="0.5.0",
    description="Framework that makes it easier to obtain the parameters and "
                "settings needed to query data in TabNet Web",
    long_description=read("README.md"),  # Read directly from README.md
    long_description_content_type="text/markdown",
    author="Jailton Paiva",
    author_email="jailtoncarlos@gmail.com",
    keywords=["superset", "superset api", "superset-api-client", "supersetapiclient"],
    classifiers=[
        "Development Status :: 1 - Planning",
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
    python_requires=">=3.10",
    install_requires=read("requirements/requirements-packaging.txt"),
    packages=find_packages(exclude=["tests*"]),
    url="",
    include_package_data=True,
)
