# Eval: DeepSeek Harness agent vs plain tool-calling loop

- Model: `deepseek-r1-8b-12k` via Ollama (local) · run `20261118-031936` · 3 tasks · same sandboxed tools for both
- Generated 2026-11-18 03:50

## Summary

| Agent | Passed | Success rate | Median time / task | Total time | Tool calls |
|---|---|---|---|---|---|
| harness | 0/3 | 0% | 301.5s | 904s | 0 |
| baseline | 0/3 | 0% | 300.2s | 901s | 0 |

## Per task

| Task | harness | baseline |
|---|---|---|
| hello_file | ❌ 301s (timeout) | ❌ 300s (timeout) |
| fix_add_bug | ❌ 302s (timeout) | ❌ 300s (timeout) |
| fizzbuzz | – | – |
| count_errors | ❌ 302s (timeout) | ❌ 301s (timeout) |
| edit_json | – | – |
| palindrome_tests | – | – |
| csv_total | – | – |
| make_package | – | – |
| fix_slugify | – | – |
| merge_sorted | – | – |
