# -*- coding: utf-8 -*-
from odoo import fields, models


class AdvanceReorderProductwiseByProductLine(models.Model):
    _name = 'advance.reorder.productwise.by.product.line'
    _description = 'Product-Wise By Product Line'
    _order = 'product_id, id'

    product_wise_reorder_id = fields.Many2one(
        'advance.reorder.product.wise.process',
        string='Product-Wise Real Demand',
        required=True,
        ondelete='cascade',
        index=True,
    )
    source_product_id = fields.Many2one('product.product', string='Generated From')
    source_product_demand = fields.Float(string='Production Quantity')
    product_id = fields.Many2one('product.product', string='Product')
    quantity = fields.Float(
        string='Expected Quantity',
        help='By-product quantity: parent MO qty × (BOM by-product qty / BOM qty).',
    )
