"""Tree-sitter code parsing service.

Parses source files into structured code chunks (functions, classes, methods,
types, interfaces) using tree-sitter-language-pack. Supports Python, TypeScript,
JavaScript, Go, Rust, Java, Ruby, C, and C++ with language-specific extraction
logic and generic fallback for other languages.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from tree_sitter import Node
from tree_sitter_language_pack import get_parser

logger = logging.getLogger(__name__)

# File extension to tree-sitter language mapping.
# Covers all mainstream programming languages available in tree-sitter-language-pack.
EXTENSION_MAP: dict[str, str] = {
    # Python
    ".py": "python",
    # TypeScript / JavaScript
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "javascript",
    # Go
    ".go": "go",
    # Rust
    ".rs": "rust",
    # Java / JVM
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".scala": "scala",
    ".groovy": "groovy",
    ".gradle": "groovy",
    # C / C++
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hxx": "cpp",
    # C#
    ".cs": "csharp",
    # Swift / Objective-C
    ".swift": "swift",
    ".m": "objc",
    # Ruby
    ".rb": "ruby",
    # PHP
    ".php": "php",
    # Dart (Flutter)
    ".dart": "dart",
    # Haskell
    ".hs": "haskell",
    # Lua
    ".lua": "lua",
    # Shell
    ".sh": "bash",
    ".bash": "bash",
    # Zig
    ".zig": "zig",
    # Solidity
    ".sol": "solidity",
}

# Cache parsers to avoid re-initialization
_parser_cache: dict[str, object] = {}

# Minimum lines for a chunk to be considered non-trivial
MIN_CHUNK_LINES = 2

# Identifier node types used for name extraction fallback (Kotlin, Scala, etc.)
_IDENT_TYPES: frozenset[str] = frozenset({
    "identifier", "simple_identifier", "type_identifier", "constant",
})

# C++ keywords/constructs that don't exist in C — used to upgrade .h files
_CPP_INDICATORS = re.compile(
    r'\b(?:class|namespace|template|public:|private:|protected:|virtual|nullptr|constexpr|auto\s+\w+\s*=)\b'
)
# Strip C/C++ comments and string literals before running the heuristic,
# so that "class" in a comment doesn't trigger a false C++ upgrade.
_C_COMMENTS_AND_STRINGS = re.compile(
    r'//[^\n]*|/\*.*?\*/|"(?:[^"\\]|\\.)*"', re.DOTALL
)

# Target node types for the generic parser (shared across _parse_generic and _walk_generic)
_GENERIC_TARGET_TYPES: dict[str, str] = {
    # Functions
    "function_definition": "function",
    "function_declaration": "function",
    "function_item": "function",         # Rust
    "method_definition": "method",
    "method_declaration": "method",
    "method": "method",               # Ruby
    # Classes
    "class_definition": "class",
    "class_declaration": "class",
    "class": "class",                   # Ruby
    "class_specifier": "class",         # C/C++
    "impl_item": "class",               # Rust impl blocks
    # Structs
    "struct_item": "type",              # Rust
    "struct_specifier": "type",         # C/C++
    "struct_declaration": "type",
    # Interfaces / Protocols / Traits
    "interface_declaration": "interface",
    "protocol_declaration": "interface",  # Swift
    "trait_item": "interface",            # Rust
    "trait_definition": "interface",      # Scala
    # Enums
    "enum_item": "type",                # Rust
    "enum_declaration": "type",
    # Objects / Modules
    "object_definition": "class",        # Scala
    "object_declaration": "class",       # Kotlin
    # Type aliases
    "type_alias_declaration": "type",
    "type_item": "type",                # Rust
}

# Container node types to recurse into without emitting as chunks
_CONTAINER_TYPES: frozenset[str] = frozenset({
    "module", "namespace_definition", "namespace_declaration",
    "mod_item", "program", "translation_unit",
})

# Body/block wrapper types to recurse into
_BODY_TYPES: frozenset[str] = frozenset({
    "body", "class_body", "block", "declaration_list",
    "body_statement",                    # Ruby
    "field_declaration_list",            # C/C++ class/struct body
})


@dataclass
class CodeChunkData:
    """Parsed code chunk data extracted by tree-sitter."""

    symbol_name: str
    symbol_type: str  # function, class, method, type, interface, decorator, module
    language: str
    content: str
    start_line: int  # 1-indexed
    end_line: int  # 1-indexed
    metadata: dict = field(default_factory=dict)


def detect_language(file_path: str) -> str | None:
    """Map a file path's extension to a tree-sitter language name.

    Args:
        file_path: Path to the source file.

    Returns:
        Tree-sitter language name, or None if extension is unknown.
    """
    suffix = Path(file_path).suffix.lower()
    return EXTENSION_MAP.get(suffix)


def _get_cached_parser(language: str):
    """Get or create a cached tree-sitter parser for the given language.

    Args:
        language: Tree-sitter language name (e.g., "python", "typescript").

    Returns:
        A tree-sitter Parser configured for the language, or None on failure.
    """
    if language in _parser_cache:
        return _parser_cache[language]

    try:
        parser = get_parser(language)
        _parser_cache[language] = parser
        return parser
    except Exception:
        logger.warning("Failed to create parser for language: %s", language)
        return None


def _node_text(node: Node, source_bytes: bytes) -> str:
    """Extract the text content of a tree-sitter node."""
    return source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _get_node_name(node: Node) -> str | None:
    """Extract the name identifier from a tree-sitter node.

    Tries the 'name' field first (most grammars), then falls back to
    finding the first identifier-like child node (Kotlin, Scala, etc.).
    """
    name_node = node.child_by_field_name("name")
    if name_node:
        return name_node.text.decode("utf-8", errors="replace")
    # Fallback: find first identifier child (covers Kotlin simple_identifier,
    # type_identifier for classes, etc.)
    for child in node.children:
        if child.type in _IDENT_TYPES:
            return child.text.decode("utf-8", errors="replace")
    return None


def _extract_python_docstring(node: Node, source_bytes: bytes) -> str | None:
    """Extract docstring from a Python function or class definition node."""
    body_node = node.child_by_field_name("body")
    if body_node is None:
        return None

    for child in body_node.children:
        if child.type == "expression_statement":
            for sub in child.children:
                if sub.type == "string":
                    text = _node_text(sub, source_bytes)
                    # Strip triple-quote delimiters
                    for delim in ('"""', "'''"):
                        if text.startswith(delim) and text.endswith(delim):
                            return text[3:-3].strip()
                    return text.strip("'\"").strip()
            break  # Only first statement can be a docstring
        elif child.type != "comment":
            break  # Not a docstring if first non-comment isn't a string
    return None


