# -*- coding: utf-8 -*-
from odoo import fields, models, api


class AdvanceReorderOrderprocessLine(models.Model):
    _inherit = 'advance.reorder.orderprocess.line'

    sales_qty = fields.Float(
        string='Sales Qty',
        help='Total sales quantity for the selected period.',
    )
    sales_return_qty = fields.Float(
        string='Sales Return Qty',
        help='Total sales return quantity for the selected period.',
    )
    consumed_qty = fields.Float(
        string='Consumed Qty',
        help='Total production consumption quantity for the selected period '
             '(non-zero for production_driven / combined planning types).',
    )
    resupply_qty = fields.Float(string='Resupply Qty',)
    resupply_return_qty = fields.Float(string='Resupply Return Qty',)
    scrap_qty = fields.Float(string='Scraped Qty',)
    config_id = fields.Many2one(comodel_name='advance.reorder.orderprocess.config',
                                string='Reorder configuration', help="Reorder configuration")
