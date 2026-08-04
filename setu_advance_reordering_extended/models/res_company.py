# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    use_subcontracting_for_demand = fields.Boolean(
        string="Subcontracting",
        help="Include subcontracting Bill of Materials in demand calculation."
    )

    use_scrap_for_demand = fields.Boolean(
        string="Scrap",
        help="If enabled, scrap  consider in Real Demand calculation."
    )

    subcontracting_enabled = fields.Boolean(
        string="Subcontracting",
        default=False,
        help="If enabled, subcontract history, resupply history tabs and lead time configuration for subcontracting will be visible on the reordering rules form view."
    )
    scrap_enabled = fields.Boolean(
        string="Scrap",
        default=False,
        help="If enabled, scrap history tab will be visible on the reordering rules form view."
    )

    subcontract_lead_calc_base_on = fields.Selection([
        ('vendor_lead_time', 'Vendor Lead Time'),
        ('real_time', 'Real Time'),
        ('static_lead_time', 'Static Lead Time')
    ], string="Subcontract lead calculation base on", default="vendor_lead_time")

    subcontract_max_lead_days_calc_method = fields.Selection([
        ('max_lead_days', 'Actual Maximum Lead Time'),
        ('avg_extra_percentage', 'Average + Extra Percentage')
    ], string='Subcontract max lead days calculation Method', default="max_lead_days")

    subcontract_extra_lead_percentage = fields.Float('Subcontract Extra Percentage For Max Lead Days', default=0.0)