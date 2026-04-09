#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from html import escape
from html.parser import HTMLParser
from pathlib import Path


@dataclass(frozen=True)
class BookmarkEntry:
    category: str
    name: str
    url: str


class KnowledgeBookmarksParser(HTMLParser):
    """Parse a Netscape bookmarks export and collect entries from Knowledge."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.folder_stack: list[str] = []
        self.pending_folder: str | None = None
        self.in_h3 = False
        self.in_a = False
        self.current_h3 = ""
        self.current_name = ""
        self.current_href: str | None = None
        self.knowledge_found = False
        self.entries: list[BookmarkEntry] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        tag = tag.lower()

        if tag == "h3":
            self.in_h3 = True
            self.current_h3 = ""
            return

        if tag == "a":
            self.in_a = True
            self.current_name = ""
            self.current_href = attr_map.get("href")
            return

        if tag == "dl" and self.pending_folder is not None:
            self.folder_stack.append(self.pending_folder)
            if self.pending_folder == "Knowledge":
                self.knowledge_found = True
            self.pending_folder = None

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()

        if tag == "h3":
            folder_name = self.current_h3.strip()
            if folder_name:
                self.pending_folder = folder_name
            self.in_h3 = False
            self.current_h3 = ""
            return

        if tag == "a":
            self._finish_bookmark()
            self.in_a = False
            self.current_name = ""
            self.current_href = None
            return

        if tag == "dl" and self.folder_stack:
            self.folder_stack.pop()

    def handle_data(self, data: str) -> None:
        if self.in_h3:
            self.current_h3 += data
        elif self.in_a:
            self.current_name += data

    def _finish_bookmark(self) -> None:
        if not self.current_href or "Knowledge" not in self.folder_stack:
            return

        knowledge_index = self.folder_stack.index("Knowledge")
        subfolders = self.folder_stack[knowledge_index + 1 :]
        category = " / ".join(subfolders) if subfolders else "Knowledge"
        name = self.current_name.strip() or self.current_href
        self.entries.append(BookmarkEntry(category=category, name=name, url=self.current_href))


def parse_bookmarks(input_path: Path) -> list[BookmarkEntry]:
    parser = KnowledgeBookmarksParser()
    parser.feed(input_path.read_text(encoding="utf-8"))
    parser.close()

    if not parser.knowledge_found:
        raise ValueError('Folder "Knowledge" was not found in the bookmarks file.')

    return sorted(parser.entries, key=lambda entry: (entry.category.casefold(), entry.name.casefold(), entry.url))


def build_html_table(entries: list[BookmarkEntry]) -> str:
    lines = [
        "<table>",
        "  <thead>",
        "    <tr><th>Name</th><th>Category</th><th>URL</th></tr>",
        "  </thead>",
        "  <tbody>",
    ]

    for entry in entries:
        category = escape(entry.category, quote=True)
        name = escape(entry.name, quote=True)
        url = escape(entry.url, quote=True)
        lines.append(
            f'    <tr><td>{name}</td><td>{category}</td><td><a href="{url}">{url}</a></td></tr>'
        )

    lines.extend(["  </tbody>", "</table>"])
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract bookmarks from the Knowledge folder and render them as an HTML table."
    )
    parser.add_argument("input_bookmarks", type=Path, help="Path to the Netscape-format bookmarks HTML file.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Optional output path for the generated HTML table fragment. Defaults to stdout.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    try:
        entries = parse_bookmarks(args.input_bookmarks)
        html_table = build_html_table(entries)
    except FileNotFoundError:
        print(f"Input file not found: {args.input_bookmarks}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.output is not None:
        args.output.write_text(html_table, encoding="utf-8")
    else:
        print(html_table)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
