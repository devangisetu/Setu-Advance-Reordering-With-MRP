# -*- coding: utf-8 -*-
from odoo import fields, models


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    reorder_process_id = fields.Many2one(
        'advance.reorder.orderprocess',
        string='Advance Reorder Process',
        index=True,
    )
