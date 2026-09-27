# Contributing

Bug reports and compatibility fixes are welcome.

Before opening an issue:

1. Remove bearer tokens, account identifiers, names, and other personal data.
2. Do not upload copyrighted passages, questions, audio, or full raw exports.
3. Reduce any response sample to the smallest synthetic or heavily redacted fixture that reproduces the parser problem.
4. Include the IELTSBro client version, operating system, command used, and the exact error message.

Before opening a pull request, run:

```powershell
python -m unittest -v
```

Changes must preserve the read-only boundary and must not introduce telemetry, token persistence, or third-party token forwarding.
