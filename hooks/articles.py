"""Normalize optional article dates for sorting, display and structured data."""
from datetime import date

from mkdocs.exceptions import PluginError


def on_page_markdown(markdown, page, **kwargs):
    if page.meta.get("og_type") == "article":
        for field in ("published_date", "modified_date"):
            value = page.meta.get(field)
            if not value:
                page.meta.pop(field, None)
                continue
            try:
                page.meta[field] = date.fromisoformat(str(value))
            except ValueError as error:
                raise PluginError(f"{page.file.src_uri}: use YYYY-MM-DD for {field}") from error
    return markdown
