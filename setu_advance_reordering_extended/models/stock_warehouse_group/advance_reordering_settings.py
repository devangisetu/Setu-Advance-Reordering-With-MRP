# -*- coding: utf-8 -*-
from odoo import fields, models


class AdvanceReorderingSettings(models.Model):
    _inherit = "advance.reordering.settings"

    use_subcontracting = fields.Boolean(
        string="Subcontracting",
        help="If enabled, subcontracting Bill of Materials will be included while calculating demand."
    )

    consider_scrap = fields.Selection(
        [
            ('component_loss', 'Component Loss'),
            ('production_rejection', 'Production Rejection'),
            ('both', 'Component Loss & Production Rejection'),
        ],
        string="Consider Scrap",
        config_parameter='your_module.consider_scrap',
        help="Select which type of scrap to consider in Real Demand calculation."
    )