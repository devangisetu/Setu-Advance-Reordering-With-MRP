{
    "name": "Python Editor",
    "description": """
        Installing this module, user will able to execute python code from Odoo.
    """,
    "author": "Setu Consulting Services Pvt. Ltd.",
    "version": "18.0",
    'license' : 'LGPL-3',
    "depends": ["base"],
    "init_xml": [],
    'external_dependencies': {
        'python': ['pandas']
    },
    "data": [
        'data/developer_utility.xml',
        'security/ir.model.access.csv',
        'view/python_code_view.xml',
        'view/ir_module_views.xml',
    ],
    'assets': {
        'web.assets_backend': [

            'setu_python_editor/static/src/js/lib/codemirror.css',
            'setu_python_editor/static/src/js/lib/codemirror.js',
            'setu_python_editor/static/src/js/theme/dracula.css',
            'setu_python_editor/static/src/js/mode/python/python.js',
            'setu_python_editor/static/src/js/addon/hint/show-hint.css',
            'setu_python_editor/static/src/js/addon/dialog/dialog.css',
            'setu_python_editor/static/src/js/addon/display/fullscreen.css',
            'setu_python_editor/static/src/js/addon/fold/foldgutter.css',
            'setu_python_editor/static/src/js/addon/hint/show-hint.js',
            'setu_python_editor/static/src/js/addon/hint/python-hint.js',
            'setu_python_editor/static/src/js/addon/search/search.js',
            'setu_python_editor/static/src/js/addon/search/jump-to-line.js',
            'setu_python_editor/static/src/js/addon/search/searchcursor.js',
            'setu_python_editor/static/src/js/addon/dialog/dialog.js',
            'setu_python_editor/static/src/js/addon/display/fullscreen.js',
            'setu_python_editor/static/src/js/addon/comment/comment.js',
            'setu_python_editor/static/src/js/addon/comment/continuecomment.js',
            'setu_python_editor/static/src/js/addon/fold/foldcode.js',
            'setu_python_editor/static/src/js/addon/fold/foldgutter.js',
            'setu_python_editor/static/src/js/addon/fold/indent-fold.js',
            'setu_python_editor/static/src/js/addon/fold/brace-fold.js',
            'setu_python_editor/static/src/js/addon/fold/comment-fold.js',
            'setu_python_editor/static/src/js/addon/selection/mark-selection.js',
            'setu_python_editor/static/src/js/addon/edit/matchbrackets.js',


            'setu_python_editor/static/src/js/setu_python_playground.js',
            'setu_python_editor/static/src/xml/**/*',

            'setu_python_editor/static/src/scss/main.scss',
        ],
    },
    "demo_xml": [],
    "installable": True,
}
