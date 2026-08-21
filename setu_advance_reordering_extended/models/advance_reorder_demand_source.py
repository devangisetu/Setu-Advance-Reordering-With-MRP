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
    productwise_component_demand_line_id = fields.Many2one(
        comodel_name='advance.reorder.productwise.component.demand.line',
        string='Product-Wise Component Line',
        ondelete='cascade',
    )
    productwise_to_be_produced_demand_line_id = fields.Many2one(
        comodel_name='advance.reorder.productwise.produced.demand.line',
        string='Product-Wise To Be Produced Line',
        ondelete='cascade',
    )

    source_product_id = fields.Many2one(
        comodel_name='product.product',
        string="Source Product",
        required=True,
    )

    source_qty = fields.Float(string='Source Qty',)
    required_qty = fields.Float(string="Required Qty")
    bom_id = fields.Many2one(comodel_name="mrp.bom", string="BOM")