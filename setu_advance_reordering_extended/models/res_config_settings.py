# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    use_subcontracting_for_demand = fields.Boolean(
        related='company_id.use_subcontracting_for_demand',
        string="Subcontracting",
        help="Include subcontracting Bill of Materials in demand calculation.",
        store=True,
        readonly=False,
    )

    use_scrap_for_demand = fields.Boolean(
        related='company_id.use_scrap_for_demand',
        string="Scrap",
        help="If enabled, scrap consider in Real Demand calculation.",
        store=True,
        readonly=False,
    )

    use_subcontracting_for_orderpoint = fields.Boolean(
        related='company_id.use_subcontracting_for_orderpoint',
        string="Subcontracting",
        help="Include subcontracting in lead time calculation.",
        store=True,
        readonly=False,
    )

    use_scrap_for_orderpoint = fields.Boolean(
        related='company_id.use_scrap_for_orderpoint',
        string="Scrap",
        help="Include scrap in daily demand calculation.",
        store=True,
        readonly=False,
    )

    subcontract_lead_calc_base_on = fields.Selection(
        related='company_id.subcontract_lead_calc_base_on',
        string="Subcontract lead calculation base on",
        store=True,
        readonly=False,
    )

    subcontract_max_lead_days_calc_method = fields.Selection(
        related='company_id.subcontract_max_lead_days_calc_method',
        string="Subcontract max lead days calculation Method",
        store=True,
        readonly=False,
    )

    subcontract_extra_lead_percentage = fields.Float(
        related='company_id.subcontract_extra_lead_percentage',
        string="Subcontract Extra Percentage For Max Lead Days",
        store=True,
        readonly=False,
    )