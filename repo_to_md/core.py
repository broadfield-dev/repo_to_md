import requests
import base64
import json
import mimetypes
import os
from huggingface_hub import HfApi
from pathlib import Path
import re

GITHUB_API = "https://api.github.com/repos/"

def generate_file_tree(paths):
    """Generate a simple file tree from a list of paths."""
    tree = ["📁 Root"]
    sorted_paths = sorted(paths)
    for path in sorted_paths:
        parts = path.split('/')
        indent = "  " * (len(parts) - 1)
        tree.append(f"{indent}📄 {parts[-1]}")
    return "\n".join(tree) + "\n\n"

def get_all_files(owner, repo, path="", is_hf=False):
    """Recursively fetch all files from a repository."""
    if is_hf:
        api_url = f"https://huggingface.co/api/spaces/{owner}/{repo}/tree/main/{path}".rstrip('/')
    else:
        api_url = f"{GITHUB_API}{owner}/{repo}/contents/{path}".rstrip('/')
    
    try:
        response = requests.get(api_url, headers={"Accept": "application/json"}, timeout=10)
        response.raise_for_status()
        items = response.json() if response.headers.get('Content-Type', '').startswith('application/json') else None
        if not items:
            return None
        
        files = []
        for item in items:
            if item.get('type') == 'file':
                files.append(item)
            elif item.get('type') == 'dir':
                sub_files = get_all_files(owner, repo, item['path'], is_hf)
                if sub_files:
                    files.extend(sub_files)
        return files
    except requests.exceptions.RequestException:
        return None

def get_hf_files(owner, repo):
    """Fetch all files from a Hugging Face Space."""
    api = HfApi(token=os.getenv('HF_TOKEN'))
    try:
        file_list = api.list_repo_files(repo_id=f'{owner}/{repo}', repo_type="space")
        processed_files = []
        for file_path in file_list:
            raw_url = f"https://huggingface.co/spaces/{owner}/{repo}/raw/main/{file_path}"
            response = requests.get(raw_url, timeout=10)
            response.raise_for_status()
            if not response.headers.get('Content-Type', '').startswith(('text/plain', 'application/octet-stream', 'text/')):
                continue
            processed_files.append({"path": file_path})
        return processed_files
    except Exception:
        return []

def get_repo_contents(url):
    """Parse URL and fetch repository contents."""
    try:
        if "huggingface.co" in url.lower():
            parts = url.rstrip('/').split('/')
            owner, repo = parts[-2], parts[-1]
            files = get_hf_files(owner, repo)
            if not files:
                raise Exception("No files found in the Hugging Face Space")
            return owner, repo, files, True
        else:
            parts = url.rstrip('/').split('/')
            owner, repo = parts[-2], parts[-1]
            files = get_all_files(owner, repo, "", False)
            if files is None:
                raise Exception("Failed to fetch GitHub repository contents")
            return owner, repo, files, False
    except Exception as e:
        return None, None, f"Error fetching repo contents: {str(e)}", False

def process_file_content(file_info, owner, repo, is_hf=False):
    """Process individual file content from a repository."""
    content = ""
    file_path = file_info['path']
    
    try:
        if is_hf:
            file_url = f"https://huggingface.co/spaces/{owner}/{repo}/raw/main/{file_path}"
            response = requests.get(file_url, timeout=10)
            response.raise_for_status()
            content_raw = response.content
        else:
            file_url = f"{GITHUB_API}{owner}/{repo}/contents/{file_path}"
            response = requests.get(file_url, headers={"Accept": "application/json"}, timeout=10)
            response.raise_for_status()
            data = response.json()
            content_raw = base64.b64decode(data['content']) if 'content' in data else b""
        
        size = len(content_raw)
        file_extension = file_path.split('.')[-1] if '.' in file_path else ''
        mime_type, _ = mimetypes.guess_type(file_path)
        is_text = (mime_type and mime_type.startswith('text')) or file_extension in ['py', 'md', 'txt', 'js', 'html', 'css', 'json'] or "Dockerfile" in file_path
        
        if is_text:
            text_content = content_raw.decode('utf-8')
            if file_extension == 'json':
                try:
                    json_data = json.loads(text_content)
                    formatted_json = json.dumps(json_data, indent=2)
                    content = f"### File: {file_path}\n```json\n{formatted_json}\n```\n\n"
                except json.JSONDecodeError:
                    content = f"### File: {file_path}\n```json\n{text_content}\n```\n[Note: Invalid JSON format]\n\n"
            else:
                content = f"### File: {file_path}\n```{file_extension or 'text'}\n{text_content}\n```\n\n"
        else:
            content = f"### File: {file_path}\n[Binary file - {size} bytes]\n\n"
    except Exception as e:
        content = f"### File: {file_path}\n[Error fetching file content: {str(e)}]\n\n"
    
    return content

