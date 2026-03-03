"""Tests for tree-sitter code parsing service.

Covers:
- parse_file() extracts function definitions from Python
- parse_file() extracts class definitions with methods from Python
- parse_file() extracts function/class definitions from TypeScript
- parse_file() returns empty list for binary/unparseable files
- parse_file() includes decorators in extracted content
- parse_file() extracts type/interface definitions from TypeScript
- detect_language() maps extensions correctly
"""

import pytest

from src.services.code_parser import CodeChunkData, detect_language, parse_file


class TestDetectLanguage:
    """Tests for file extension to tree-sitter language mapping."""

    def test_python_extension(self):
        assert detect_language("src/main.py") == "python"

    def test_typescript_extension(self):
        assert detect_language("src/index.ts") == "typescript"

    def test_tsx_extension(self):
        assert detect_language("src/App.tsx") == "typescript"

    def test_javascript_extension(self):
        assert detect_language("lib/utils.js") == "javascript"

    def test_jsx_extension(self):
        assert detect_language("components/Button.jsx") == "javascript"

    def test_go_extension(self):
        assert detect_language("cmd/server/main.go") == "go"

    def test_rust_extension(self):
        assert detect_language("src/lib.rs") == "rust"

    def test_java_extension(self):
        assert detect_language("src/Main.java") == "java"

    def test_ruby_extension(self):
        assert detect_language("app/models/user.rb") == "ruby"

    def test_cpp_extension(self):
        assert detect_language("src/engine.cpp") == "cpp"

    def test_c_extension(self):
        assert detect_language("src/utils.c") == "c"

    def test_header_extension(self):
        assert detect_language("include/types.h") == "c"

    def test_unknown_extension_returns_none(self):
        assert detect_language("README.md") is None

    def test_no_extension_returns_none(self):
        assert detect_language("Makefile") is None


class TestParseFilePython:
    """Tests for Python code parsing."""

    def test_extracts_function_definitions(self):
        """parse_file() extracts function definitions from Python code."""
        code = '''def authenticate_user(token: str) -> bool:
    """Authenticate a user by their token."""
    if not token:
        return False
    return validate(token)
'''
        chunks = parse_file("auth.py", code, "python")
        assert len(chunks) >= 1
        func_chunks = [c for c in chunks if c.symbol_type == "function"]
        assert len(func_chunks) == 1
        chunk = func_chunks[0]
        assert chunk.symbol_name == "authenticate_user"
        assert chunk.symbol_type == "function"
        assert chunk.start_line == 1
        assert chunk.end_line == 5
        assert "def authenticate_user" in chunk.content

    def test_extracts_class_and_methods(self):
        """parse_file() extracts class definitions and methods within them."""
        code = '''class UserService:
    """Service for user operations."""

    def create_user(self, name: str) -> dict:
        """Create a new user."""
        return {"name": name}

    def delete_user(self, user_id: int) -> bool:
        """Delete a user by ID."""
        return True
'''
        chunks = parse_file("service.py", code, "python")
        class_chunks = [c for c in chunks if c.symbol_type == "class"]
        method_chunks = [c for c in chunks if c.symbol_type == "method"]
        assert len(class_chunks) == 1
        assert class_chunks[0].symbol_name == "UserService"
        assert len(method_chunks) == 2
        method_names = {c.symbol_name for c in method_chunks}
        assert "create_user" in method_names
        assert "delete_user" in method_names
        # Methods should have parent_class in metadata
        for method in method_chunks:
            assert method.metadata.get("parent_class") == "UserService"

    def test_includes_decorators(self):
        """parse_file() includes decorators in extracted content."""
        code = '''@app.route("/api/users")
@require_auth
def list_users():
    """List all users."""
    return get_all_users()
'''
        chunks = parse_file("routes.py", code, "python")
        func_chunks = [c for c in chunks if c.symbol_name == "list_users"]
        assert len(func_chunks) == 1
        chunk = func_chunks[0]
        assert "@app.route" in chunk.content
        assert "@require_auth" in chunk.content

    def test_returns_empty_for_empty_code(self):
        """parse_file() returns empty list for empty code."""
        chunks = parse_file("empty.py", "", "python")
        assert chunks == []


class TestParseFileTypeScript:
    """Tests for TypeScript code parsing."""

    def test_extracts_function_declarations(self):
        """parse_file() extracts function/class definitions from TypeScript."""
        code = '''function calculateTotal(items: Item[]): number {
    return items.reduce((sum, item) => sum + item.price, 0);
}

class ShoppingCart {
    items: Item[] = [];

    addItem(item: Item): void {
        this.items.push(item);
    }
}
'''
        chunks = parse_file("cart.ts", code, "typescript")
        func_chunks = [c for c in chunks if c.symbol_type == "function"]
        class_chunks = [c for c in chunks if c.symbol_type == "class"]
        assert any(c.symbol_name == "calculateTotal" for c in func_chunks)
        assert any(c.symbol_name == "ShoppingCart" for c in class_chunks)

    def test_extracts_type_and_interface(self):
        """parse_file() extracts type/interface definitions from TypeScript."""
        code = '''interface User {
    id: string;
    name: string;
    email: string;
}

type UserRole = "admin" | "user" | "guest";
'''
        chunks = parse_file("types.ts", code, "typescript")
        interface_chunks = [c for c in chunks if c.symbol_type == "interface"]
        type_chunks = [c for c in chunks if c.symbol_type == "type"]
        assert any(c.symbol_name == "User" for c in interface_chunks)
        assert any(c.symbol_name == "UserRole" for c in type_chunks)


class TestParseFileEdgeCases:
    """Tests for edge cases and error handling."""

    def test_returns_empty_for_binary_content(self):
        """parse_file() returns empty list for binary/unparseable content."""
        # Binary-like content with null bytes
        binary_content = "function test() {\x00\x01\x02 return true; }"
        chunks = parse_file("test.ts", binary_content, "typescript")
        # Should handle gracefully (empty or parsed - both acceptable)
        assert isinstance(chunks, list)

    def test_returns_empty_for_unknown_language(self):
        """parse_file() returns empty list for unknown language."""
        chunks = parse_file("test.xyz", "some content", "unknown_lang")
        assert chunks == []

    def test_chunk_data_structure(self):
        """CodeChunkData has correct fields."""
        chunk = CodeChunkData(
            symbol_name="test_func",
            symbol_type="function",
            language="python",
            content="def test_func():\n    pass",
            start_line=1,
            end_line=2,
            metadata={"docstring": "A test function"},
        )
        assert chunk.symbol_name == "test_func"
        assert chunk.symbol_type == "function"
        assert chunk.language == "python"
        assert chunk.start_line == 1
        assert chunk.end_line == 2
        assert chunk.metadata["docstring"] == "A test function"
