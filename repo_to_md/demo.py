from flask import Flask, render_template, request, jsonify, send_file, send_from_directory, g, session
from repo_to_md.core import create_markdown_document, markdown_to_files
import markdown
import os
import pkg_resources
import sys
import io
import zipfile
import tempfile
import mimetypes
from pathlib import Path
import shutil
import re

app = Flask(__name__)
app.secret_key = os.urandom(24)
reverse_buffers = {}

def find_template_path():
    try:
        template_path = pkg_resources.resource_filename("repo_to_md", "templates")
    except Exception:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(current_dir, "../templates")
        template_path = os.path.abspath(template_path)

    if not os.path.exists(template_path):
        package_dir = os.path.dirname(os.path.abspath(__file__))
        alternative_path = os.path.join(package_dir, "templates")
        if os.path.exists(alternative_path):
            template_path = alternative_path
        else:
            site_packages = os.path.join(os.path.dirname(sys.executable), "site-packages")
            installed_path = os.path.join(site_packages, "repo_to_md", "templates")
            if os.path.exists(installed_path):
                template_path = installed_path
            else:
                raise FileNotFoundError(
                    f"Template directory not found at: {template_path}, {alternative_path}, or {installed_path}"
                )
    return template_path

def rebuild_html_content(html_content, buffers):
    """Rebuild HTML by inlining script and CSS references."""
    html_content = html_content.decode('utf-8') if isinstance(html_content, bytes) else html_content

    script_pattern = r'<script\s+src=["\']([^"\']+)["\'].*?</script>'
    for match in re.finditer(script_pattern, html_content, re.IGNORECASE):
        src = match.group(1)
        if src in buffers:
            script_content = buffers[src].decode('utf-8', errors='ignore')
            replacement = f"<script>\n{script_content}\n</script>"
            html_content = html_content.replace(match.group(0), replacement)

    css_pattern = r'<link\s+[^>]*href=["\']([^"\']+)["\'][^>]*rel=["\']stylesheet["\'][^>]*>'
    for match in re.finditer(css_pattern, html_content, re.IGNORECASE):
        href = match.group(1)
        if href in buffers:
            css_content = buffers[href].decode('utf-8', errors='ignore')
            replacement = f"<style>\n{css_content}\n</style>"
            html_content = html_content.replace(match.group(0), replacement)

    return html_content.encode('utf-8')

def extract_file_tree(markdown_text):
    """Extract the file tree section from Markdown and return it as HTML."""
    tree_start = markdown_text.find("## File Structure")
    if tree_start == -1:
        return "<pre>No file structure found.</pre>"
    
    tree_end = markdown_text.find("Below are the contents", tree_start)
    if tree_end == -1:
        tree_end = len(markdown_text)
    
    tree_section = markdown_text[tree_start:tree_end].strip()
    # Convert the tree section to HTML with minimal styling
    tree_html = markdown.markdown(tree_section)
    return f"""
    <div style='font-family: monospace; padding: 10px; background: #f4f4f4; border-radius: 5px;'>
        {tree_html}
    </div>
    """