def process_uploaded_file(file):
    """Process uploaded file content (expects a file-like object with read() method)."""
    content = ""
    filename = getattr(file, 'filename', 'unknown')
    file_extension = filename.split('.')[-1] if '.' in filename else ''
    
    try:
        content_raw = file.read()
        size = len(content_raw)
        mime_type, _ = mimetypes.guess_type(filename)
        is_text = (mime_type and mime_type.startswith('text')) or file_extension in ['py', 'md', 'txt', 'js', 'html', 'css', 'json']
        
        if is_text:
            text_content = content_raw.decode('utf-8')
            if file_extension == 'json':
                try:
                    json_data = json.loads(text_content)
                    formatted_json = json.dumps(json_data, indent=2)
                    content = f"### File: {filename}\n```json\n{formatted_json}\n```\n\n"
                except json.JSONDecodeError:
                    content = f"### File: {filename}\n```json\n{text_content}\n```\n[Note: Invalid JSON format]\n\n"
            else:
                content = f"### File: {filename}\n```{file_extension or 'text'}\n{text_content}\n```\n\n"
        else:
            content = f"### File: {filename}\n[Binary file - {size} bytes]\n\n"
    except Exception as e:
        content = f"### File: {filename}\n[Error processing file: {str(e)}]\n\n"
    
    return content

def create_markdown_document(url=None, files=None):
    """Create markdown document from repo contents or uploaded files."""
    if url:
        owner, repo, contents, is_hf = get_repo_contents(url)
        if isinstance(contents, str):  # Error case
            return f"Error: {contents}"
        
        markdown_content = f"# {'Space' if is_hf else 'Repository'}: {owner}/{repo}\n\n"
        markdown_content += "## File Structure\n```\n"
        markdown_content += generate_file_tree([item['path'] for item in contents])
        markdown_content += "```\n\n"
        markdown_content += f"Below are the contents of all files in the {'space' if is_hf else 'repository'}:\n\n"
        
        for item in contents:
            markdown_content += process_file_content(item, owner, repo, is_hf)
    else:
        markdown_content = "# Uploaded Files\n\n"
        markdown_content += "## File Structure\n```\n"
        markdown_content += generate_file_tree([file.filename for file in files])
        markdown_content += "```\n\n"
        markdown_content += "Below are the contents of all uploaded files:\n\n"
        for file in files:
            markdown_content += process_uploaded_file(file)
    
    return markdown_content


def markdown_to_files(markdown_text):
    """
    Converts a markdown document back into individual files.
    Returns a tuple: (file_data, file_buffers)
    - file_data: List of dicts for display ({filename, content, is_binary, filepath})
    - file_buffers: Dict of filename -> bytes for download
    """
    files = []
    buffers = {}
    current_filename = None
    current_content = []
    is_binary = False
    in_code_block = False
    code_block_lang = None

    lines = markdown_text.splitlines()

    for line in lines:
        if line.startswith("### File: "):
            if current_filename:  # Save the previous file
                content = "\n".join(current_content) if not is_binary else ""
                file_path = current_filename
                files.append({
                    "filename": current_filename,
                    "content": "[Binary File]" if is_binary else content,
                    "is_binary": is_binary,
                    "filepath": file_path
                })
                buffers[file_path] = b"[Binary content not stored in Markdown]" if is_binary else content.encode('utf-8')
            current_filename = line[len("### File: "):].strip()
            current_content = []
            is_binary = False
            in_code_block = False
            code_block_lang = None
        elif line.startswith("[Binary file - ") and current_filename:
            is_binary = True
            current_content = []
        elif line.startswith("```"):
            if in_code_block:
                in_code_block = False
                code_block_lang = None
            else:
                in_code_block = True
                match = re.match(r"^```(\w+)?", line)
                code_block_lang = match.group(1) if match else None
        elif not in_code_block or is_binary:
            continue
        elif line != "```":
            current_content.append(line)

    if current_filename:  # Save the last file
        content = "\n".join(current_content) if not is_binary else ""
        file_path = current_filename
        files.append({
            "filename": current_filename,
            "content": "[Binary File]" if is_binary else content,
            "is_binary": is_binary,
            "filepath": file_path
        })
        buffers[file_path] = b"[Binary content not stored in Markdown]" if is_binary else content.encode('utf-8')

    if not files:
        return "Error: No files found in the markdown document.", {}
    return files, buffers
