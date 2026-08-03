# -*- coding: utf-8 -*-
from odoo import fields, models

class AdvanceReorderComponentDemandSource(models.Model):
    _name = 'advance.reorder.demand.source'
    _description = 'Component Demand Source'

    component_demand_line_id = fields.Many2one(
        comodel_name='advance.reorder.component.demand.line',
        string="Component Line"
    )

    to_be_produced_demand_line_id = fields.Many2one(
        comodel_name='advance.reorder.to.be.produced.line',
        string="To Be Produced Line"
    )

    source_product_id = fields.Many2one(
        comodel_name='product.product',
        string="Source Product",
        required=True,
    )

    source_qty = fields.Float(string='Source Qty',)

    required_qty = fields.Float(string="Required Qty")

    bom_id = fields.Many2one(comodel_name="mrp.bom", string="BOM")