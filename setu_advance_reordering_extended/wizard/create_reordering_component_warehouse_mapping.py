# -*- coding: utf-8 -*-
from odoo import fields, models

class CreateReorderingComponentWarehouseMapping(models.TransientModel):
    _name = 'create.reordering.component.warehouse.mapping'
    _description = 'Wizard Component Planning Warehouse Mapping'

    wizard_id = fields.Many2one(
        'create.reordering',
        string='Wizard',
        ondelete='cascade',
        required=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
    )
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Component Warehouse',
        required=True,
        domain="[('company_id', '=', company_id)]",
    )
