"""Setup for code-logger CLI. Use: pip install . or pip install -e ."""
from setuptools import setup, find_packages

setup(
    name="code-logger-cli",
    version="0.1.0",
    description="CLI for Code Logger - integratable with any IDE",
    python_requires=">=3.9",
    packages=find_packages(include=["code_logger_cli", "code_logger_cli.*"]),
    install_requires=["requests>=2.28.0"],
    entry_points={
        "console_scripts": [
            "code-logger=code_logger_cli.commands:main",
        ],
    },
)
