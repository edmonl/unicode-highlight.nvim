# Data Sources

`confusable-overrides.json` contains local overrides applied after parsing Unicode
security confusables data.

`scripts/generate_data.py` downloads the pinned Unicode source file on demand:

```text
https://www.unicode.org/Public/security/16.0.0/confusables.txt
```

The downloaded file is cached at `cache/confusables-16.0.0.txt`.
