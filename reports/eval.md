# Eval: DeepSeek Harness agent vs plain tool-calling loop

- Model: `qwen3.5-9b-12k` via Ollama (local) · run `20261118-025437` · 10 tasks · same sandboxed tools for both
- Generated 2026-11-18 03:50

## Summary

| Agent | Passed | Success rate | Median time / task | Total time | Tool calls |
|---|---|---|---|---|---|
| harness | 10/10 | 100% | 79.7s | 801s | 44 |
| baseline | 10/10 | 100% | 42.5s | 627s | 43 |

## Per task

| Task | harness | baseline |
|---|---|---|
| hello_file | ✅ 46s | ✅ 28s |
| fix_add_bug | ✅ 73s | ✅ 36s |
| fizzbuzz | ✅ 68s | ✅ 67s |
| count_errors | ✅ 95s | ✅ 38s |
| edit_json | ✅ 66s | ✅ 40s |
| palindrome_tests | ✅ 79s | ✅ 45s |
| csv_total | ✅ 81s | ✅ 87s |
| make_package | ✅ 80s | ✅ 37s |
| fix_slugify | ✅ 92s | ✅ 177s |
| merge_sorted | ✅ 121s | ✅ 73s |

See also [eval-deepseek-r1-8b-12k.md](eval-deepseek-r1-8b-12k.md): DeepSeek-R1-8B, 0/3 for both agents (timeouts, no tool calls).
Analysis: [README](../README.md#results-2026-11-18-apple-m5-16-gb-other-heavy-jobs-running-at-the-same-time).
