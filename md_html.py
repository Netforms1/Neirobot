"""Markdown → Telegram HTML converter.

Telegram supports a restricted set of HTML tags:
<b> <strong> <i> <em> <u> <s> <strike> <del>
<code> <pre> <blockquote> <a href=""> <tg-spoiler>
plus <pre><code class="language-xxx"> for syntax highlighting.

This converter keeps it simple and predictable: extract code blocks first
(so their content is not mangled), HTML-escape the rest, then apply
inline transforms.
"""

import html
import re

_CB_TOKEN = "\x00CB{}\x00"
_IC_TOKEN = "\x00IC{}\x00"


def md_to_html(text: str) -> str:
    code_blocks: list[tuple[str, str]] = []

    def _save_code_block(m: re.Match) -> str:
        lang = (m.group(1) or "").strip()
        code = m.group(2)
        code_blocks.append((lang, code))
        return _CB_TOKEN.format(len(code_blocks) - 1)

    text = re.sub(
        r"```([^\n`]*)\n(.*?)```",
        _save_code_block,
        text,
        flags=re.DOTALL,
    )

    inline_codes: list[str] = []

    def _save_inline(m: re.Match) -> str:
        inline_codes.append(m.group(1))
        return _IC_TOKEN.format(len(inline_codes) - 1)

    text = re.sub(r"`([^`\n]+)`", _save_inline, text)

    text = html.escape(text, quote=False)

    text = re.sub(r"^#{1,6}\s+(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)

    text = re.sub(r"\*\*([^*\n]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__([^_\n]+)__", r"<b>\1</b>", text)

    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"(?<![A-Za-z0-9_])_([^_\n]+)_(?![A-Za-z0-9_])", r"<i>\1</i>", text)

    text = re.sub(r"~~([^~\n]+)~~", r"<s>\1</s>", text)

    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', text)

    lines = text.split("\n")
    result: list[str] = []
    quote_buf: list[str] = []

    def _flush_quote() -> None:
        if quote_buf:
            result.append("<blockquote>" + "\n".join(quote_buf) + "</blockquote>")
            quote_buf.clear()

    for line in lines:
        m = re.match(r"^&gt;\s?(.*)$", line)
        if m:
            quote_buf.append(m.group(1))
        else:
            _flush_quote()
            result.append(line)
    _flush_quote()
    text = "\n".join(result)

    text = re.sub(r"^(\s*)[-*+]\s+", r"\1• ", text, flags=re.MULTILINE)
    text = re.sub(r"^(\s*)(\d+)\.\s+", r"\1\2. ", text, flags=re.MULTILINE)

    for i, code in enumerate(inline_codes):
        text = text.replace(
            _IC_TOKEN.format(i), f"<code>{html.escape(code, quote=False)}</code>"
        )

    for i, (lang, code) in enumerate(code_blocks):
        escaped = html.escape(code.rstrip("\n"), quote=False)
        if lang:
            block = (
                f'<pre><code class="language-{html.escape(lang)}">'
                f"{escaped}</code></pre>"
            )
        else:
            block = f"<pre>{escaped}</pre>"
        text = text.replace(_CB_TOKEN.format(i), block)

    return text
