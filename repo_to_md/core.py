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

TEXT_EXTENSIONS = {
    'py', 'md', 'txt', 'js', 'html', 'css', 'json', 'toml', 'yaml', 'yml',
    'xml', 'csv', 'sh', 'bat', 'ini', 'cfg', 'conf', 'rst',
    'sql', 'ts', 'tsx', 'jsx', 'c', 'cpp', 'h', 'hpp', 'java', 'go',
    'php', 'rb', 'pl', 'swift', 'kt', 'kts', 'dart', 'scala', 'hs', 'lua',
    'r', 'ps1', 'svg'
}

TEXT_FILENAMES = {
    'dockerfile', 'license', 'readme', 'requirements.txt',
    'setup.py', 'gemfile', 'procfile', 'makefile'
}

EXCLUDE_EXTENSIONS = {'.lock', '.log', '.env', '.so', '.o', '.a', '.dll', '.exe'}
EXCLUDE_FILENAMES = {'.gitignore', '.DS_Store'}
EXCLUDE_PATTERNS = {'__pycache__/', '.git/', 'node_modules/'}

def is_excluded(filepath: str) -> bool:
    path = Path(filepath)
    if path.name in EXCLUDE_FILENAMES:
        return True
    if path.suffix.lower() in EXCLUDE_EXTENSIONS:
        return True
    if any(pattern in filepath for pattern in EXCLUDE_PATTERNS):
        return True
    return False

def is_binary_content(filename: str, content: bytes) -> bool:
    if not content:
        return False

    file_path = Path(filename)
    extension = file_path.suffix[1:].lower()

    if extension in TEXT_EXTENSIONS or file_path.name.lower() in TEXT_FILENAMES:
        return False

    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type and mime_type.startswith('text/'):
        return False

    if content.startswith((b'\xef\xbb\xbf', b'\xfe\xff', b'\xff\xfe')):
        return False

    sample = content[:1024]
    if b'\0' in sample:
        return True

    text_chars = set(bytes(range(32, 127)) + b'\n\r\t\f\b')
    if len(sample) > 0:
        non_text_ratio = sum(1 for byte in sample if byte not in text_chars) / len(sample)
        if non_text_ratio > 0.30:
            return True

    try:
        content.decode('utf-8')
        return False
    except UnicodeDecodeError:
        return True

def generate_file_tree(paths: List[str]) -> str:
    tree = ["📁 Root"]
    for path in sorted(paths):
        indent = "  " * (path.count('/'))
        tree.append(f"{indent}📄 {Path(path).name}")
    return "\n".join(tree) + "\n\n"

def fetch_files(owner: str, repo: str, path: str = "", is_hf: bool = False) -> Optional[List[Dict]]:
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
    api = HfApi(token=os.getenv('HF_TOKEN'))
    try:
        file_paths = api.list_repo_files(repo_id=f'{owner}/{repo}', repo_type="space")
        return [{"path": path} for path in file_paths]
    except Exception:
        return []

def get_repo_contents(url: str) -> Tuple[Optional[str], Optional[str], Union[List[Dict], str], bool]:
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
    if url:
        owner, repo, contents, is_hf = get_repo_contents(url)
        if isinstance(contents, str):
            return f"Error: {contents}"
        
        contents = [item for item in contents if not is_excluded(item['path'])]
        if not contents:
            return f"Error: No non-excluded files found in the repository."

        markdown_content = [
            f"# {'Space' if is_hf else 'Repository'}: {owner}/{repo}\n",
            "## File Structure\n```\n",
            generate_file_tree([item['path'] for item in contents]),
            "```\n\n",
            f"Below are the contents of all files in the {'space' if is_hf else 'repository'}:\n\n"
        ]
        markdown_content.extend(process_file_content(item, owner, repo, is_hf) for item in contents)
    else:
        files = [file for file in files if not is_excluded(file.filename)]
        if not files:
            return f"Error: No non-excluded files were uploaded."

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
