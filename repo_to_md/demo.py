from flask import Flask, render_template, request, jsonify, send_file
from .core import create_markdown_document
import markdown
import os
import pkg_resources
import sys

def find_template_path():
    """Find the templates directory, either from installed package or source."""
    try:
        # Try to use pkg_resources for installed packages
        template_path = pkg_resources.resource_filename("repo_to_md", "templates")
    except Exception as e:
        # Fallback for running from source (development)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(current_dir, "../templates")
        template_path = os.path.abspath(template_path)

    # Check if the template path exists
    if not os.path.exists(template_path):
        # Try an alternative path within the package directory
        package_dir = os.path.dirname(os.path.abspath(__file__))
        alternative_path = os.path.join(package_dir, "templates")
        if os.path.exists(alternative_path):
            template_path = alternative_path
        else:
            # One last attempt: check if installed but in a different structure
            site_packages = os.path.join(os.path.dirname(sys.executable), "site-packages")
            installed_path = os.path.join(site_packages, "repo_to_md", "templates")
            if os.path.exists(installed_path):
                template_path = installed_path
            else:
                raise FileNotFoundError(
                    f"Template directory not found at: {template_path}, {alternative_path}, or {installed_path}"
                )

    return template_path

def run_demo(host="0.0.0.0", port=7860, debug=True):
    # Get the correct template path
    template_path = find_template_path()

    # Create Flask app with the resolved template folder
    app = Flask(__name__, template_folder=template_path)

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

    app.run(host=host, port=port, debug=debug)

if __name__ == '__main__':
    run_demo()
