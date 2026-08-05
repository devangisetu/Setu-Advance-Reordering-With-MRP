# -*- coding: utf-8 -*-
from odoo import fields, models, api


class AdvanceReorderOrderProcessSummary(models.Model):
    _inherit = 'advance.reorder.orderprocess.summary'

    ORDER_ACTION_SELECTION = [
        ('purchase', 'Generate Purchase Orders'),
        ('production', 'Generate Production Orders'),
        ('ict', 'Generate ICT'),
        ('iwt', 'Generate IWT'),
        ('subcontracting', 'Subcontracting'),
    ]

    order_action = fields.Selection(
        selection=ORDER_ACTION_SELECTION,
        string='Action',
        default='purchase',
        help='Defines which document type will be generated for this summary line. '
             'Auto-set from product routes on verify and can be changed before processing.',
    )

    warehouse_group_id = fields.Many2one('stock.warehouse.group', string="Warehouse group")