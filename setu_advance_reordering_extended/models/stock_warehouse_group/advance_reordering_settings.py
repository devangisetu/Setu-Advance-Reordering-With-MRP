# -*- coding: utf-8 -*-
from odoo import fields, models


class AdvanceReorderingSettings(models.Model):
    _inherit = "advance.reordering.settings"

    use_subcontracting = fields.Boolean(
        string="Subcontracting",
        help="If enabled, subcontracting Bill of Materials will be included while calculating demand."
    )

    use_scrap = fields.Boolean(
        string="Scrap",
        help="If enabled, scrap  consider in Real Demand calculation."
    )