def _extract_decorators(node: Node, source_bytes: bytes) -> list[str]:
    """Extract decorator names from a decorated_definition node."""
    decorators = []
    for child in node.children:
        if child.type == "decorator":
            dec_text = _node_text(child, source_bytes).strip()
            # Extract just the decorator name (e.g., "@app.route" from "@app.route(\"/path\")")
            decorators.append(dec_text)
    return decorators


def _parse_python(root: Node, source_bytes: bytes, language: str) -> list[CodeChunkData]:
    """Extract code chunks from a Python AST."""
    chunks: list[CodeChunkData] = []

    for node in root.children:
        if node.type == "decorated_definition":
            # Decorated function or class
            decorators = _extract_decorators(node, source_bytes)
            inner = None
            for child in node.children:
                if child.type in ("function_definition", "class_definition"):
                    inner = child
                    break
            if inner is None:
                continue

            name = _get_node_name(inner)
            if name is None:
                continue

            content = _node_text(node, source_bytes)
            start_line = node.start_point.row + 1
            end_line = node.end_point.row + 1

            if end_line - start_line + 1 < MIN_CHUNK_LINES:
                continue

            symbol_type = "function" if inner.type == "function_definition" else "class"
            docstring = _extract_python_docstring(inner, source_bytes)

            metadata: dict = {}
            if docstring:
                metadata["docstring"] = docstring
            if decorators:
                metadata["decorators"] = decorators

            chunks.append(CodeChunkData(
                symbol_name=name,
                symbol_type=symbol_type,
                language=language,
                content=content,
                start_line=start_line,
                end_line=end_line,
                metadata=metadata,
            ))

            # If it's a class, also extract methods
            if inner.type == "class_definition":
                chunks.extend(_extract_python_methods(inner, source_bytes, language, name))

        elif node.type == "function_definition":
            name = _get_node_name(node)
            if name is None:
                continue

            content = _node_text(node, source_bytes)
            start_line = node.start_point.row + 1
            end_line = node.end_point.row + 1

            if end_line - start_line + 1 < MIN_CHUNK_LINES:
                continue

            docstring = _extract_python_docstring(node, source_bytes)
            metadata = {}
            if docstring:
                metadata["docstring"] = docstring

            chunks.append(CodeChunkData(
                symbol_name=name,
                symbol_type="function",
                language=language,
                content=content,
                start_line=start_line,
                end_line=end_line,
                metadata=metadata,
            ))

        elif node.type == "class_definition":
            name = _get_node_name(node)
            if name is None:
                continue

            content = _node_text(node, source_bytes)
            start_line = node.start_point.row + 1
            end_line = node.end_point.row + 1

            if end_line - start_line + 1 < MIN_CHUNK_LINES:
                continue

            docstring = _extract_python_docstring(node, source_bytes)
            metadata = {}
            if docstring:
                metadata["docstring"] = docstring

            chunks.append(CodeChunkData(
                symbol_name=name,
                symbol_type="class",
                language=language,
                content=content,
                start_line=start_line,
                end_line=end_line,
                metadata=metadata,
            ))

            # Extract methods from the class
            chunks.extend(_extract_python_methods(node, source_bytes, language, name))

    return chunks


