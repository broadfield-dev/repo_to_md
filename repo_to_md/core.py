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

EXCLUDE_EXTENSIONS = {'.lock', '.log', '.env', '.so', '.o', '.a', '.dll', '.exe', '.ipynb'}
EXCLUDE_FILENAMES = {'.gitignore', '.DS_Store'}
EXCLUDE_PATTERNS = {'__pycache__/', '.git/', 'node_modules/', 'dist/', 'build/'}

HEADERS = {"Accept": "application/json"}
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
if GITHUB_TOKEN:
    HEADERS['Authorization'] = f'token {GITHUB_TOKEN}'

def is_excluded(filepath: str) -> bool:
    path = Path(filepath)
    if path.name in EXCLUDE_FILENAMES or path.suffix.lower() in EXCLUDE_EXTENSIONS:
        return True
    normalized_path = path.as_posix()
    if any(pattern in normalized_path for pattern in EXCLUDE_PATTERNS):
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
    structure = {}
    for path in sorted(paths):
        parts = path.split('/')
        current_level = structure
        for part in parts:
            current_level = current_level.setdefault(part, {})

    def build_tree(level_structure, indent=""):
        for name in sorted(level_structure.keys()):
            is_dir = bool(level_structure[name])
            icon = "📁" if is_dir else "📄"
            tree.append(f"{indent}{icon} {name}")
            if is_dir:
                build_tree(level_structure[name], indent + "  ")

    build_tree(structure)
    return "\n".join(tree) + "\n\n"

def get_github_files_recursive(owner: str, repo: str) -> Tuple[Optional[List[Dict]], Optional[str]]:
    try:
        repo_info_url = f"{GITHUB_API}{owner}/{repo}"
        repo_response = requests.get(repo_info_url, headers=HEADERS, timeout=10)
        repo_response.raise_for_status()
        default_branch = repo_response.json()['default_branch']

        branch_info_url = f"{GITHUB_API}{owner}/{repo}/branches/{default_branch}"
        branch_response = requests.get(branch_info_url, headers=HEADERS, timeout=10)
        branch_response.raise_for_status()
        tree_sha = branch_response.json()['commit']['commit']['tree']['sha']

        tree_url = f"{GITHUB_API}{owner}/{repo}/git/trees/{tree_sha}?recursive=1"
        tree_response = requests.get(tree_url, headers=HEADERS, timeout=30)
        tree_response.raise_for_status()

        files = [
            {"path": item['path']}
            for item in tree_response.json()['tree']
            if item['type'] == 'blob'
        ]
        return files, default_branch

    except requests.RequestException as e:
        error_message = f"Error fetching from GitHub API: {e}. "
        if 'rate limit' in str(e).lower() and not GITHUB_TOKEN:
            error_message += "You may have hit the rate limit. Please set a GITHUB_TOKEN environment variable."
        raise ConnectionError(error_message) from e

def get_hf_files(owner: str, repo: str) -> List[Dict]:
    try:
        api = HfApi(token=os.getenv('HF_TOKEN'))
        file_paths = api.list_repo_files(repo_id=f'{owner}/{repo}', repo_type="space")
        return [{"path": path} for path in file_paths]
    except Exception as e:
        raise ConnectionError(f"Error fetching from Hugging Face Hub: {e}") from e

def get_repo_contents(url: str) -> Tuple[Optional[str], Optional[str], Optional[str], Union[List[Dict], str], bool]:
    try:
        parts = url.rstrip('/').split('/')
        owner, repo = parts[-2], parts[-1]
        is_hf = "huggingface.co" in url.lower()
        default_branch = None

        if is_hf:
            files = get_hf_files(owner, repo)
        else:
            files, default_branch = get_github_files_recursive(owner, repo)

        if not files:
            error_msg = f"No files found in {'Hugging Face Space' if is_hf else 'GitHub repository'}."
            if not is_hf and not GITHUB_TOKEN:
                 error_msg += " If this is a private repo or you've hit a rate limit, please set a GITHUB_TOKEN."
            raise ValueError(error_msg)
            
        return owner, repo, default_branch, files, is_hf
    except Exception as e:
        return None, None, None, f"Error fetching repo contents: {str(e)}", False

def process_file_content(file_info: Dict, owner: str, repo: str, default_branch: Optional[str] = None, is_hf: bool = False) -> str:
    file_path = file_info['path']
    try:
        if is_hf:
            url = f"https://huggingface.co/spaces/{owner}/{repo}/raw/main/{file_path}"
            response = requests.get(url, timeout=10)
        else:
            url = f"https://raw.githubusercontent.com/{owner}/{repo}/{default_branch}/{file_path}"
            response = requests.get(url, timeout=10)

        response.raise_for_status()
        content_raw = response.content
        
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

    except requests.RequestException as e:
        error_message = f"Error fetching file content: {e}"
        if '404' in str(e):
             error_message += " (This can happen with submodules or broken links)"
        return f"### File: {file_path}\n[{error_message}]\n\n"
    except Exception as e:
        return f"### File: {file_path}\n[Error processing file: {str(e)}]\n\n"

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
        owner, repo, default_branch, contents, is_hf = get_repo_contents(url)
        if isinstance(contents, str):
            return f"Error: {contents}"
        
        filtered_contents = [item for item in contents if not is_excluded(item['path'])]
        if not filtered_contents:
            return "Error: No non-excluded files found in the repository."

        markdown_content = [
            f"# {'Space' if is_hf else 'Repository'}: {owner}/{repo}\n",
            "## File Structure\n",
            generate_file_tree([item['path'] for item in filtered_contents]),
            f"Below are the contents of all files in the {'space' if is_hf else 'repository'}:\n\n"
        ]
        markdown_content.extend(process_file_content(item, owner, repo, default_branch, is_hf) for item in filtered_contents)
    else:
        filtered_files = [file for file in files if hasattr(file, 'filename') and not is_excluded(file.filename)]
        if not filtered_files:
            return "Error: No non-excluded files were uploaded."

        markdown_content = [
            "# Uploaded Files\n",
            "## File Structure\n",
            generate_file_tree([file.filename for file in filtered_files]),
            "Below are the contents of all uploaded files:\n\n"
        ]
        markdown_content.extend(process_uploaded_file(file) for file in filtered_files)
    
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
        elif in_code_block and not is_binary:
            current_content.append(line)

    if current_filename:
        content = "\n".join(current_content) if not is_binary else ""
        files.append({"filename": current_filename, "content": "[Binary File]" if is_binary else content, "is_binary": is_binary, "filepath": current_filename})
        buffers[current_filename] = b"[Binary content not stored]" if is_binary else content.encode('utf-8')

    if not files:
        return "Error: No files found in the markdown document.", {}
    return files, buffers
