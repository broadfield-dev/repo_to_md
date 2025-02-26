# Repo to Markdown

Convert GitHub or Hugging Face repositories, or local files, into a single Markdown document.

## Installation

Install the core package via pip:

```
pip install repo_to_md
```

## Usage

### As a Library

Use the package in your Python code to generate Markdown from repositories or files:

```python
from repo_to_md import create_markdown_document

# From a repository URL
markdown = create_markdown_document(url="https://github.com/username/repo")
print(markdown)

# From local files (file-like objects)
with open("file.txt", "rb") as f:
    markdown = create_markdown_document(files=[f])
    print(markdown)
```

### Optional Demo UI

The package includes a Flask-based demo UI in the repository, but it’s not installed with pip. To run it:

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/repo_to_md.git
   cd repo_to_md
   ```
2. Install demo dependencies:
   ```
   pip install flask markdown
   ```
3. Run the demo:
   ```
   python demo/app.py
   ```
4. Visit `http://localhost:7860` in your browser.

## Features

- Supports GitHub and Hugging Face Spaces
- Handles text and binary files
- Generates a file tree and formatted Markdown output

## Requirements

- Python 3.6+
- Core dependencies: `requests`, `huggingface_hub`
- Demo dependencies (optional): `flask`, `markdown`

## Contributing

Feel free to submit issues or pull requests to the [GitHub repository](https://github.com/yourusername/repo_to_md).

## License

This project is licensed under the MIT License.