def _extract_python_methods(
    class_node: Node, source_bytes: bytes, language: str, class_name: str
) -> list[CodeChunkData]:
    """Extract method definitions from a Python class body."""
    methods: list[CodeChunkData] = []
    body_node = class_node.child_by_field_name("body")
    if body_node is None:
        return methods

    for child in body_node.children:
        target_node = child
        decorators: list[str] = []

        if child.type == "decorated_definition":
            decorators = _extract_decorators(child, source_bytes)
            for sub in child.children:
                if sub.type == "function_definition":
                    target_node = sub
                    break
            else:
                continue

        if target_node.type == "function_definition":
            name = _get_node_name(target_node)
            if name is None:
                continue

            # Use the decorated_definition node for content if decorators exist
            content_node = child if child.type == "decorated_definition" else target_node
            content = _node_text(content_node, source_bytes)
            start_line = content_node.start_point.row + 1
            end_line = content_node.end_point.row + 1

            if end_line - start_line + 1 < MIN_CHUNK_LINES:
                continue

            docstring = _extract_python_docstring(target_node, source_bytes)
            metadata: dict = {"parent_class": class_name}
            if docstring:
                metadata["docstring"] = docstring
            if decorators:
                metadata["decorators"] = decorators

            methods.append(CodeChunkData(
                symbol_name=name,
                symbol_type="method",
                language=language,
                content=content,
                start_line=start_line,
                end_line=end_line,
                metadata=metadata,
            ))

    return methods


