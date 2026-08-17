# -*- coding: utf-8 -*-
from odoo import fields, models


class AdvanceReorderProductRealDemandLine(models.Model):
    _name = 'advance.reorder.product.component.line'
    _description = 'Product-Wise Real Demand Component Line'
    _order = 'product_id, id'

    real_demand_id = fields.Many2one(
        'advance.reorder.product.real.demand',
        required=True,
        ondelete='cascade',
        index=True,
    )
    product_id = fields.Many2one('product.product', string='Product', required=True)
    calculated_lead_days = fields.Float(string='Lead Days')
