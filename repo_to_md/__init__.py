from .core import create_markdown_document, generate_file_tree

__version__ = "0.1.0"
__all__ = ["create_markdown_document", "generate_file_tree"]

try:
    from .demo import run_demo  # Optional import for demo
    __all__.append("run_demo")
except ImportError:
    pass  # Demo not available if Flask/markdown not installed
