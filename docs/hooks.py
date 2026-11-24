"""MkDocs hook: clean up the notebook pages.

mkdocs-jupyter (0.27) adds its highlighting styles after each notebook as an
indented ``<style>`` block. With ``markdown_cell_processor: mkdocs`` that block
becomes a code block, shown at the bottom of the page and indexed by search.
This hook removes it.
"""

import re

STYLE_CODE_BLOCK = re.compile(
    r'<div class="highlight"><pre><span></span><code>\s*&lt;style&gt;.*?&lt;/style&gt;\s*</code></pre></div>',
    re.DOTALL,
)


def on_page_content(html, page, config, files):
    if not page.file.src_uri.endswith(".ipynb"):
        return html
    return STYLE_CODE_BLOCK.sub("", html)
