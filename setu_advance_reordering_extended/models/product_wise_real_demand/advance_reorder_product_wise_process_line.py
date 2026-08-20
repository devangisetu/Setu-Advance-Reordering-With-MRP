# -*- coding: utf-8 -*-
from odoo import fields, models


class AdvanceReorderProductRealDemandCalcLine(models.Model):
    _name = 'advance.reorder.product.wise.process.line'
    _description = 'Product-Wise Real Demand Calculation Line'
    _order = 'product_id, id'

    product_wise_reorder_id = fields.Many2one(
        'advance.reorder.product.wise.process',
        string='Product-Wise Real Demand',
        required=True,
        ondelete='cascade',
        index=True,
    )
    product_id = fields.Many2one('product.product', string='Product', required=True)
    average_daily_sale = fields.Float(string='ADS', help='Average daily sales')
    available_stock = fields.Float(string='Free qty')
    incoming_qty = fields.Float(string='Incoming')
    stock_move_ids = fields.Many2many('stock.move', string='Stock Move')
    transit_time_sales = fields.Float(string='Transit sales')
    stock_after_transit = fields.Float(string='Stock after transit')
    expected_sales = fields.Float(string='Coverage days sales')
    sales_qty = fields.Float(string='Sales Qty')
    sales_return_qty = fields.Float(string='Sales Return Qty')
    consumed_qty = fields.Float(string='Consumed Qty')
    resupply_qty = fields.Float(string='Resupply Qty')
    resupply_return_qty = fields.Float(string='Resupply Return Qty')
    scrap_qty = fields.Float(string='Scrap Qty')
    demanded_qty = fields.Float(string='Demand')
    demand_adjustment_qty = fields.Integer(string='To be ordered')

    def action_incoming_qty_stock_move(self):
        """Open incoming stock moves for this demand line."""
        action = self.env['ir.actions.actions']._for_xml_id(
            'setu_advance_reordering.actions_advance_reorder_stock_move'
        )
        action['domain'] = [('id', 'in', self.stock_move_ids.ids)]
        return action
