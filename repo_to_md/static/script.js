let currentMarkdown = '';
let currentFilename = '';
let extractedFiles = [];

function openTab(evt, tabName) {
    const tabcontent = document.getElementsByClassName("tabcontent");
    for (let i = 0; i < tabcontent.length; i++) {
        tabcontent[i].style.display = "none";
    }
    const tablinks = document.getElementsByClassName("tablinks");
    for (let i = 0; i < tablinks.length; i++) {
        tablinks[i].className = tablinks[i].className.replace(" active", "");
    }
    document.getElementById(tabName).style.display = "block";
    evt.currentTarget.className += " active";

    if (tabName === 'markdownToFiles') {
        resetMarkdownToFilesTab();
    }
}

function resetMarkdownToFilesTab() {
    document.getElementById('markdownFileInput').value = '';
    document.getElementById('markdownPasteInput').value = '';
    document.getElementById('filesDisplay').innerHTML = '<p>Upload or paste Markdown to extract files.</p>';
    document.getElementById('combinedPreviewContent').innerHTML = '';
    document.getElementById('downloadExtractedBtn').classList.add('hidden');
    resetMode();
}

function toggleMode() {
    const body = document.body;
    const toggle = document.getElementById('modeToggle');
    body.classList.toggle('dark-mode', !toggle.checked);
    body.classList.toggle('light-mode', toggle.checked);
}

async function processRepo() {
    const repoUrl = document.getElementById('repoUrl').value;
    await processContent('/process', { repo_url: repoUrl });
}

async function processFiles() {
    const files = document.getElementById('fileInput').files;
    if (files.length === 0) {
        alert('Please select at least one file or folder');
        return;
    }
    const formData = new FormData();
    for (let file of files) {
        formData.append('files[]', file);
    }
    await processContent('/process', formData, false);
}

async function processContent(url, data, isJson = true) {
    const spinner = document.getElementById('spinner');
    const buttons = document.querySelectorAll('button');
    spinner.style.display = 'block';
    buttons.forEach(btn => btn.disabled = true);

    try {
        const options = {
            method: 'POST',
            ...(isJson ? {
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            } : { body: data })
        };
        const response = await fetch(url, options);
        const result = await response.json();

        if (result.error) {
            alert(result.error);
            return;
        }

        currentMarkdown = result.markdown;
        currentFilename = result.filename;
        document.getElementById('markdownOutput').value = result.markdown;

        // Render individual file blocks
        const output = document.getElementById('output');
        output.innerHTML = '';
        if (result.files && result.files.length > 0) {
            result.files.forEach(file => {
                const fileContainer = document.createElement('div');
                fileContainer.className = 'file-preview';

                const fileName = document.createElement('div');
                fileName.className = 'file-name';
                fileName.textContent = file.filename;
                fileContainer.appendChild(fileName);

                const codeBlock = document.createElement('pre');
                codeBlock.className = 'code-block hljs';
                const code = document.createElement('code');
                code.className = file.is_binary ? 'language-binary' : `language-${file.language}`;
                code.textContent = file.content;
                codeBlock.appendChild(code);
                fileContainer.appendChild(codeBlock);
                if (!file.is_binary) {
                    hljs.highlightElement(code);
                }

                output.appendChild(fileContainer);
            });
        } else {
            output.innerHTML = '<p>No files found in the Markdown.</p>';
        }

        document.getElementById('downloadBtn').style.display = 'inline-block';

        const markdownOutput = document.getElementById('markdownOutput');
        markdownOutput.classList.add('fade-in');
        output.classList.add('fade-in');
        setTimeout(() => {
            markdownOutput.classList.remove('fade-in');
            output.classList.remove('fade-in');
        }, 500);

        const markdownHeight = markdownOutput.scrollHeight;
        const outputHeight = output.scrollHeight;
        const maxHeight = Math.max(markdownHeight, outputHeight);
        markdownOutput.style.height = `${maxHeight}px`;
        output.style.maxHeight = `${maxHeight}px`;

        resetMode();
    } catch (error) {
        alert('An error occurred: ' + error.message);
    } finally {
        spinner.style.display = 'none';
        buttons.forEach(btn => btn.disabled = false);
    }
}

function resetMode() {
    const toggle = document.getElementById('modeToggle');
    document.body.classList.remove('light-mode', 'dark-mode');
    document.body.classList.add(toggle.checked ? 'light-mode' : 'dark-mode');
}

async function downloadMarkdown() {
    try {
        const response = await fetch('/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ markdown: currentMarkdown, filename: currentFilename })
        });
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = currentFilename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
    } catch (error) {
        alert('Error downloading file: ' + error.message);
    }
}

async function copyToClipboard() {
    const markdownOutput = document.getElementById('markdownOutput');
    if (!markdownOutput || !markdownOutput.value) {
        alert('Nothing to copy!');
        return;
    }
    try {
        await navigator.clipboard.writeText(markdownOutput.value);
        alert('Markdown copied to clipboard!');
    } catch (err) {
        console.error('Clipboard API failed:', err);
        markdownOutput.select();
        try {
            document.execCommand('copy');
            alert('Markdown copied to clipboard (legacy method)!');
        } catch (fallbackErr) {
            alert('Failed to copy to clipboard: ' + (err.message || 'Unknown error'));
        }
    }
}

