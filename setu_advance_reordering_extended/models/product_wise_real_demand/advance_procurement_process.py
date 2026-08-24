# -*- coding: utf-8 -*-
from odoo import fields, models


class AdvanceProcurementProcess(models.Model):
    _inherit = 'advance.procurement.process'

    product_wise_reorder_id = fields.Many2one(
        'advance.reorder.product.wise.process',
        string='Product-Wise Reorder',
        index=True,
    )
