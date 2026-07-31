# -*- coding: utf-8 -*-
from odoo import fields, models


class AdvanceReorderingSettings(models.Model):
    _inherit = "advance.reordering.settings"

    use_subcontracting = fields.Boolean(
        string="Subcontracting",
        help="If enabled, subcontracting Bill of Materials will be included while calculating demand."
    )

    consider_component_loss = fields.Boolean(
        string="Consider Component Loss",
        config_parameter='your_module.consider_component_loss',
        help="Consider material loss during manufacturing in Real Demand calculation."
    )

    consider_production_rejection = fields.Boolean(
        string="Consider Production Rejection",
        config_parameter='your_module.consider_production_rejection',
        help="Consider rejected Finished/Semi-finished products in Real Demand calculation."
    )

    consider_both = fields.Boolean(
        string="Consider Both",
        config_parameter='your_module.consider_both',
        help="Consider both Component Loss and Production Rejection in Real Demand calculation."
    )