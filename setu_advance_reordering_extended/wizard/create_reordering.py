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
        if self.env.company.use_subcontracting_for_orderpoint:
            options.extend([
                ('resupply_history', 'Resupply History'),
                ('subcontract_history', 'Subcontracting Orders'),
            ])
        if self.env.company.use_scrap_for_orderpoint:
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
        if self.env.company.use_subcontracting_for_orderpoint:
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
    component_planning_warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Component Planning Warehouse"
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

    use_subcontracting_for_orderpoint = fields.Boolean(
        default=lambda self: self.env.company.use_subcontracting_for_orderpoint,
        string="Subcontracting Enabled"
    )

    use_scrap_for_orderpoint = fields.Boolean(
        default=lambda self: self.env.company.use_scrap_for_orderpoint,
        string="Scrap Enabled"
    )

    def perform_operation(self):
        self._filter_wizard_products()
        self = self.with_context(
            wizard_add_mo_in_lead_calc=self.add_mo_in_lead_calc,
            wizard_add_sc_in_lead_calc=self.add_sc_in_lead_calc,
            wizard_auto_create_components_orderpoint=self.auto_create_components_orderpoint,
            wizard_demand_planning_type=self.demand_planning_type,
            wizard_component_planning_warehouse_id=self.component_planning_warehouse_id.id,
        )
        return super().perform_operation()

    def prepare_orderpoint_domain(self):
        self._filter_wizard_products()
        return super().prepare_orderpoint_domain()

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
                orderpoints.with_context(
                    wizard_component_planning_warehouse_id=self.component_planning_warehouse_id.id
                )._auto_create_components_orderpoint()
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
                orderpoints.with_context(
                    wizard_component_planning_warehouse_id=self.component_planning_warehouse_id.id
                )._auto_create_components_orderpoint()
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
