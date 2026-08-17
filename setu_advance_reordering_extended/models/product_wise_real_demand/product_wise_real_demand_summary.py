# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AdvanceReorderProductRealDemandSummary(models.Model):
    _name = 'advance.reorder.product.wise.order.summary'
    _description = 'Product-Wise Real Demand Summary'
    _order = 'product_id, id'

    real_demand_id = fields.Many2one(
        'advance.reorder.product.wise.process',
        string='Product-Wise Real Demand',
        required=True,
        ondelete='cascade',
        index=True,
    )
    product_id = fields.Many2one('product.product', string='Product', required=True)
    warehouse_group_id = fields.Many2one('stock.warehouse.group', string='Warehouse group')
    vendor_moq = fields.Integer(string='Vendor MOQ')
    demanded_qty = fields.Integer(string='Demand')
    order_qty = fields.Integer(string='To be ordered')
    total_volume = fields.Float(string='Total volume')
    to_be_ordered_in_purchase_uom = fields.Integer(string='To Be Ordered In Purchase UoM')
    uom_id = fields.Many2one(related='product_id.uom_id', string='Product UOM')
    uom_po_id = fields.Many2one(related='product_id.uom_po_id', string='Purchase UOM')
    product_volume = fields.Float(related='product_id.volume', string='Volume')
    volume_uom_name = fields.Char(related='product_id.volume_uom_name', string='Volume UOM')
    product_weight = fields.Float(related='product_id.weight', string='Weight')
    order_action = fields.Selection(
        selection=[
            ('purchase', 'Generate Purchase Orders'),
            ('production', 'Generate Production Orders'),
            ('ict', 'Generate ICT'),
            ('iwt', 'Generate IWT'),
            ('subcontracting', 'Subcontracting'),
        ],
        string='Action',
        default='purchase',
    )
    is_order_moq = fields.Boolean(
        string='Is Order MOQ?',
        compute='_compute_is_order_moq',
        store=True,
    )

    @api.depends('vendor_moq', 'demanded_qty')
    def _compute_is_order_moq(self):
        for record in self:
            record.is_order_moq = record.vendor_moq > record.demanded_qty
