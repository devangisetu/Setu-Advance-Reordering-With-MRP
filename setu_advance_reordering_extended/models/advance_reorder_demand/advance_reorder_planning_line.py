# -*- coding: utf-8 -*-
from odoo import fields, models


class AdvanceReorderPlanningLine(models.TransientModel):
    _name = 'advance.reorder.planning.line'
    _description = 'Advance Reorder Planning Line'

    reorder_process_id = fields.Many2one('advance.reorder.orderprocess', string="Reorder Process")
    product_id = fields.Many2one('product.product', string="Product")
    net_demand = fields.Float(string="Net Demand")
    line_type = fields.Selection([('sfg', 'SFG'), ('component', 'Component')], string="Type")
