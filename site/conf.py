import os

from sphinx.util.docutils import SphinxDirective

project = 'RxDjango'
author = 'RxDjango contributors'

extensions = ['myst_parser']
source_suffix = {'.md': 'markdown'}
master_doc = 'index'

exclude_patterns = [
    '_build', 'Thumbs.db', '.DS_Store',
    'adr', 'rfcs', 'dev',
    # Loose drafts not yet linked from the root toctree.
    '01-static-rx-push.md', 'issues.md', 'rxdjango-spec.md',
]

html_theme = 'basic'
pygments_style = 'monokai'
html_title = 'RxDjango'
html_static_path = ['_static']
templates_path = ['_templates']
html_css_files = ['custom.css']

html_show_sphinx = False
html_show_sourcelink = False
html_copy_source = False
html_use_index = False
html_domain_indices = False

# Base URL where the live demo React app is served. Each example is
# loaded in an iframe at "<demo_base_url>/react/<app>/demo".
demo_base_url = os.environ.get('DEMO_URL', '')

html_context = {
    'demo_base_url': demo_base_url,
}

myst_enable_extensions = ['colon_fence']


class RxDemoDirective(SphinxDirective):
    """Mark a page as having a live demo app.

    Usage:

        ```{rxdemo} appname
        ```

    Renders nothing inline; stores the app name on the page's
    environment metadata so the template can render the iframe in
    the right-hand demo column.
    """

    required_arguments = 1
    final_argument_whitespace = False
    has_content = False
    option_spec = {}

    def run(self):
        app_name = self.arguments[0].strip()
        self.env.metadata.setdefault(self.env.docname, {})
        self.env.metadata[self.env.docname]['rxdemo'] = app_name
        return []


def _page_context(app, pagename, templatename, context, doctree):
    metadata = app.env.metadata.get(pagename, {})
    context['rxdemo_app'] = metadata.get('rxdemo')


def setup(app):
    app.add_directive('rxdemo', RxDemoDirective)
    app.connect('html-page-context', _page_context)
    return {'parallel_read_safe': True, 'parallel_write_safe': True}
