"""Fixed task set: 10 small coding/file tasks, each with seed files and a checker.

Checkers run outside the sandbox on the files the agent left behind.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass
class Task:
    id: str
    prompt: str
    check: Callable[[Path], bool]
    files: dict[str, str] = field(default_factory=dict)


def _read(p: Path) -> str | None:
    return p.read_text() if p.is_file() else None


def _py(root: Path, code: str) -> bool:
    r = subprocess.run([sys.executable, "-B", "-c", code], cwd=root, capture_output=True, text=True, timeout=30)
    return r.returncode == 0


LOG = "\n".join(
    f"2026-11-{d:02d} {lvl} {msg}"
    for d, lvl, msg in [
        (1, "INFO", "boot"), (1, "ERROR", "disk full"), (2, "WARN", "slow"),
        (2, "ERROR", "timeout"), (3, "INFO", "ok"), (3, "ERROR", "oom"),
        (4, "INFO", "ERRORS are not counted here? yes they are"), (5, "DEBUG", "x"),
    ]
) + "\n"

SALES = "region,amount\nnorth,120.50\nsouth,80\neast,99.50\nwest,200\n"

TASKS: list[Task] = [
    Task("hello_file",
         "Create a file named hello.txt whose entire content is exactly: Hello, DeepSeek!",
         lambda r: (_read(r / "hello.txt") or "").strip() == "Hello, DeepSeek!"),

    Task("fix_add_bug",
         "calc.py has a bug: add() returns the wrong result. Fix it so add(a, b) returns a + b. Do not change other functions.",
         lambda r: _py(r, "import calc; assert calc.add(2,3)==5 and calc.mul(2,3)==6"),
         {"calc.py": "def add(a, b):\n    return a - b\n\n\ndef mul(a, b):\n    return a * b\n"}),

    Task("fizzbuzz",
         "Write fizzbuzz.py with a function fizzbuzz(n) that returns a list of strings for 1..n: "
         "'Fizz' for multiples of 3, 'Buzz' for multiples of 5, 'FizzBuzz' for both, otherwise the number as a string.",
         lambda r: _py(r, "from fizzbuzz import fizzbuzz as f; o=f(15); "
                          "assert o[:5]==['1','2','Fizz','4','Buzz'] and o[14]=='FizzBuzz' and len(o)==15")),

    Task("count_errors",
         "Count the lines in app.log whose log level (the second field) is ERROR. "
         "Write only that number to count.txt.",
         lambda r: (_read(r / "count.txt") or "").strip() == "3",
         {"app.log": LOG}),

    Task("edit_json",
         "In config.json set \"debug\" to true and \"retries\" to 5. Keep every other key unchanged and keep the file valid JSON.",
         lambda r: (lambda c: c == {"name": "svc", "debug": True, "retries": 5, "tags": ["a", "b"]})(
             json.loads(_read(r / "config.json") or "null")),
         {"config.json": json.dumps({"name": "svc", "debug": False, "retries": 1, "tags": ["a", "b"]}, indent=2)}),

    Task("palindrome_tests",
         "Implement is_palindrome(s) in strings_util.py: ignore case and any non-alphanumeric characters. "
         "Make the tests in test_strings_util.py pass (run them with: python test_strings_util.py).",
         lambda r: _py(r, "import runpy; runpy.run_path('test_strings_util.py', run_name='__main__')")
                   and _py(r, "from strings_util import is_palindrome as p; assert p('Was it a car or a cat I saw?') and not p('abca')"),
         {"strings_util.py": "def is_palindrome(s):\n    raise NotImplementedError\n",
          "test_strings_util.py": "from strings_util import is_palindrome\n\n"
                                  "if __name__ == '__main__':\n"
                                  "    assert is_palindrome('A man, a plan, a canal: Panama')\n"
                                  "    assert is_palindrome('')\n"
                                  "    assert not is_palindrome('hello')\n"
                                  "    print('ok')\n"}),

    Task("csv_total",
         "sales.csv has a header and an 'amount' column. Compute the sum of amount and write it to total.txt "
         "with exactly two decimals (e.g. 12.30).",
         lambda r: (_read(r / "total.txt") or "").strip() == "500.00",
         {"sales.csv": SALES}),

    Task("make_package",
         "Create a Python package directory named mypkg with an __init__.py that defines VERSION = \"1.0.0\" "
         "and a function greet(name) returning 'Hello, <name>!'.",
         lambda r: _py(r, "import mypkg; assert mypkg.VERSION=='1.0.0' and mypkg.greet('Ada')=='Hello, Ada!'")),

    Task("fix_slugify",
         "text.py has a slugify(s) function that fails its tests. Fix slugify so test_text.py passes "
         "(run: python test_text.py). Lowercase, words joined by single '-', no leading/trailing '-', "
         "drop characters that are not letters, digits or spaces.",
         lambda r: _py(r, "import runpy; runpy.run_path('test_text.py', run_name='__main__')")
                   and _py(r, "from text import slugify; assert slugify('  C++ & Rust  rock ')=='c-rust-rock'"),
         {"text.py": "def slugify(s):\n    return s.replace(' ', '-')\n",
          "test_text.py": "from text import slugify\n\n"
                          "if __name__ == '__main__':\n"
                          "    assert slugify('Hello World') == 'hello-world'\n"
                          "    assert slugify('  Spaces   everywhere ') == 'spaces-everywhere'\n"
                          "    assert slugify('Rock & Roll!') == 'rock-roll'\n"
                          "    print('ok')\n"}),

    Task("merge_sorted",
         "Merge the lines of a.txt and b.txt into merged.txt: unique lines only, sorted alphabetically, one per line.",
         lambda r: (_read(r / "merged.txt") or "").split() == ["apple", "banana", "cherry", "date", "fig"],
         {"a.txt": "banana\napple\nfig\n", "b.txt": "date\napple\ncherry\nbanana\n"}),
]


def seed(task: Task, root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for rel, content in task.files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(content)

