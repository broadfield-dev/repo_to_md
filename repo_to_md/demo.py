from flask import Flask, render_template, request, jsonify, send_file, send_from_directory, g
from .core import create_markdown_document, markdown_to_files
import os
import io
import zipfile
import tempfile
import mimetypes
import shutil
import re
import sys
from pathlib import Path
from typing import Dict

app = Flask(__name__)
app.secret_key = os.urandom(24)
reverse_buffers = {}

def find_template_path() -> str:
    possible_paths = [
        Path(__file__).parent / "templates",
        Path(__file__).parent.parent / "templates",
        Path(sys.executable).parent / "site-packages/repo_to_md/templates"
    ]
    for path in possible_paths:
        if path.exists():
            return str(path)
    raise FileNotFoundError("Template directory not found")

def rebuild_html_content(html_content: bytes, buffers: Dict[str, bytes]) -> bytes:
    html_str = html_content.decode('utf-8', errors='replace')
    for pattern, tag in [
        (r'<script\s+src=["\']([^"\']+)["\'].*?</script>', "<script>\n{0}\n</script>"),
        (r'<link\s+[^>]*href=["\']([^"\']+)["\'][^>]*rel=["\']stylesheet["\'][^>]*>', "<style>\n{0}\n</style>")
    ]:
        for match in re.finditer(pattern, html_str, re.IGNORECASE):
            src = match.group(1)
            if src in buffers:
                html_str = html_str.replace(match.group(0), tag.format(buffers[src].decode('utf-8', errors='replace')))
    return html_str.encode('utf-8')

def extract_file_tree(markdown_text: str) -> str:
    tree_section = re.search(r'## File Structure\n```(.*?)```', markdown_text, re.DOTALL)
    if not tree_section:
        return "<pre>No file structure found.</pre>"
    return f"<div style='font-family: monospace; padding: 10px; background: #f4f4f4; border-radius: 5px;'>{tree_section.group(1)}</div>"

def extract_file_blocks(markdown_text: str) -> list:
    """Extract file names and contents from Markdown, ensuring binary files are isolated."""
    # Split the markdown into blocks starting with ### File:
    blocks = []
    pattern = r'### File: (.+?)(?:\s+\[Binary file - (\d+) bytes\])?\n(?:```(\w+)?\n(.*?)\n```|Binary content not shown|(?=### File:)|$)'
    matches = re.finditer(pattern, markdown_text, re.DOTALL)
    
    for match in matches:
        filename = match.group(1).strip()
        binary_size = match.group(2)  # Captures [Binary file - XXX bytes] if present
        language = match.group(3) or 'text'
        content = match.group(4) if match.group(4) else 'Binary content not shown'
        
        # Check if the filename contains "Binary file"
        is_binary = "Binary file" in filename or content == 'Binary content not shown'
        
        blocks.append({
            'filename': filename,
            'language': 'binary' if is_binary else language,
            'content': f"Binary content [File size: {binary_size or 'unknown'} bytes]" if is_binary else content.strip(),
            'is_binary': is_binary,
            'binary_size': binary_size
        })
    
    return blocks

def run_demo(host: str = "0.0.0.0", port: int = 7860, debug: bool = True) -> None:
    app.template_folder = find_template_path()
    app.static_folder = str(Path(app.template_folder).parent / "static")

    @app.before_request
    def setup_temp_dir():
        g.temp_dir = tempfile.mkdtemp()

    @app.teardown_appcontext
    def cleanup_temp_dir(_=None):
        if hasattr(g, 'temp_dir'):
            shutil.rmtree(g.temp_dir, ignore_errors=True)

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/process', methods=['POST'])
    def process():
        if 'files[]' in request.files:
            files = request.files.getlist('files[]')
            if not files:
                return jsonify({'error': 'No files uploaded'}), 400
            markdown_content = create_markdown_document(files=files)
            filename = "uploaded_files_summary.md"
        else:
            repo_url = request.json.get('repo_url', '').strip()
            if not repo_url:
                return jsonify({'error': 'Please provide a repository URL or upload files'}), 400
            markdown_content = create_markdown_document(repo_url)
            if markdown_content.startswith("Error:"):
                return jsonify({'error': markdown_content}), 400
            owner, repo = repo_url.rstrip('/').split('/')[-2:]
            filename = f"{owner}_{repo}_summary.md"
        file_blocks = extract_file_blocks(markdown_content)
        return jsonify({'markdown': markdown_content, 'filename': filename, 'files': file_blocks})

    @app.route('/download', methods=['POST'])
    def download():
        data = request.json
        buffer = io.BytesIO(data['markdown'].encode('utf-8'))
        return send_file(buffer, as_attachment=True, download_name=data.get('filename', 'document.md'), mimetype='text/markdown')

    @app.route('/reverse', methods=['POST'])
    def reverse():
        global reverse_buffers
        markdown_text = (
            request.files.get('markdown_file', {}).read().decode('utf-8', errors='replace') or
            request.form.get('markdown_text', '')
        )
        if not markdown_text.strip():
            return jsonify({'error': 'No Markdown data provided', 'files': [], 'combined_html': '<p>Please provide Markdown input.</p>'}), 400

        files, buffers = markdown_to_files(markdown_text)
        if isinstance(files, str):
            return jsonify({'error': files, 'files': [], 'combined_html': '<p>Invalid Markdown format.</p>'}), 400

        reverse_buffers.clear()
        reverse_buffers.update({k: v.encode('utf-8') if isinstance(v, str) else v for k, v in buffers.items()})
        combined_html = ""
        has_html = False

        for file_info in files:
            if not file_info['is_binary'] and file_info['filename'].endswith(".html"):
                has_html = True
                html_content = rebuild_html_content(reverse_buffers[file_info['filepath']], reverse_buffers)
                filepath = Path(g.temp_dir) / file_info['filepath']
                filepath.parent.mkdir(parents=True, exist_ok=True)
                filepath.write_bytes(html_content)
                combined_html += f"<iframe src='/temp/{file_info['filepath']}' style='width:100%; height:400px; border:1px solid #ddd;'></iframe>"

        if not has_html:
            tree_path = Path(g.temp_dir) / "file_tree.html"
            tree_html = f"<!DOCTYPE html><html><body>{extract_file_tree(markdown_text)}</body></html>"
            tree_path.write_text(tree_html, encoding='utf-8')
            combined_html = f"<iframe src='/temp/file_tree.html' style='width:100%; height:400px; border:1px solid #ddd;'></iframe>"

        return jsonify({'files': files, 'combined_html': combined_html, 'error': None})

    @app.route('/temp/<path:filename>')
    def temp_files(filename):
        return send_from_directory(g.temp_dir, filename)

    @app.route('/download_file', methods=['POST'])
    def download_file():
        filepath = request.json.get('filepath')
        if filepath not in reverse_buffers:
            return jsonify({'error': 'File not found'}), 404
        return send_file(
            io.BytesIO(reverse_buffers[filepath]),
            as_attachment=True,
            download_name=Path(filepath).name,
            mimetype=mimetypes.guess_type(filepath)[0] or 'application/octet-stream'
        )

    @app.route('/download_extracted', methods=['POST'])
    def download_extracted():
        if not reverse_buffers:
            return jsonify({'error': 'No files available'}), 400
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for filepath, content in reverse_buffers.items():
                zip_file.writestr(filepath, content if isinstance(content, bytes) else content.encode('utf-8'))
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name="extracted_files.zip", mimetype='application/zip')

    app.run(host=host, port=port, debug=debug)

if __name__ == "__main__":
    run_demo()
