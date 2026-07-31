# -*- coding: utf-8 -*-
from odoo import fields, models, api

class AdvanceReorderingSettings(models.Model):
    _inherit = 'advance.reordering.settings'

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

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.subcontracting_enabled:
                record._enable_mrp_subcontracting()
        return records

    def write(self, vals):
        res = super().write(vals)
        if vals.get('subcontracting_enabled'):
            self._enable_mrp_subcontracting()
        return res

    def _enable_mrp_subcontracting(self):
        mrp_subcontracting = self.env['ir.module.module'].search([('name', '=', 'mrp_subcontracting')], limit=1)
        if mrp_subcontracting and mrp_subcontracting.state != 'installed':
            mrp_subcontracting.button_immediate_install()
