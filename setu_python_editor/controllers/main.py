# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import http
from odoo.addons.web.controllers.home import Home as WebHome
from odoo.http import request
from odoo.tools.misc import str2bool

ALLOWED_DEBUG_MODES = ['', '1', 'assets', 'tests', 'disable-t-cache']


class home(WebHome):

    @http.route()
    def web_client(self, s_action=None, **kw):
        if request.session.uid and request.env['res.users'].sudo().browse(request.session.uid).has_group(
                'setu_python_editor.group_developer_utility'):
            request.session.debug = ','.join(
                mode if mode in ALLOWED_DEBUG_MODES
                else '1' if str2bool(mode, mode)
                else ''
                for mode in ('1' or '').split(',')
            )
        return super().web_client(s_action, **kw)