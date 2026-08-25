# -*- coding: utf-8 -*-
from odoo import fields, models, api


class AdvanceReorderOrderProcessSummary(models.Model):
    _inherit = 'advance.reorder.orderprocess.summary'

    ORDER_ACTION_SELECTION = [
        ('none', 'None'),
        ('purchase', 'Generate Purchase Orders'),
        ('production', 'Generate Production Orders'),
        ('subcontracting', 'Subcontracting'),
    ]

    order_action = fields.Selection(
        selection=ORDER_ACTION_SELECTION,
        string='Action',
        default='none',
        help='Defines which document type will be generated for this summary line. '
             'Auto-set from product tracking and routes on verify and can be changed before processing. '
             'Products without lot/serial tracking default to None.',
    )

    warehouse_group_id = fields.Many2one('stock.warehouse.group', string="Warehouse group")
    is_action_done = fields.Boolean(
        string='Action Done',
        copy=False,
        help='Set to True when the document for this summary action has been created.',
    )
