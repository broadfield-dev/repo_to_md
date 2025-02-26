# Repo to Markdown

Convert GitHub or Hugging Face repositories, or local files, into a single Markdown document.

## Installation

### Core Package
Install the core functionality with required dependencies:

```
pip install repo_to_md
```

### With Demo UI
Install with the optional demo UI and its additional dependencies:

```
pip install repo_to_md[demo]
```

## Usage

### As a Library
Use the core functionality to generate Markdown:

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

### Running the Demo UI
If installed with the demo extra, run the Flask-based UI:

```python
from repo_to_md import run_demo

# Run the demo (default: http://localhost:7860)
run_demo()
```

Alternatively, run directly from the command line after installing with demo:

```
python -m repo_to_md.demo
```

Visit `http://localhost:7860` in your browser.

## Features

- Supports GitHub and Hugging Face Spaces
- Handles text and binary files
- Generates a file tree and formatted Markdown output

## Requirements

- Python 3.6+
- Core dependencies: `requests`, `huggingface_hub`
- Demo dependencies (optional, with `repo_to_md[demo]`): `flask`, `markdown`

## Contributing

Feel free to submit issues or pull requests to the [GitHub repository](https://github.com/yourusername/repo_to_md).

## License

This project is licensed under the MIT License.
