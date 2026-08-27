# File-link fixtures

The file-link tests build minimal PDF and DOCX documents in memory so the
fixtures stay deterministic and contain no candidate PII. The synthetic
documents cover:

- standard PDF and DOCX metadata, including missing and malformed values;
- visible URLs and embedded targets with matching, friendly-label, duplicate,
  and mismatching cases;
- DOCX body, table, header, and footer hyperlinks;
- malformed or missing hyperlink relationships; and
- controlled public, unavailable, unsafe, and redirect outcomes through fake
  DNS and HTTP seams.

All names, URLs, and evidence values in these tests use `example.com` or
synthetic labels.