async function reverseProcess() {
    let markdownText = '';
    const markdownFile = document.getElementById('markdownFileInput').files[0];
    const markdownPasteInput = document.getElementById('markdownPasteInput').value;

    if (markdownFile) {
        markdownText = await markdownFile.text();
    } else if (markdownPasteInput) {
        markdownText = markdownPasteInput;
    } else {
        alert('Please upload a Markdown file or paste Markdown text.');
        document.getElementById('filesDisplay').innerHTML = '<p>No Markdown provided.</p>';
        return;
    }

    const formData = new FormData();
    formData.append('markdown_file', new Blob([markdownText], { type: 'text/markdown' }));

    const reverseSpinner = document.getElementById('reverseSpinner');
    const buttons = document.querySelectorAll('button');
    reverseSpinner.style.display = 'block';
    buttons.forEach(btn => btn.disabled = true);

    try {
        const response = await fetch('/reverse', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errorData = await response.json();
            alert(errorData.error || 'An error occurred.');
            document.getElementById('filesDisplay').innerHTML = '<p>Error processing Markdown.</p>';
            return;
        }

        const result = await response.json();
        console.log('Reverse result:', result);
        if (result.error) {
            alert(result.error);
            document.getElementById('filesDisplay').innerHTML = `<p>${result.error}</p>`;
            return;
        }

        extractedFiles = result.files || [];
        displayExtractedFiles(extractedFiles);
        const combinedPreviewContent = document.getElementById('combinedPreviewContent');
        combinedPreviewContent.innerHTML = '';
        if (result.combined_html) {
            const iframeContainer = document.createElement('div');
            iframeContainer.innerHTML = result.combined_html;
            combinedPreviewContent.appendChild(iframeContainer);
        } else {
            combinedPreviewContent.innerHTML = '<p>No HTML preview available.</p>';
        }
        document.getElementById('downloadExtractedBtn').classList.toggle('hidden', !extractedFiles.length);
    } catch (error) {
        console.error('Reverse process error:', error);
        alert('An error occurred: ' + error.message);
        document.getElementById('filesDisplay').innerHTML = '<p>An error occurred while processing.</p>';
    } finally {
        reverseSpinner.style.display = 'none';
        buttons.forEach(btn => btn.disabled = false);
        resetMode();
    }
}

function displayExtractedFiles(files) {
    const filesDisplay = document.getElementById('filesDisplay');
    if (!filesDisplay) {
        console.error('filesDisplay element not found');
        return;
    }
    filesDisplay.innerHTML = '';

    if (!files || files.length === 0) {
        filesDisplay.innerHTML = '<p>No files extracted. Please provide valid Markdown input.</p>';
        return;
    }

    for (const file of files) {
        const fileContainer = document.createElement('div');
        fileContainer.className = 'file-container';

        const fileNameDiv = document.createElement('div');
        fileNameDiv.className = 'file-name';
        fileNameDiv.textContent = file.filename;
        fileContainer.appendChild(fileNameDiv);

        if (!file.is_binary) {
            const codeBlock = document.createElement('pre');
            codeBlock.className = 'code-block hljs';
            const code = document.createElement('code');
            const fileExtension = file.filename.split('.').pop().toLowerCase();
            code.className = `language-${fileExtension}`;
            code.textContent = file.content;
            codeBlock.appendChild(code);
            fileContainer.appendChild(codeBlock);
            hljs.highlightElement(code);
        } else {
            const codeBlock = document.createElement('pre');
            codeBlock.className = 'code-block hljs';
            const code = document.createElement('code');
            code.className = 'language-binary';
            code.textContent = 'Binary content (not displayable)';
            codeBlock.appendChild(code);
            fileContainer.appendChild(codeBlock);
        }

        const previewDownloadContainer = document.createElement('div');
        const downloadButton = document.createElement('button');
        downloadButton.className = 'download-button';
        downloadButton.textContent = 'Download';
        downloadButton.onclick = () => downloadSingleFile(file.filepath, file.filename);
        previewDownloadContainer.appendChild(downloadButton);
        fileContainer.appendChild(previewDownloadContainer);

        if (file.filename.endsWith(".html") && !file.is_binary) {
            const previewIframe = document.createElement("iframe");
            previewIframe.className = "preview-iframe";
            previewIframe.src = `/temp/${file.filepath}`;
            fileContainer.appendChild(previewIframe);
        }

        filesDisplay.appendChild(fileContainer);
    }
}

async function downloadSingleFile(filepath, filename) {
    try {
        const response = await fetch('/download_file', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filepath: filepath })
        });

        if (!response.ok) {
            const errorData = await response.json();
            alert(errorData.error || 'An error occurred during download.');
            return;
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
    } catch (error) {
        console.error('Download error:', error);
        alert('Error downloading file: ' + error.message);
    }
}

async function downloadExtractedFiles() {
    try {
        const response = await fetch('/download_extracted', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files: extractedFiles })
        });

        if (!response.ok) {
            const errorData = await response.json();
            alert(errorData.error || 'An error occurred during download.');
            return;
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = "extracted_files.zip";
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
    } catch (error) {
        alert('Error downloading files: ' + error.message);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    hljs.highlightAll();
    resetMarkdownToFilesTab();
    resetMode();
});
