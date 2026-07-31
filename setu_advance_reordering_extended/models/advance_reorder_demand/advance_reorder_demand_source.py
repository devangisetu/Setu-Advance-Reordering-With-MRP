# -*- coding: utf-8 -*-
from odoo import fields, models

class AdvanceReorderComponentDemandSource(models.Model):
    _name = 'advance.reorder.demand.source'
    _description = 'Component Demand Source'

    component_demand_line_id = fields.Many2one(
        'advance.reorder.component.demand.line',
    )

    to_be_produced_demand_line_id = fields.Many2one(
        'advance.reorder.to.be.produced.line',
    )

    source_product_id = fields.Many2one(
        'product.product',
        required=True,
    )

    source_qty = fields.Float(
        string='Required Qty',
    )