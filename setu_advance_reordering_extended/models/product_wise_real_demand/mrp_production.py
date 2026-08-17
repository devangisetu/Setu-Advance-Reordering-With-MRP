# -*- coding: utf-8 -*-
from odoo import fields, models


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    product_wise_reorder_id = fields.Many2one(
        'advance.reorder.product.wise.process',
        string='Product-Wise Real Demand',
        index=True,
        ondelete='set null',
    )