def _parse_typescript(root: Node, source_bytes: bytes, language: str) -> list[CodeChunkData]:
    """Extract code chunks from a TypeScript/JavaScript AST."""
    chunks: list[CodeChunkData] = []

    for node in root.children:
        if node.type == "function_declaration":
            name = _get_node_name(node)
            if name is None:
                continue
            content = _node_text(node, source_bytes)
            start_line = node.start_point.row + 1
            end_line = node.end_point.row + 1
            if end_line - start_line + 1 < MIN_CHUNK_LINES:
                continue
            chunks.append(CodeChunkData(
                symbol_name=name,
                symbol_type="function",
                language=language,
                content=content,
                start_line=start_line,
                end_line=end_line,
            ))

        elif node.type == "class_declaration":
            name = _get_node_name(node)
            if name is None:
                continue
            content = _node_text(node, source_bytes)
            start_line = node.start_point.row + 1
            end_line = node.end_point.row + 1
            if end_line - start_line + 1 < MIN_CHUNK_LINES:
                continue
            chunks.append(CodeChunkData(
                symbol_name=name,
                symbol_type="class",
                language=language,
                content=content,
                start_line=start_line,
                end_line=end_line,
            ))
            # Extract methods from TS/JS class
            chunks.extend(_extract_ts_methods(node, source_bytes, language, name))

        elif node.type == "interface_declaration":
            name = _get_node_name(node)
            if name is None:
                continue
            content = _node_text(node, source_bytes)
            start_line = node.start_point.row + 1
            end_line = node.end_point.row + 1
            if end_line - start_line + 1 < MIN_CHUNK_LINES:
                continue
            chunks.append(CodeChunkData(
                symbol_name=name,
                symbol_type="interface",
                language=language,
                content=content,
                start_line=start_line,
                end_line=end_line,
            ))

        elif node.type == "type_alias_declaration":
            name = _get_node_name(node)
            if name is None:
                continue
            content = _node_text(node, source_bytes)
            start_line = node.start_point.row + 1
            end_line = node.end_point.row + 1
            # Type aliases can be single-line -- allow them
            chunks.append(CodeChunkData(
                symbol_name=name,
                symbol_type="type",
                language=language,
                content=content,
                start_line=start_line,
                end_line=end_line,
            ))

        elif node.type in ("lexical_declaration", "variable_declaration"):
            # Named arrow functions: const foo = () => { ... }
            for declarator in node.children:
                if declarator.type == "variable_declarator":
                    name_n = declarator.child_by_field_name("name")
                    value_n = declarator.child_by_field_name("value")
                    if name_n and value_n and value_n.type == "arrow_function":
                        name = name_n.text.decode("utf-8", errors="replace")
                        content = _node_text(node, source_bytes)
                        start_line = node.start_point.row + 1
                        end_line = node.end_point.row + 1
                        if end_line - start_line + 1 < MIN_CHUNK_LINES:
                            continue
                        chunks.append(CodeChunkData(
                            symbol_name=name,
                            symbol_type="function",
                            language=language,
                            content=content,
                            start_line=start_line,
                            end_line=end_line,
                        ))

        elif node.type == "export_statement":
            # Handle exported declarations (export function, export class, etc.)
            for child in node.children:
                if child.type in (
                    "function_declaration",
                    "class_declaration",
                    "interface_declaration",
                    "type_alias_declaration",
                ):
                    # Recurse with the inner declaration but use the export node for content
                    name = _get_node_name(child)
                    if name is None:
                        continue
                    content = _node_text(node, source_bytes)
                    start_line = node.start_point.row + 1
                    end_line = node.end_point.row + 1

                    symbol_type_map = {
                        "function_declaration": "function",
                        "class_declaration": "class",
                        "interface_declaration": "interface",
                        "type_alias_declaration": "type",
                    }
                    symbol_type = symbol_type_map[child.type]

                    if symbol_type != "type" and end_line - start_line + 1 < MIN_CHUNK_LINES:
                        continue

                    chunks.append(CodeChunkData(
                        symbol_name=name,
                        symbol_type=symbol_type,
                        language=language,
                        content=content,
                        start_line=start_line,
                        end_line=end_line,
                    ))

                    if child.type == "class_declaration":
                        chunks.extend(
                            _extract_ts_methods(child, source_bytes, language, name)
                        )

    return chunks


def _extract_ts_methods(
    class_node: Node, source_bytes: bytes, language: str, class_name: str
) -> list[CodeChunkData]:
    """Extract method definitions from a TypeScript/JavaScript class body."""
    methods: list[CodeChunkData] = []
    body_node = class_node.child_by_field_name("body")
    if body_node is None:
        return methods

    for child in body_node.children:
        if child.type == "method_definition":
            name = _get_node_name(child)
            if name is None:
                continue
            content = _node_text(child, source_bytes)
            start_line = child.start_point.row + 1
            end_line = child.end_point.row + 1
            if end_line - start_line + 1 < MIN_CHUNK_LINES:
                continue
            methods.append(CodeChunkData(
                symbol_name=name,
                symbol_type="method",
                language=language,
                content=content,
                start_line=start_line,
                end_line=end_line,
                metadata={"parent_class": class_name},
            ))

    return methods


def _parse_go(root: Node, source_bytes: bytes, language: str) -> list[CodeChunkData]:
    """Extract code chunks from a Go AST."""
    chunks: list[CodeChunkData] = []

    for node in root.children:
        if node.type == "function_declaration":
            name = _get_node_name(node)
            if name is None:
                continue
            content = _node_text(node, source_bytes)
            start_line = node.start_point.row + 1
            end_line = node.end_point.row + 1
            if end_line - start_line + 1 < MIN_CHUNK_LINES:
                continue
            chunks.append(CodeChunkData(
                symbol_name=name,
                symbol_type="function",
                language=language,
                content=content,
                start_line=start_line,
                end_line=end_line,
            ))

        elif node.type == "method_declaration":
            name = _get_node_name(node)
            if name is None:
                continue
            content = _node_text(node, source_bytes)
            start_line = node.start_point.row + 1
            end_line = node.end_point.row + 1
            if end_line - start_line + 1 < MIN_CHUNK_LINES:
                continue
            # Try to extract receiver type as parent
            receiver = node.child_by_field_name("receiver")
            metadata: dict = {}
            if receiver:
                metadata["receiver"] = _node_text(receiver, source_bytes)
            chunks.append(CodeChunkData(
                symbol_name=name,
                symbol_type="method",
                language=language,
                content=content,
                start_line=start_line,
                end_line=end_line,
                metadata=metadata,
            ))

        elif node.type == "type_declaration":
            # Go type declarations (struct, interface)
            for spec in node.children:
                if spec.type == "type_spec":
                    name = _get_node_name(spec)
                    if name is None:
                        continue
                    content = _node_text(node, source_bytes)
                    start_line = node.start_point.row + 1
                    end_line = node.end_point.row + 1
                    # Determine if it's a struct or interface
                    type_node = spec.child_by_field_name("type")
                    symbol_type = "type"
                    if type_node and type_node.type == "interface_type":
                        symbol_type = "interface"
                    chunks.append(CodeChunkData(
                        symbol_name=name,
                        symbol_type=symbol_type,
                        language=language,
                        content=content,
                        start_line=start_line,
                        end_line=end_line,
                    ))

    return chunks


