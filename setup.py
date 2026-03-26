from setuptools import setup, find_packages

setup(
    name="aiknowledge-cli",
    version="0.1.0",
    description="AI 知识库问答 CLI — 基于 Friday 知识库",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "openai>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "aiknowledge=aiknowledge.cli:main",
        ],
    },
)
