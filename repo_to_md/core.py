import requests
import base64
import json
import mimetypes
import os
from huggingface_hub import HfApi
from pathlib import Path
import re
from typing import List, Tuple, Dict, Optional, Union

GITHUB_API = "https://api.github.com/repos/"

# A set of common text file extensions for quick binary/text classification
TEXT_EXTENSIONS = {
    'py', 'md', 'txt', 'js', 'html', 'css', 'json', 'toml', 'yaml', 'yml',
    'xml', 'csv', 'sh', 'bat', 'ini', 'cfg', 'conf', 'log', 'rst', 'gitignore',
    'sql', 'env', 'dockerfile'
}

def is_binary_content(filename: str, content: bytes) -> bool:
    """
    Determine if file content is binary by checking extension and content.
    Any file that is not determined to be text is considered binary.
    """
    file_path = Path(filename)
    extension = file_path.suffix[1:].lower()

    # 1. Check by common text extensions and special filenames
    if extension in TEXT_EXTENSIONS or file_path.name.lower() in ('dockerfile', '.gitignore'):
        return False

    # 2. Check by guessed MIME type
    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type and mime_type.startswith('text/'):
        return False

    # 3. Heuristic: Check for null bytes in the first chunk of the file.
    # This is a strong indicator for many binary formats.
    if b'\0' in content[:1024]:
        return True

    # 4. Final check: Try to decode the whole content. If it fails, it's binary.
    try:
        content.decode('utf-8')
        return False  # It's a text file if it decodes successfully
    except UnicodeDecodeError:
        return True   # It's a binary file if it fails to decode

def generate_file_tree(paths: List[str]) -> str:
    """Generate a simple file tree from a list of paths."""
    tree = ["📁 Root"]
    for path in sorted(paths):
        indent = "  " * (path.count('/'))
        tree.append(f"{indent}📄 {Path(path).name}")
    return "\n".join(tree) + "\n\n"

def fetch_files(owner: str, repo: str, path: str = "", is_hf: bool = False) -> Optional[List[Dict]]:
    """Recursively fetch all files from a repository (GitHub or Hugging Face)."""
    api_url = (
        f"https://huggingface.co/api/spaces/{owner}/{repo}/tree/main/{path.rstrip('/')}"
        if is_hf
        else f"{GITHUB_API}{owner}/{repo}/contents/{path.rstrip('/')}"
    )
    
    try:
        response = requests.get(api_url, headers={"Accept": "application/json"}, timeout=10)
        response.raise_for_status()
        if not response.headers.get('Content-Type', '').startswith('application/json'):
            return None
        items = response.json()
        
        files = []
        for item in items:
            if item.get('type') == 'file':
                files.append(item)
            elif item.get('type') == 'dir':
                sub_files = fetch_files(owner, repo, item['path'], is_hf)
                if sub_files:
                    files.extend(sub_files)
        return files
    except requests.RequestException:
        return None

def get_hf_files(owner: str, repo: str) -> List[Dict]:
    """Fetch all file paths from a Hugging Face Space."""
    api = HfApi(token=os.getenv('HF_TOKEN'))
    try:
        # HfApi.list_repo_files returns a list of file paths (str)
        file_paths = api.list_repo_files(repo_id=f'{owner}/{repo}', repo_type="space")
        # Return a list of dicts to be consistent with the structure from fetch_files
        return [{"path": path} for path in file_paths]
    except Exception:
        return []

def get_repo_contents(url: str) -> Tuple[Optional[str], Optional[str], Union[List[Dict], str], bool]:
    """Parse URL and fetch repository contents."""
    try:
        parts = url.rstrip('/').split('/')
        owner, repo = parts[-2], parts[-1]
        is_hf = "huggingface.co" in url.lower()
        files = get_hf_files(owner, repo) if is_hf else fetch_files(owner, repo)
        if not files:
            raise ValueError(f"No files found in {'Hugging Face Space' if is_hf else 'GitHub repository'}")
        return owner, repo, files, is_hf
    except Exception as e:
        return None, None, f"Error fetching repo contents: {str(e)}", False

