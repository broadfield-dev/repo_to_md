import requests
import base64
import json
import mimetypes
import os
from huggingface_hub import HfApi
from pathlib import Path

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
        response = requests.get(api_url, headers={"Accept": "application/json"},
