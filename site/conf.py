project = 'RxDjango'
author = 'RxDjango contributors'

extensions = ['myst_parser']
source_suffix = {'.md': 'markdown'}
master_doc = 'index'

exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

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

# Base URL where the live demo React app is served. Each example is loaded
# in an iframe at "<demo_base_url>/<example_name>".
demo_base_url = 'http://localhost:3000'

html_context = {
    'demo_base_url': demo_base_url,
}

myst_enable_extensions = ['colon_fence']