def _parse_generic(root: Node, source_bytes: bytes, language: str) -> list[CodeChunkData]:
    """Generic fallback parser for languages without specific extraction logic.

    Recursively walks the AST to extract functions, classes, structs,
    interfaces, protocols, enums, traits, and methods nested inside classes.
    """
    chunks: list[CodeChunkData] = []
    _walk_generic(root, source_bytes, language, chunks, parent_class=None)
    return chunks


def _walk_generic(
    node: Node,
    source_bytes: bytes,
    language: str,
    chunks: list[CodeChunkData],
    parent_class: str | None,
) -> None:
    """Recursively walk the AST collecting code chunks.

    Recurses into container types (modules, namespaces) and class-like
    nodes (to extract methods with parent_class metadata).
    """
    for child in node.children:
        if child.type in _GENERIC_TARGET_TYPES:
            name = _get_node_name(child)
            if name is None:
                continue
            base_type = _GENERIC_TARGET_TYPES[child.type]
            if parent_class and base_type in ("function", "method"):
                symbol_type = "method"
                metadata: dict = {"parent_class": parent_class}
            else:
                symbol_type = base_type
                metadata = {}
            content = _node_text(child, source_bytes)
            start_line = child.start_point.row + 1
            end_line = child.end_point.row + 1
            if end_line - start_line + 1 < MIN_CHUNK_LINES:
                continue
            chunks.append(CodeChunkData(
                symbol_name=name,
                symbol_type=symbol_type,
                language=language,
                content=content,
                start_line=start_line,
                end_line=end_line,
                metadata=metadata if metadata else {},
            ))
            # Recurse into class-like nodes for methods
            if symbol_type in ("class", "interface", "type") and child.type not in (
                "type_item", "type_alias_declaration",
            ):
                _walk_generic(child, source_bytes, language, chunks, parent_class=name)
        elif child.type in _CONTAINER_TYPES:
            _walk_generic(child, source_bytes, language, chunks, parent_class=parent_class)
        elif child.type in _BODY_TYPES:
            _walk_generic(child, source_bytes, language, chunks, parent_class=parent_class)


# Language family to parser function mapping
_LANGUAGE_PARSERS = {
    "python": _parse_python,
    "typescript": _parse_typescript,
    "tsx": _parse_typescript,          # Same AST structure
    "javascript": _parse_typescript,   # Same AST structure
    "go": _parse_go,
}


def parse_file(file_path: str, content: str, language: str) -> list[CodeChunkData]:
    """Parse a source file into structured code chunks using tree-sitter.

    Args:
        file_path: Path to the source file (for logging).
        content: The raw text content of the file.
        language: Tree-sitter language name.

    Returns:
        List of CodeChunkData extracted from the file.
        Returns empty list on parse failure or for unknown languages.
    """
    if not content or not content.strip():
        return []

    # Upgrade .h files to C++ if content contains C++ constructs.
    # Strip comments and strings first to avoid false positives like
    # /* Base class for widgets */ triggering the "class" keyword match.
    if language == "c":
        stripped = _C_COMMENTS_AND_STRINGS.sub("", content)
        if _CPP_INDICATORS.search(stripped):
            language = "cpp"

    parser = _get_cached_parser(language)
    if parser is None:
        return []

    try:
        source_bytes = content.encode("utf-8")
        tree = parser.parse(source_bytes)
        root = tree.root_node

        parse_fn = _LANGUAGE_PARSERS.get(language, _parse_generic)
        chunks = parse_fn(root, source_bytes, language)

        logger.debug(
            "Parsed %s: %d chunks extracted (language=%s)",
            file_path, len(chunks), language,
        )
        return chunks

    except Exception:
        logger.warning("Failed to parse %s (language=%s)", file_path, language, exc_info=True)
        return []