def run_demo(host="0.0.0.0", port=7860, debug=True):
    template_path = find_template_path()
    app.template_folder = template_path

    @app.before_request
    def before_request():
        g.temp_dir = tempfile.mkdtemp()
        print(f"Created temp dir: {g.temp_dir}")

    @app.teardown_appcontext
    def teardown_appcontext(exception=None):
        if hasattr(g, 'temp_dir'):
            try:
                shutil.rmtree(g.temp_dir)
                print(f"Removed temp dir: {g.temp_dir}")
            except Exception as e:
                print(f"Error removing temp dir: {g.temp_dir}: {e}")

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/process', methods=['POST'])
    def process():
        response_data = {'markdown': '', 'html': '', 'filename': '', 'error': None}
        try:
            if 'files[]' in request.files:
                files = request.files.getlist('files[]')
                if not files:
                    response_data['error'] = 'No files uploaded'
                    return jsonify(response_data), 400
                markdown_content = create_markdown_document(files=files)
                response_data['markdown'] = markdown_content
                response_data['html'] = markdown.markdown(markdown_content)
                response_data['filename'] = "uploaded_files_summary.md"
            else:
                repo_url = request.json.get('repo_url', '').strip()
                if not repo_url:
                    response_data['error'] = 'Please provide a repository URL or upload files'
                    return jsonify(response_data), 400
                markdown_content = create_markdown_document(repo_url)
                if markdown_content.startswith("Error:"):
                    response_data['error'] = markdown_content
                    return jsonify(response_data), 400
                response_data['markdown'] = markdown_content
                response_data['html'] = markdown.markdown(markdown_content)
                owner, repo = repo_url.rstrip('/').split('/')[-2:]
                response_data['filename'] = f"{owner}_{repo}_summary.md"
        except Exception as e:
            response_data['error'] = f"Server error processing request: {str(e)}"
            return jsonify(response_data), 500
        return jsonify(response_data)

    @app.route('/download', methods=['POST'])
    def download():
        markdown_content = request.json.get('markdown', '')
        filename = request.json.get('filename', 'document.md')
        buffer = io.BytesIO()
        buffer.write(markdown_content.encode('utf-8'))
        buffer.seek(0)
        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='text/markdown'
        )

    @app.route('/reverse', methods=['POST'])
    def reverse():
        global reverse_buffers
        try:
            markdown_file = request.files.get('markdown_file')
            if not markdown_file:
                markdown_text = request.form.get('markdown_text', '')
            else:
                markdown_text = markdown_file.read().decode('utf-8')

            if not markdown_text:
                return jsonify({'error': 'No Markdown data provided'}), 400

            files, buffers = markdown_to_files(markdown_text)
            if isinstance(files, str) and files.startswith("Error:"):
                return jsonify({'error': files}), 400

            reverse_buffers.clear()
            reverse_buffers.update(buffers)
            print(f"Stored buffers: {list(reverse_buffers.keys())}")

            combined_html = ""
            has_html = False
            for file_info in files:
                if not file_info['is_binary'] and file_info['filename'].endswith(".html"):
                    has_html = True
                    html_content = rebuild_html_content(buffers[file_info['filepath']], buffers)
                    filepath = os.path.join(g.temp_dir, file_info['filepath'])
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    with open(filepath, 'wb') as f:
                        f.write(html_content)
                    combined_html += f"<iframe src='/temp/{file_info['filepath']}' style='width:100%; height:400px; border:1px solid #ddd;'></iframe>"

            if not has_html:
                # Write file tree to a temp file and serve it in an iframe
                tree_html = extract_file_tree(markdown_text)
                tree_path = os.path.join(g.temp_dir, "file_tree.html")
                with open(tree_path, 'w', encoding='utf-8') as f:
                    f.write(f"""
<!DOCTYPE html>
<html>
<head>
    <title>File Tree</title>
</head>
<body>
    {tree_html}
</body>
</html>
                    """)
                combined_html = f"<iframe src='/temp/file_tree.html' style='width:100%; height:400px; border:1px solid #ddd;'></iframe>"

            return jsonify({'files': files, 'combined_html': combined_html, 'error': None}), 200
        except Exception as e:
            return jsonify({'error': f"Server error: {str(e)}"}), 500

    @app.route('/temp/<path:filename>')
    def temp_files(filename):
        return send_from_directory(g.temp_dir, filename)

    @app.route('/download_file', methods=['POST'])
    def download_file():
        global reverse_buffers
        filepath = request.json.get('filepath')
        print(f"Attempting to download: {filepath}, Available buffers: {list(reverse_buffers.keys())}")
        if not filepath or filepath not in reverse_buffers:
            return jsonify({'error': 'File not found in buffer'}), 404

        try:
            filename = os.path.basename(filepath)
            buffer = io.BytesIO(reverse_buffers[filepath])
            buffer.seek(0)
            return send_file(
                buffer,
                as_attachment=True,
                download_name=filename,
                mimetype=mimetypes.guess_type(filename)[0] or 'application/octet-stream'
            )
        except Exception as e:
            return jsonify({'error': f"Server error: {str(e)}"}), 500

    @app.route('/download_extracted', methods=['POST'])
    def download_extracted():
        global reverse_buffers
        print(f"Creating zip with buffers: {list(reverse_buffers.keys())}")
        try:
            if not reverse_buffers:
                return jsonify({'error': 'No files available to zip'}), 400
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for filepath, content in reverse_buffers.items():
                    zip_file.writestr(filepath, content)
            zip_buffer.seek(0)
            return send_file(
                zip_buffer,
                as_attachment=True,
                download_name="extracted_files.zip",
                mimetype='application/zip'
            )
        except Exception as e:
            return jsonify({'error': f"Server error: {str(e)}"}), 500

    app.run(host=host, port=port, debug=debug)

if __name__ == '__main__':
    run_demo()
