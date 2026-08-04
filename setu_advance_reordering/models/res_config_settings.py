from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    reorder_rounding_method = fields.Selection(
        related='company_id.reorder_rounding_method',
        string="Rounding Method",
        store=True,
        readonly=False,
    )

    reorder_round_quantity = fields.Integer(
        related='company_id.reorder_round_quantity',
        string="Round Quantity",
        store=True,
        readonly=False,
    )

    purchase_lead_calc_base_on = fields.Selection(
        related='company_id.purchase_lead_calc_base_on',
        string="Purchase Lead Calculation Based On",
        store=True,
        readonly=False,
    )

    max_lead_days_calc_method = fields.Selection(
        related='company_id.max_lead_days_calc_method',
        string="Max Lead Days Calculation Method",
        store=True,
        readonly=False,
    )

    extra_lead_percentage = fields.Float(
        related='company_id.extra_lead_percentage',
        string="Extra Percentage For Max Lead Days",
        store=True,
        readonly=False,
    )

    max_sales_calc_method = fields.Selection(
        related='company_id.max_sales_calc_method',
        string="Max Sales Calculation Method",
        store=True,
        readonly=False,
    )

    extra_sales_percentage = fields.Float(
        related='company_id.extra_sales_percentage',
        string="Extra Percentage For Max Sales",
        store=True,
        readonly=False,
    )

    vendor_lead_days_method = fields.Selection(
        related='company_id.vendor_lead_days_method',
        string="Vendor Lead Days Calculation Method",
        store=True,
        readonly=False,
    )

    vendor_static_lead_days = fields.Integer(
        related='company_id.vendor_static_lead_days',
        string="Vendor Static Lead Days",
        store=True,
        readonly=False,
    )
