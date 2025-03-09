# repo_to_md / md_to_repo

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

`repo_to_md` is a Python package that converts GitHub or Hugging Face Spaces repositories, or local files, into a single, well-structured Markdown document.  It's designed to create human-readable summaries of codebases, complete with file trees and formatted code snippets.  It also includes a reverse functionality to convert the generated Markdown back into individual files, and a Flask-based web UI for easy use.

## Features

*   **Repository Conversion:**  Fetches and processes both GitHub repositories and Hugging Face Spaces.
*   **Local File Support:**  Handles multiple local files (provided as file-like objects).
*   **File Tree Generation:**  Creates a clear, indented file tree representation of the repository or uploaded files.
*   **Formatted Code Output:**  Presents code with syntax highlighting (using language detection) and proper formatting for JSON files.
*   **Binary File Handling:**  Identifies and reports binary files with their sizes.
*   **Error Handling:**  Gracefully handles common errors like invalid URLs, network issues, and JSON decoding problems.
*   **Markdown to Files (Reverse Conversion):**  Converts the generated Markdown back into the original file structure, with separate files.
*   **Interactive Web UI (Optional):** A Flask-based web interface for easy interaction, allowing users to input a repository URL or upload files, view the Markdown output, preview rendered HTML, and download the results. It also supports extracting files from the markdown back to their original form, including a zip download.
*   **HTML Preview and Inlining:**  In the "Markdown to Files" mode, the demo automatically inlines CSS and JavaScript into HTML files, creating self-contained HTML previews.  If multiple HTML files are present, they are displayed in separate iframes. If no HTML files are present, it displays a file tree preview.

## Installation

There are two ways to install `repo_to_md`, depending on whether you need the interactive demo UI.

### 1. Core Package (No UI)

This installs only the core functionality and its dependencies (`requests` and `huggingface_hub`).  Use this if you only need the Python library features.

```bash
pip install git+https://github.com/broadfield-dev/repo_to_md.git@dev#egg=repo_to_md[main]
```

### 2. With Demo UI

This installs the core package *and* the dependencies needed for the web UI (`flask` and `markdown`).
This calls the 'dev' branch of the repo that has the reverse markdown to repo function.

```bash
pip install git+https://github.com/broadfield-dev/repo_to_md.git@dev#egg=repo_to_md[demo]
```

## Usage

### As a Library (Core Functionality)

The core function is `create_markdown_document`.  It can take either a repository URL or a list of file-like objects.

```python
from repo_to_md import create_markdown_document

# --- From a GitHub or Hugging Face Spaces URL ---
url = "https://github.com/broadfield-dev/repo_to_md"  # Example: Use a real URL
# url = "https://huggingface.co/spaces/your_username/your_space" # Or a Hugging Face Space
markdown_output = create_markdown_document(url=url)

if markdown_output.startswith("Error:"):
    print(markdown_output)  # Handle potential errors
else:
    print(markdown_output)
    # Or, save to a file:
    with open("repo_summary.md", "w", encoding="utf-8") as f:
        f.write(markdown_output)

# --- From Local Files ---
#  You need to provide a list of *file-like objects* (objects with a .read() method)
#  The objects should also have a 'filename' attribute.
import io
file_data1 = io.BytesIO(b"print('Hello from file1')")
file_data1.filename = "file1.py"

file_data2 = io.BytesIO(b'{"message": "Hello from file2"}')
file_data2.filename = "file2.json"

files = [file_data1, file_data2]

markdown_output = create_markdown_document(files=files)
print(markdown_output)
 # Or, save to a file:
with open("files_summary.md", "w", encoding="utf-8") as f:
    f.write(markdown_output)



# --- Markdown to Files (Reverse Conversion) ---
from repo_to_md.core import markdown_to_files

# Assuming you have a Markdown string called 'markdown_text'
file_data, file_buffers = markdown_to_files(markdown_output) # Use the output from previous examples

if isinstance(file_data, str) and file_data.startswith("Error:"):
  print(file_data)  # Handle potential errors
else:
    # Display the file data
    for file_info in file_data:
        print(f"Filename: {file_info['filename']}")
        print(f"Is Binary: {file_info['is_binary']}")
        print(f"Filepath: {file_info['filepath']}")
        if not file_info['is_binary']:
          print(f"Content:\n{file_info['content']}\n")

    #  Access the file buffers (for downloading or further processing)
    #  for filename, content in file_buffers.items():
    #    with open(filename, "wb") as f:
    #        f.write(content)


```

### As a Demo (Web UI)

If you installed `repo_to_md` with the `[demo]` extra, you can run the interactive web application.

1.  **Run the Demo:**

    ```bash
    python -m repo_to_md.demo
    ```
    This will start the Flask development server.  By default, it runs on `http://localhost:7860`.

2.  **Access the UI:** Open your web browser and go to `http://localhost:7860`.

3.  **Usage:**

    *   **Repo to Markdown Tab:**
        *   **Repository URL:** Enter a GitHub or Hugging Face Spaces URL in the input field and click "Convert URL".
        *   **Upload Files:**  Click the "Choose Files" button to select multiple files or a directory (using the `webkitdirectory` attribute, supported by most modern browsers) and click "Convert Files".
        *   **Output:** The Markdown output and a rendered HTML preview will be displayed.  You can copy the Markdown or download it as a `.md` file.
    *  **Markdown to Files Tab:**
        *  **Upload a markdown File:** Click the "Choose File" button to select your markdown file
        *  **Paste Markdown text:** You can also paste the Markdown in the text area.
        *   **Extract Files:** Click the extract files button to convert it into the original file structure.
        * **Output:** The UI will display the files found in the markdown, with the option to view the contents, or download them individually, or all together inside a .zip file.  The combined HTML preview will also show all the HTML content inlined, inside an iframe.

    The UI also includes a light/dark mode toggle.

## Project Structure

```
repo_to_md/
├── LICENSE
├── README.md          <- This file
├── requirements.txt
├── setup.py
└── repo_to_md/
    ├── __init__.py
    ├── core.py          <- Core logic for Markdown conversion
    ├── demo.py          <- Flask web application
    ├── static/
    │   └── styles.css   <- Styles for the web UI
    │   └── script.js    <- JavaScript for the web UI
    └── templates/
        └── index.html   <- Main HTML template for the web UI
```

## Requirements

*   **Python 3.6+**
*   **Core Dependencies:**
    *   `requests`: For making HTTP requests to GitHub and Hugging Face APIs.
    *   `huggingface_hub`: For interacting with Hugging Face Spaces.
*   **Demo Dependencies (Optional):**
    *   `flask`: For the web application framework.
    *   `markdown`: For rendering Markdown to HTML.

## Contributing

Contributions are welcome! Please feel free to open issues or submit pull requests on the [GitHub repository](https://github.com/broadfield-dev/repo_to_md).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
