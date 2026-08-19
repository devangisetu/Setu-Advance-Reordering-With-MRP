# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AdvanceReorderProductComponentLine(models.Model):
    _name = 'advance.reorder.product.component.line'
    _description = 'Product-Wise Real Demand Component Line'
    _parent_store = True
    _parent_name = 'parent_id'
    _order = 'parent_path, id'

    product_wise_reorder_id = fields.Many2one(
        'advance.reorder.product.wise.process',
        required=True,
        ondelete='cascade',
        index=True,
    )
    parent_id = fields.Many2one(
        'advance.reorder.product.component.line',
        string='Parent Component',
        index=True,
        ondelete='cascade',
    )
    parent_path = fields.Char(index=True, unaccent=False)
    child_ids = fields.One2many(
        'advance.reorder.product.component.line',
        'parent_id',
        string='Child Components',
    )
    level = fields.Integer(string='Level', default=0)
    product_id = fields.Many2one('product.product', string='Product', required=True)
    product_display = fields.Char(
        string='Product',
        compute='_compute_product_display',
    )
    actual_lead_days = fields.Float(string='Actual Lead Days',)
    lead_days = fields.Float(string='Lead Days')
    manufacture_lead_days = fields.Float(
        string='Manufacture Lead Days',
        help='Manufacturing lead days from the selected BOM produce delay.',
    )

    @api.depends('product_id', 'product_id.display_name', 'level', 'parent_id')
    def _compute_product_display(self):
        for line in self:
            name = line.product_id.display_name or ''
            level = line.level or 0
            if level:
                indent = '\u2003' * level
                line.product_display = f'{indent}↳ {name}'
            else:
                line.product_display = name
