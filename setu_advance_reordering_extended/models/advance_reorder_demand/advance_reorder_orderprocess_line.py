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
    scrap_qty = fields.Float(string='Scraped Qty',)
    historical_scrap = fields.Float(string='Historical Scrap(%)', compute='_compute_historical_scrap', store=True)
    

    @api.depends('consumed_qty', 'scrap_qty')
    def _compute_historical_scrap(self):
        for line in self:
            total_qty = line.consumed_qty + line.scrap_qty
            line.historical_scrap = (
                ((line.scrap_qty / total_qty) * 100) if total_qty else 0.0
            )
