---
name: ieltsbro-exporter
description: Export and verify a user's own IELTSBro (雅思哥) PC learning records with the bundled read-only tool. Use for 雅思哥学习记录导出、错题备份、文章备份、数据迁移 or troubleshooting an existing export; require explicit authorization before reading the local login token.
---

# IELTSBro Exporter

Back up the user's own IELTSBro learning history without changing server data. Resolve commands and files relative to this `SKILL.md`; the bundled executable is `ieltsbro_export.py` and the Windows launcher is `run_export.ps1`.

## Authorization boundary

Treat the bearer token and every export as sensitive account data.

- Obtain explicit authorization in the current conversation before reading a local IELTSBro login token. A request to export using the signed-in PC client is sufficient; a general question about the tool is not.
- Keep the token in process memory. Use `--profile` so the bundled script reads it directly; never print, copy into chat, persist, or place it in a command string.
- Send the token only to the fixed API origin compiled into the exporter.
- Export only data the user is authorized to access. Keep exports local unless the user separately asks to move them to a specific private destination.
- Keep the read-only boundary: do not add or call answer submission, deletion, account mutation, access-control bypass, or bulk public-content collection endpoints.

## Workflow

1. Confirm Windows, Python 3, the desired output directory, and whether local-login access is authorized. Prefer an output directory in the user's current workspace, outside this skill folder.
2. When local-login access is authorized, use the IELTSBro profile at `$env:APPDATA\雅思哥机考软件` unless the user identifies another profile. If authorization is absent, offer hidden interactive token entry in a terminal instead of asking for a token in chat.
3. Run the bundled exporter. On Windows, prefer:

   ```powershell
   .\run_export.ps1 -Profile "$env:APPDATA\雅思哥机考软件" -Out "<authorized-output-directory>"
   ```

   Resolve `.\run_export.ps1` against this skill's directory, not the user's current directory.
4. Read `manifest.json` and `failures.json` after the process exits. Completion requires an existing output directory, a parseable manifest, and every failure reported to the user. A non-empty failure list means partial success, not full completion.
5. Report the output path and counts for practice records, exams, wrong answers, articles, and failures. Do not quote article or question content unless the user asks to inspect it.

## Verification and troubleshooting

- Use `-CheckOnly` when the user asks only to validate login or connectivity.
- A login-expired error is a stopping condition: ask the user to sign in again, then retry once.
- For individual detail failures, preserve successful files and use `failures.json`; rerunning the same output directory reuses raw detail caches.
- If parsing breaks after a client update, read `TECHNICAL_NOTES.md`, retain the raw response, create a minimal redacted fixture, and update tests before changing the parser.
- Run `python -m unittest -v` after code changes. Tests must remain offline and use synthetic data.

## Public-data boundary

Repository changes may contain code, synthetic tests, and redacted schemas. They must not contain real bearer tokens, account identifiers, exported records, copyrighted passages, or generated export directories.
