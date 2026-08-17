# -*- coding: utf-8 -*-
from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    real_demand_id = fields.Many2one(
        'advance.reorder.product.real.demand',
        string='Product-Wise Real Demand',
        index=True,
        ondelete='set null',
    )
