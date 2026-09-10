# Security policy

`assetcheck` is intended to run against untrusted manifests. It does not fetch URLs, execute media decoders, decompress archives, or write referenced files. By default it rejects absolute paths, `..` traversal, and symlinks, and caps each asset read.

Please report a path escape, unexpected network access, secret/payload leakage in a report, or a denial-of-service issue privately to the repository maintainer before opening a public issue. Include the version, operating system, and a minimal reproducer that contains no private data.
