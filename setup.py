from setuptools import setup, find_packages

setup(
    name="repo_to_md",
    version="0.1.0",
    description="Convert GitHub/HF repositories or files into a single Markdown document",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Your Name",
    author_email="your.email@example.com",
    url="https://github.com/yourusername/repo_to_md",
    packages=["repo_to_md"],
    package_data={
        "repo_to_md": ["templates/*.html"],  # Include templates for demo
    },
    install_requires=[
        "requests",
        "huggingface_hub",
    ],
    extras_require={
        "demo": ["flask", "markdown"],  # Optional dependencies for demo
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
