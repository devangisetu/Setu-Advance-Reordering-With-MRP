# -*- coding: utf-8 -*-
from odoo import fields, models


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    real_demand_id = fields.Many2one(
        'advance.reorder.product.real.demand',
        string='Product-Wise Real Demand',
        index=True,
        ondelete='set null',
    )
