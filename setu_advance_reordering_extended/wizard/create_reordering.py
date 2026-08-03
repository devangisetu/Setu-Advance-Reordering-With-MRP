# -*- coding: utf-8 -*-
from odoo import fields, models, api

class CreateReordering(models.TransientModel):
    _inherit = 'create.reordering'

    def _get_operation_options(self):
        options = [
            ('orderpoint', 'Reordering Rule'),
            ('sales_history', 'Sales History'),
            ('purchase_history', 'Purchase Orders'),
            ('iwt_history', 'IWT Orders'),
            ('production_history', 'Production Orders'),
            ('consumption_history', 'Consumption History'),
        ]
        setting = self.env['advance.reordering.settings'].search([], limit=1)
        if setting and setting.subcontracting_enabled:
            options.extend([
                ('resupply_history', 'Resupply History'),
                ('subcontract_history', 'Subcontracting Orders'),
            ])
        if setting and setting.scrap_enabled:
            options.append(('scrap_history', 'Scrap History'))
        return options

    operation = fields.Selection(
        selection='_get_operation_options',
        default="orderpoint",
        string="Operations"
    )

    def _get_document_creation_options(self):
        options = [
            ('ict', 'Inter Company Transfer'),
            ('iwt', 'Inter Warehouse Transfer'),
            ('po', 'Purchase Order'),
            ('od_default', 'Odoo Default'),
            ('mrp', 'Production Order'),
        ]
        setting = self.env['advance.reordering.settings'].search([], limit=1)
        if setting and setting.subcontracting_enabled:
            options.append(('subcontracting', 'Subcontract Order'))
        return options

    document_creation_option = fields.Selection(
        selection='_get_document_creation_options',
        string="Reorder Fullfilment Strategy",
        default='od_default'
    )

    add_mo_in_lead_calc = fields.Boolean("Production", default=False)
    add_sc_in_lead_calc = fields.Boolean("Subcontracting", default=False)
    auto_create_components_orderpoint = fields.Boolean("Auto Create Components Orderpoint", default=False)
    average_sale_calculation_base = fields.Selection(string="Get Average Data From")
    consider_current_period_sales = fields.Boolean(
        string='Consider Current Period Data',
        help='Consider current period data in the calculation history'
    )
    demand_planning_type = fields.Selection([
        ('sales_driven', 'Sales Driven'),
        ('production_driven', 'Production Driven'),
        ('combined', 'Combined')
    ], string="Demand Planning Type", default="sales_driven")

    update_component_orderpoint = fields.Boolean(
        "Update Component Orderpoint",
        default=False,
        help="If enabled, product selection will only show products whose orderpoints have no parent product orderpoints."
    )
    product_domain_ids = fields.Many2many(
        'product.product',
        compute='_compute_product_domain_ids',
        string='Product Domain Helper'
    )

    @api.depends('update_component_orderpoint')
    def _compute_product_domain_ids(self):
        for wizard in self:
            if not wizard.update_component_orderpoint:
                ops_with_parents = self.env['stock.warehouse.orderpoint'].search([
                    ('parent_orderpoint_ids', '!=', False)
                ])
                excluded_product_ids = ops_with_parents.mapped('product_id').ids
                wizard.product_domain_ids = self.env['product.product'].search([
                    ('id', 'not in', excluded_product_ids)
                ])
            else:
                wizard.product_domain_ids = self.env['product.product'].search([])


    def _filter_wizard_products(self):
        self.product_ids = self.product_domain_ids


    def _default_subcontracting_enabled(self):
        setting = self.env['advance.reordering.settings'].search([], limit=1)
        return setting.subcontracting_enabled if setting else False

    subcontracting_enabled = fields.Boolean(
        default=_default_subcontracting_enabled,
        string="Subcontracting Enabled"
    )

    def _default_scrap_enabled(self):
        setting = self.env['advance.reordering.settings'].search([], limit=1)
        return setting.scrap_enabled if setting else False

    scrap_enabled = fields.Boolean(
        default=_default_scrap_enabled,
        string="Scrap Enabled"
    )

    def perform_operation(self):
        self._filter_wizard_products()
        self = self.with_context(
            wizard_add_mo_in_lead_calc=self.add_mo_in_lead_calc,
            wizard_add_sc_in_lead_calc=self.add_sc_in_lead_calc,
        )
        return super().perform_operation()

    def prepare_orderpoint_domain(self):
        self._filter_wizard_products()
        return super().prepare_orderpoint_domain()

    def _update_orderpoint_planning_type(self, orderpoints):
        if not orderpoints:
            return
        orderpoints.write({
            'auto_create_components_orderpoint': self.auto_create_components_orderpoint,
            'demand_planning_type': self.demand_planning_type,
        })
        orderpoints.update_product_sales_history()
        for op in orderpoints:
            op._calculate_lead_time()
            op.calculate_sales_average_max()
            op.onchange_average_sale_calculation_base()
            op.onchange_safety_stock()
            op.onchange_avg_sale_lead_time()
            op.onchange_safety_stock()
        orderpoints.update_order_point_data()
        orderpoints._auto_create_components_orderpoint()

    def create_reorder_rule(self):
        res = super().create_reorder_rule()
        if isinstance(res, dict) and 'domain' in res:
            domain = res.get('domain', [])
            orderpoint_ids = []
            for item in domain:
                if isinstance(item, tuple) and len(item) == 3 and item[0] == 'id' and item[1] == 'in':
                    orderpoint_ids = item[2]
                    break
            if orderpoint_ids:
                orderpoints = self.env['stock.warehouse.orderpoint'].browse(orderpoint_ids)
                self._update_orderpoint_planning_type(orderpoints)
        return res

    def update_reorder_rule(self):
        res = super().update_reorder_rule()
        if isinstance(res, dict) and 'domain' in res:
            domain = res.get('domain', [])
            orderpoint_ids = []
            for item in domain:
                if isinstance(item, tuple) and len(item) == 3 and item[0] == 'id' and item[1] == 'in':
                    orderpoint_ids = item[2]
                    break
            if orderpoint_ids:
                orderpoints = self.env['stock.warehouse.orderpoint'].browse(orderpoint_ids)
                self._update_orderpoint_planning_type(orderpoints)
        return res

    def update_production_history(self):
        domain = self.prepare_orderpoint_domain()
        orderpoints = self.env['stock.warehouse.orderpoint'].search(domain)
        if orderpoints:
            orderpoints.update_product_production_history()
        action = self.env.ref('setu_advance_reordering_extended.product_production_history_action').sudo().read()[0]
        return action

    def update_consumption_history(self):
        domain = self.prepare_orderpoint_domain()
        orderpoints = self.env['stock.warehouse.orderpoint'].search(domain)
        if orderpoints:
            orderpoints.update_product_consumption_history()
        action = self.env.ref('setu_advance_reordering_extended.product_consumption_history_action').sudo().read()[0]
        return action

    def update_resupply_history(self):
        domain = self.prepare_orderpoint_domain()
        orderpoints = self.env['stock.warehouse.orderpoint'].search(domain)
        if orderpoints:
            orderpoints.update_product_resupply_history()
        action = self.env.ref('setu_advance_reordering_extended.product_resupply_history_action').sudo().read()[0]
        return action

    def update_subcontract_history(self):
        domain = self.prepare_orderpoint_domain()
        orderpoints = self.env['stock.warehouse.orderpoint'].search(domain)
        if orderpoints:
            orderpoints.update_product_subcontract_history()
        action = self.env.ref('setu_advance_reordering_extended.product_subcontract_history_action').sudo().read()[0]
        return action

    def update_scrap_history(self):
        domain = self.prepare_orderpoint_domain()
        orderpoints = self.env['stock.warehouse.orderpoint'].search(domain)
        if orderpoints:
            orderpoints.update_product_scrap_history()
        action = self.env.ref('setu_advance_reordering_extended.product_scrap_history_action').sudo().read()[0]
        return action
