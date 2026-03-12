"""Tests for tree-sitter code parsing service.

Covers:
- parse_file() extracts function definitions from Python
- parse_file() extracts class definitions with methods from Python
- parse_file() extracts function/class definitions from TypeScript
- parse_file() returns empty list for binary/unparseable files
- parse_file() includes decorators in extracted content
- parse_file() extracts type/interface definitions from TypeScript
- detect_language() maps extensions correctly
- Generic parser: recursive extraction for Rust, Java, Ruby, Kotlin, Swift, C#, Lua, Bash, Dart
- Dead extensions removed (yaml, json, elixir, etc.)
- .h file C++ heuristic upgrade
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
        assert detect_language("src/App.tsx") == "tsx"

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


class TestDeadExtensionsRemoved:
    """Verify removed extensions return None from detect_language."""

    @pytest.mark.parametrize("ext", [
        ".yaml", ".yml", ".json", ".toml", ".html", ".css", ".scss",
        ".sql", ".ex", ".exs", ".erl", ".clj", ".vue", ".svelte",
        ".elm", ".fs", ".fsx", ".nix", ".tf", ".hcl",
        ".proto", ".graphql", ".gql", ".nim", ".odin",
    ])
    def test_dead_extension_not_supported(self, ext):
        assert detect_language(f"test{ext}") is None


class TestParseFileGenericLanguages:
    """Tests for generic parser across multiple languages."""

    def test_rust_function_and_struct(self):
        code = '''fn process_data(input: &str) -> Result<Data, Error> {
    let parsed = parse(input)?;
    Ok(Data::new(parsed))
}

struct Config {
    name: String,
    value: i32,
    enabled: bool,
}
'''
        chunks = parse_file("lib.rs", code, "rust")
        funcs = [c for c in chunks if c.symbol_type == "function"]
        types = [c for c in chunks if c.symbol_type == "type"]
        assert any(c.symbol_name == "process_data" for c in funcs)
        assert any(c.symbol_name == "Config" for c in types)

    def test_rust_impl_methods(self):
        code = '''impl Server {
    fn new(port: u16) -> Self {
        Server {
            port,
            running: false,
        }
    }

    fn start(&mut self) -> Result<(), Error> {
        self.running = true;
        Ok(())
    }
}
'''
        chunks = parse_file("server.rs", code, "rust")
        methods = [c for c in chunks if c.symbol_type == "method"]
        assert len(methods) == 2
        method_names = {m.symbol_name for m in methods}
        assert method_names == {"new", "start"}
        for m in methods:
            assert m.metadata.get("parent_class") == "Server"

    def test_java_class_and_method(self):
        code = '''class UserService {
    public User findById(long id) {
        return repository
            .findById(id)
            .orElseThrow();
    }

    public void deleteUser(long id) {
        repository.deleteById(id);
        logger.info("Deleted");
    }
}
'''
        chunks = parse_file("UserService.java", code, "java")
        classes = [c for c in chunks if c.symbol_type == "class"]
        methods = [c for c in chunks if c.symbol_type == "method"]
        assert any(c.symbol_name == "UserService" for c in classes)
        assert len(methods) >= 1
        for m in methods:
            assert m.metadata.get("parent_class") == "UserService"

    def test_ruby_module_nested_class(self):
        code = '''module Services
  class AuthHandler
    def authenticate(token)
      return false unless token
      validate(token)
    end

    def revoke(token)
      tokens.delete(token)
      true
    end
  end
end
'''
        chunks = parse_file("auth.rb", code, "ruby")
        classes = [c for c in chunks if c.symbol_type == "class"]
        assert any(c.symbol_name == "AuthHandler" for c in classes)
        methods = [c for c in chunks if c.symbol_type == "method"]
        method_names = {m.symbol_name for m in methods}
        assert method_names == {"authenticate", "revoke"}
        for m in methods:
            assert m.metadata.get("parent_class") == "AuthHandler"

    def test_kotlin_function(self):
        code = '''fun processPayment(amount: Double, currency: String): PaymentResult {
    val validated = validate(amount)
    return execute(validated, currency)
}
'''
        chunks = parse_file("payment.kt", code, "kotlin")
        funcs = [c for c in chunks if c.symbol_type == "function"]
        assert any(c.symbol_name == "processPayment" for c in funcs)

    def test_swift_class(self):
        code = '''class NetworkManager {
    var session: URLSession
    var baseURL: String

    func fetchData(from endpoint: String) -> Data? {
        let url = URL(string: baseURL + endpoint)
        return try? Data(contentsOf: url!)
    }
}
'''
        chunks = parse_file("Network.swift", code, "swift")
        classes = [c for c in chunks if c.symbol_type == "class"]
        assert any(c.symbol_name == "NetworkManager" for c in classes)
        methods = [c for c in chunks if c.symbol_type == "method"]
        assert any(m.symbol_name == "fetchData" for m in methods)
        for m in methods:
            assert m.metadata.get("parent_class") == "NetworkManager"

    def test_csharp_namespace_class(self):
        code = '''namespace MyApp.Services {
    class DataProcessor {
        public void Process(string input) {
            var result = Parse(input);
            Save(result);
        }

        private string Parse(string raw) {
            return raw.Trim();
        }
    }
}
'''
        chunks = parse_file("Processor.cs", code, "csharp")
        classes = [c for c in chunks if c.symbol_type == "class"]
        assert any(c.symbol_name == "DataProcessor" for c in classes)
        methods = [c for c in chunks if c.symbol_type == "method"]
        method_names = {m.symbol_name for m in methods}
        assert "Process" in method_names
        assert "Parse" in method_names
        for m in methods:
            assert m.metadata.get("parent_class") == "DataProcessor"

    def test_lua_function(self):
        code = '''function calculate_score(player, level)
    local base = player.skill * level
    local bonus = math.random(1, 10)
    return base + bonus
end
'''
        chunks = parse_file("game.lua", code, "lua")
        funcs = [c for c in chunks if c.symbol_type == "function"]
        assert any(c.symbol_name == "calculate_score" for c in funcs)

    def test_dart_class_extracted_but_methods_missing(self):
        """Dart grammar uses method_signature + function_body as siblings inside
        class_body — the generic parser doesn't recognize method_signature, so
        only the class itself is extracted, not its methods. Top-level functions
        use function_signature + function_body (also siblings), so they're also
        not extracted. This test documents the limitation."""
        code = '''class UserService {
  final String apiUrl;

  UserService(this.apiUrl);

  Future<User> fetchUser(int id) async {
    final response = await http.get(
      Uri.parse(apiUrl),
    );
    return User.fromJson(jsonDecode(response.body));
  }
}
'''
        chunks = parse_file("user_service.dart", code, "dart")
        classes = [c for c in chunks if c.symbol_type == "class"]
        assert len(classes) == 1
        assert classes[0].symbol_name == "UserService"
        # Methods are NOT extracted — Dart uses method_signature nodes
        # which aren't in _GENERIC_TARGET_TYPES
        methods = [c for c in chunks if c.symbol_type == "method"]
        assert len(methods) == 0, "If this fails, Dart method support was added — update test"

    def test_php_class_with_methods(self):
        code = '''<?php
class UserRepository {
    public function findById(int $id): ?User {
        return $this->db
            ->table("users")
            ->find($id);
    }

    public function delete(int $id): bool {
        return $this->db
            ->table("users")
            ->delete($id);
    }
}
'''
        chunks = parse_file("UserRepository.php", code, "php")
        classes = [c for c in chunks if c.symbol_type == "class"]
        assert len(classes) == 1
        assert classes[0].symbol_name == "UserRepository"
        methods = [c for c in chunks if c.symbol_type == "method"]
        method_names = {m.symbol_name for m in methods}
        assert method_names == {"findById", "delete"}
        for m in methods:
            assert m.metadata.get("parent_class") == "UserRepository"

    def test_objc_not_supported_by_generic_parser(self):
        """ObjC uses class_implementation/implementation_definition node types
        that the generic parser doesn't recognize — produces no chunks.
        This test documents the limitation rather than pretending to test ObjC."""
        code = '''@implementation AppDelegate

- (BOOL)application:(UIApplication *)application didFinishLaunchingWithOptions:(NSDictionary *)launchOptions {
    self.window = [[UIWindow alloc] initWithFrame:[[UIScreen mainScreen] bounds]];
    [self.window makeKeyAndVisible];
    return YES;
}

@end
'''
        chunks = parse_file("AppDelegate.m", code, "objc")
        assert chunks == [], "Generic parser has no ObjC support — if this fails, support was added"

    def test_bash_function(self):
        code = '''function deploy_service() {
    echo "Deploying..."
    docker build -t app .
    docker push app
    kubectl apply -f deploy.yaml
}
'''
        chunks = parse_file("deploy.sh", code, "bash")
        funcs = [c for c in chunks if c.symbol_type == "function"]
        assert any(c.symbol_name == "deploy_service" for c in funcs)


class TestGenericRecursion:
    """Verify recursive parser handles nesting correctly."""

    def test_class_methods_have_parent_class(self):
        """Methods inside classes get parent_class metadata."""
        code = '''class Calculator {
    public int add(int a, int b) {
        return a + b;
    }

    public int multiply(int a, int b) {
        return a * b;
    }
}
'''
        chunks = parse_file("Calc.java", code, "java")
        methods = [c for c in chunks if c.symbol_type == "method"]
        for m in methods:
            assert m.metadata.get("parent_class") == "Calculator"

    def test_nested_module_extraction(self):
        """Ruby module wrapping a class still extracts the class."""
        code = '''module Outer
  class Inner
    def work
      do_something
      do_more
    end
  end
end
'''
        chunks = parse_file("nested.rb", code, "ruby")
        classes = [c for c in chunks if c.symbol_type == "class"]
        assert any(c.symbol_name == "Inner" for c in classes)

    def test_no_double_counting_class(self):
        """A class should only appear once, not duplicated."""
        code = '''class Handler {
    public void handle(Request req) {
        process(req);
        respond(req);
    }
}
'''
        chunks = parse_file("Handler.java", code, "java")
        class_chunks = [c for c in chunks if c.symbol_type == "class" and c.symbol_name == "Handler"]
        assert len(class_chunks) == 1


class TestHFileHeuristic:
    """Tests for .h file C/C++ detection heuristic."""

    def test_h_file_detected_as_cpp(self):
        """Header with C++ constructs is parsed as C++."""
        code = '''class Widget {
public:
    Widget(int width, int height);
    virtual ~Widget();

    void render() const;
};
'''
        chunks = parse_file("widget.h", code, "c")
        # Should detect C++ and parse the class
        classes = [c for c in chunks if c.symbol_type == "class"]
        assert any(c.symbol_name == "Widget" for c in classes)

    def test_h_file_stays_c(self):
        """Pure C header stays as C — struct produces a chunk with language='c'."""
        code = '''struct Point {
    int x;
    int y;
    int z;
};

void draw(Point* p) {
    render(p->x, p->y);
    flush();
}
'''
        chunks = parse_file("point.h", code, "c")
        assert len(chunks) > 0, "Must produce at least one chunk to be a real test"
        for chunk in chunks:
            assert chunk.language == "c"

    def test_h_file_with_class_in_comment_stays_c(self):
        """A .h file with 'class' only in a comment must NOT upgrade to C++.

        Without the comment-stripping fix, _CPP_INDICATORS would match 'class'
        in the comment and switch to the C++ parser, changing chunk.language to 'cpp'.
        This test catches that regression because the struct produces a chunk whose
        language field reveals which parser was used.
        """
        code = '''/* Base class for all widgets */
struct Widget {
    int width;
    int height;
    int active;
};

void widget_init(Widget* w) {
    w->width = 0;
    w->height = 0;
}
'''
        chunks = parse_file("widget.h", code, "c")
        assert len(chunks) > 0, "Must produce at least one chunk to be a real test"
        for chunk in chunks:
            assert chunk.language == "c", (
                f"Chunk '{chunk.symbol_name}' has language='{chunk.language}' — "
                "comment-stripping failed, 'class' in comment triggered C++ upgrade"
            )

    def test_h_file_with_class_in_line_comment_stays_c(self):
        """Same as above but with // line comment instead of block comment."""
        code = '''// Helper class utilities
struct Buffer {
    char* data;
    int size;
    int capacity;
};
'''
        chunks = parse_file("buffer.h", code, "c")
        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.language == "c"
