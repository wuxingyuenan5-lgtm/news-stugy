# Output Contract

## Fetch JSON

`fetch_x_posts.py` writes compact JSON with this shape:

```json
{
  "generated_at": "2026-06-18T10:00:00+00:00",
  "window": {
    "start": "2026-06-15T10:00:00+00:00",
    "end": "2026-06-18T10:00:00+00:00"
  },
  "users": ["chenreason"],
  "posts": [
    {
      "author": "chenreason",
      "post_id": "123",
      "post_url": "https://x.com/chenreason/status/123",
      "published_at": "2026-06-17T22:30:00+00:00",
      "published_at_raw": "Jun 17, 2026 · 10:30 PM UTC",
      "text": "post text",
      "asset_class": "us-stocks",
      "signal_score": 2,
      "low_signal": false
    }
  ]
}
```

## Timeline Markdown

Default reader-facing output:

```markdown
# X Timeline Summary

- Window: ...
- Users: ...
- Posts kept: ...

## @creator

- 2026-06-18 06:30 CST | us-stocks
  - One-line summary
  - Source: https://x.com/...
```

## Grouped Markdown

Group by asset class first, then list short summaries.

## Card Markdown

Fixed research-card sections:

- Creator
- Window
- Coverage
- Main view
- Asset mix
- Key posts
