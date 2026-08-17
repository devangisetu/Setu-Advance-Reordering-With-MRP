# -*- coding: utf-8 -*-
from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    product_wise_reorder_id = fields.Many2one(
        'advance.reorder.product.wise.process',
        string='Product-Wise Real Demand',
        index=True,
        ondelete='set null',
    )
