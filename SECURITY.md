# Security Policy

## Sensitive data

The IELTSBro bearer token grants access to data in the signed-in account. Never paste it into an issue, pull request, screenshot, CI variable, or public log.

The exporter keeps the token in process memory only. It does not persist the token or include request headers in exported files. Exported records may still contain personal study data and copyrighted material, so keep export directories private.

## Supported use

Use this project only with an account and data you are authorized to access. The tool intentionally implements read-only record endpoints. Requests to add account takeover, access-control bypass, bulk content scraping, or write/delete operations will not be accepted.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting feature if it is enabled for the repository. Do not include a real token or unredacted export. A minimal synthetic reproduction is preferred.

If you accidentally publish a token, sign out of IELTSBro and sign in again to invalidate the exposed session before removing it from Git history.