def process_file_content(file_info: Dict, owner: str, repo: str, is_hf: bool = False) -> str:
    """Process individual file content from a repository."""
    file_path = file_info['path']
    try:
        response = requests.get(
            f"https://huggingface.co/spaces/{owner}/{repo}/raw/main/{file_path}" if is_hf
            else f"{GITHUB_API}{owner}/{repo}/contents/{file_path}",
            headers={"Accept": "application/json"} if not is_hf else {},
            timeout=10
        )
        response.raise_for_status()
        content_raw = response.content if is_hf else base64.b64decode(response.json()['content'])
        
        if is_binary_content(file_path, content_raw):
            return f"### File: {file_path}\n[Binary file - {len(content_raw)} bytes]\n\n"
        
        text_content = content_raw.decode('utf-8', errors='replace')
        file_extension = Path(file_path).suffix[1:].lower() or 'text'
        
        if file_extension == 'json':
            try:
                formatted_json = json.dumps(json.loads(text_content), indent=2)
                return f"### File: {file_path}\n```json\n{formatted_json}\n```\n\n"
            except json.JSONDecodeError:
                return f"### File: {file_path}\n```json\n{text_content}\n```\n[Note: Invalid JSON format]\n\n"
        return f"### File: {file_path}\n```{file_extension}\n{text_content}\n```\n\n"
    except Exception as e:
        return f"### File: {file_path}\n[Error fetching file content: {str(e)}]\n\n"

def process_uploaded_file(file: object) -> str:
    """Process uploaded file content."""
    filename = getattr(file, 'filename', 'unknown')
    try:
        content_raw = file.read()
        
        if is_binary_content(filename, content_raw):
            return f"### File: {filename}\n[Binary file - {len(content_raw)} bytes]\n\n"
        
        text_content = content_raw.decode('utf-8', errors='replace')
        file_extension = Path(filename).suffix[1:].lower() or 'text'
        
        if file_extension == 'json':
            try:
                formatted_json = json.dumps(json.loads(text_content), indent=2)
                return f"### File: {filename}\n```json\n{formatted_json}\n```\n\n"
            except json.JSONDecodeError:
                return f"### File: {filename}\n```json\n{text_content}\n```\n[Note: Invalid JSON format]\n\n"
        return f"### File: {filename}\n```{file_extension}\n{text_content}\n```\n\n"
    except Exception as e:
        return f"### File: {filename}\n[Error processing file: {str(e)}]\n\n"

def create_markdown_document(url: Optional[str] = None, files: Optional[List[object]] = None) -> str:
    """Create markdown document from repo contents or uploaded files."""
    if url:
        owner, repo, contents, is_hf = get_repo_contents(url)
        if isinstance(contents, str):
            return f"Error: {contents}"
        
        markdown_content = [
            f"# {'Space' if is_hf else 'Repository'}: {owner}/{repo}\n",
            "## File Structure\n```\n",
            generate_file_tree([item['path'] for item in contents]),
            "```\n\n",
            f"Below are the contents of all files in the {'space' if is_hf else 'repository'}:\n\n"
        ]
        markdown_content.extend(process_file_content(item, owner, repo, is_hf) for item in contents)
    else:
        markdown_content = [
            "# Uploaded Files\n",
            "## File Structure\n```\n",
            generate_file_tree([file.filename for file in files]),
            "```\n\n",
            "Below are the contents of all uploaded files:\n\n"
        ]
        markdown_content.extend(process_uploaded_file(file) for file in files)
    
    return "".join(markdown_content)

def markdown_to_files(markdown_text: str) -> Tuple[Union[List[Dict], str], Dict[str, bytes]]:
    """Convert a markdown document back into individual files."""
    files, buffers = [], {}
    current_filename, current_content = None, []
    is_binary, in_code_block = False, False

    for line in markdown_text.splitlines():
        if line.startswith("### File: "):
            if current_filename:
                content = "\n".join(current_content) if not is_binary else ""
                files.append({"filename": current_filename, "content": "[Binary File]" if is_binary else content, "is_binary": is_binary, "filepath": current_filename})
                buffers[current_filename] = b"[Binary content not stored]" if is_binary else content.encode('utf-8')
            current_filename, current_content = line[len("### File: "):].strip(), []
            is_binary, in_code_block = False, False
        elif line.startswith("[Binary file - ") and current_filename:
            is_binary = True
        elif line.startswith("```"):
            in_code_block = not in_code_block
        elif in_code_block and not is_binary and line != "```":
            current_content.append(line)

    if current_filename:
        content = "\n".join(current_content) if not is_binary else ""
        files.append({"filename": current_filename, "content": "[Binary File]" if is_binary else content, "is_binary": is_binary, "filepath": current_filename})
        buffers[current_filename] = b"[Binary content not stored]" if is_binary else content.encode('utf-8')

    return files or "Error: No files found in the markdown document.", buffers
