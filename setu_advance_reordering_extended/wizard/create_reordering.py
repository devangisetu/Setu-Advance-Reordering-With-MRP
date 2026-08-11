# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import UserError

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
    specific_bom = fields.Boolean("Specific BOM", default=False)
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
    component_warehouse_ids = fields.One2many(
        "create.reordering.component.warehouse.mapping",
        "wizard_id",
        string="Component Planning Warehouses"
    )
    product_domain_ids = fields.Many2many(
        'product.product',
        compute='_compute_product_domain_ids',
        string='Product Domain Helper'
    )
    use_subcontracting_for_orderpoint = fields.Boolean(
        default=lambda self: self.env.company.use_subcontracting_for_orderpoint,
        string="Subcontracting Enabled"
    )
    use_scrap_for_orderpoint = fields.Boolean(
        default=lambda self: self.env.company.use_scrap_for_orderpoint,
        string="Scrap Enabled"
    )

    @api.depends('update_component_orderpoint')
    def _compute_product_domain_ids(self):
        Product = self.env['product.product']
        Bom = self.env['mrp.bom'].search([])
        bom_product_ids = Bom.mapped('product_id').ids
        bom_template_ids = Bom.mapped('product_tmpl_id').ids
        for wizard in self:
            if wizard.auto_create_components_orderpoint:
                wizard.product_domain_ids = Product.search([('id', 'in', bom_product_ids),('product_tmpl_id', 'in', bom_template_ids),])
            else:
                wizard.product_domain_ids = self.env['product.product'].search([])


    def perform_operation(self):
        comp_wh_by_company = {
            mapping.company_id.id: mapping.warehouse_id.id
            for mapping in self.component_warehouse_ids
        }
        context = {
            'wizard_add_mo_in_lead_calc': self.add_mo_in_lead_calc,
            'wizard_add_sc_in_lead_calc': self.add_sc_in_lead_calc,
            'wizard_auto_create_components_orderpoint': self.auto_create_components_orderpoint,
            'wizard_component_warehouse_by_company': comp_wh_by_company,
        }
        if self.orderpoint_operation == 'create_order_point':
            context['wizard_demand_planning_type'] = self.demand_planning_type
        self = self.with_context(**context)
        return super().perform_operation()

    def create_reorder_rule(self):
        location_type = self.location_selection_strategy
        products = self.product_ids and set(self.product_ids.ids) or {}
        inserted_orderpoints_ids = []
        if location_type == 'specific':
            specific_location_mapping_ids = self.specific_location_mapping_ids
            if not specific_location_mapping_ids:
                raise UserError("Please configure warehouses and its specific locations.")
            for mapping in specific_location_mapping_ids:
                op_ids = self.reordering_rule_exec(products, set([mapping.warehouse_id.id]), location_type,
                                                   specific_location=mapping.specific_location_id.id)
                if op_ids:
                    inserted_orderpoints_ids.extend(op_ids)
        else:
            warehouses = self.warehouse_ids
            if not warehouses:
                allowed_company_ids = self.env.context.get('allowed_company_ids', [])
                if allowed_company_ids:
                    warehouses = self.env['stock.warehouse'].sudo().search([]).filtered(
                        lambda x: x.company_id.id in allowed_company_ids)
            for warehouse in warehouses:
                if location_type == 'lot_stock':
                    specific_location = warehouse.lot_stock_id.id
                else:
                    specific_location = warehouse.wh_input_stock_loc_id.id
                op_ids = self.reordering_rule_exec(products, set([warehouse.id]), location_type,
                                                   specific_location=specific_location)
                if op_ids:
                    inserted_orderpoints_ids.extend(op_ids)
        if inserted_orderpoints_ids:
            orderpoints = self.env['stock.warehouse.orderpoint'].browse(inserted_orderpoints_ids)
            if orderpoints and not self.period_ids:
                orderpoints.update_product_purchase_history()
                orderpoints.update_product_sales_history()
                orderpoints.update_product_iwt_history()
                self._cr.commit()
            for record in orderpoints:
                vals = {
                    'consider_current_period_sales': self.consider_current_period_sales,
                    'add_purchase_in_lead_calc': self.add_purchase_in_lead_calc,
                    'add_iwt_in_lead_calc': self.add_iwt_in_lead_calc,
                    'buffer_days': self.buffer_days,
                    'auto_create_components_orderpoint': self.auto_create_components_orderpoint,
                    'demand_planning_type': self.demand_planning_type,
                    'add_mo_in_lead_calc': self.add_mo_in_lead_calc,
                    'add_sc_in_lead_calc': self.add_sc_in_lead_calc,
                }
                if self.average_sale_calculation_base:
                    vals.update({'average_sale_calculation_base': self.average_sale_calculation_base})
                if self.document_creation_option:
                    vals.update({'document_creation_option': self.document_creation_option})
                if self.vendor_selection_strategy:
                    vals.update({'vendor_selection_strategy': self.vendor_selection_strategy})
                if self.vendor_selection_strategy == 'specific_vendor' and self.partner_id:
                    vals.update({'partner_id': self.partner_id})
                if self.purchase_lead_calc_base_on == 'static_lead_time':
                    vals.update({'max_lead_time': self.static_maximum_lead_time,
                                 'avg_lead_time': self.static_average_lead_time})
                record.with_context(do_not_checked_rule=True).write(vals)

                record.with_context(already_calculated_history=True, do_not_checked_rule=True).recalculate_data()
            if orderpoints:
                self._cr.commit()
                orderpoints.update_order_point_data()
                comp_wh_by_company = {
                    mapping.company_id.id: mapping.warehouse_id.id
                    for mapping in self.component_warehouse_ids
                }
                orderpoints.with_context(
                    wizard_component_warehouse_by_company=comp_wh_by_company,
                    wizard_specific_bom=self.specific_bom,
                )._auto_create_components_orderpoint()
            return self.action_orderpoint(orderpoints.ids)
        return True

    def update_reorder_rule(self):
        products = self.product_ids and set(self.product_ids.ids) or {}
        warehouses = self.warehouse_ids and set(self.warehouse_ids.ids) or {}

        for period in self.period_ids:
            query = """
                    Select * from update_product_purchase_history('%s','%s','%s','%s','%s')
                """ % (
                products, warehouses, period.fpstartdate.strftime("%Y-%m-%d"),
                period.fpenddate.strftime("%Y-%m-%d"), self.env.user.id)
            self._cr.execute(query)

            query = """
                Select * from update_product_sales_history('{}','%s','{}','%s','%s','%s', '%s')
            """ % (
                products, warehouses, period.fpstartdate.strftime("%Y-%m-%d"),
                period.fpenddate.strftime("%Y-%m-%d"), self.env.user.id)
            self._cr.execute(query)

            query = """
                    Select * from update_product_iwt_history('%s','%s','%s','%s','%s')
                """ % (
                products, warehouses, period.fpstartdate.strftime("%Y-%m-%d"),
                period.fpenddate.strftime("%Y-%m-%d"), self.env.user.id)
            self._cr.execute(query)

        domain = self.prepare_orderpoint_domain()
        orderpoints = self.env['stock.warehouse.orderpoint'].search(domain)

        vals = {
            'consider_current_period_sales': self.consider_current_period_sales,
            'add_purchase_in_lead_calc': self.add_purchase_in_lead_calc,
            'add_iwt_in_lead_calc': self.add_iwt_in_lead_calc,
            'buffer_days': self.buffer_days,
            'add_mo_in_lead_calc': self.add_mo_in_lead_calc,
            'add_sc_in_lead_calc': self.add_sc_in_lead_calc,
        }

        if self.average_sale_calculation_base:
            vals.update({'average_sale_calculation_base': self.average_sale_calculation_base})
        if self.document_creation_option:
            vals.update({'document_creation_option': self.document_creation_option})
        if self.vendor_selection_strategy:
            vals.update({'vendor_selection_strategy': self.vendor_selection_strategy})
        if self.vendor_selection_strategy == 'specific_vendor' and self.partner_id:
            vals.update({'partner_id': self.partner_id})
        if self.purchase_lead_calc_base_on == 'static_lead_time':
            vals.update({'max_lead_time': self.static_maximum_lead_time,
                         'avg_lead_time': self.static_average_lead_time})

        orderpoints.write(vals)

        if orderpoints and not self.period_ids:
            orderpoints.update_product_purchase_history()
            orderpoints.update_product_sales_history()
            orderpoints.update_product_iwt_history()
            self._cr.commit()

        for orderpoint_id in orderpoints.ids:
            orderpoint = self.env['stock.warehouse.orderpoint'].browse(orderpoint_id)
            orderpoint.with_context(already_calculated_history=True, do_not_checked_rule=True).recalculate_data()

        if orderpoints:
            self._cr.commit()
            orderpoints.update_order_point_data()
            comp_wh_by_company = {
                mapping.company_id.id: mapping.warehouse_id.id
                for mapping in self.component_warehouse_ids
            }
            orderpoints.with_context(
                wizard_component_warehouse_by_company=comp_wh_by_company,
                wizard_specific_bom=self.specific_bom,
            )._auto_create_components_orderpoint()
        return self.action_orderpoint(orderpoints.ids)

    def update_production_history(self):
        domain = self.prepare_orderpoint_domain()
        orderpoints = self.env['stock.warehouse.orderpoint'].search(domain)
        if orderpoints:
            orderpoints.update_product_production_history()
        action = self.env.ref('setu_advance_reordering_extended.product_production_history_action').sudo().read()[0]
        return action

    def update_consumption_history(self):
        domain = self.prepare_orderpoint_domain()
        domain.append(('parent_orderpoint_ids', '=', False))
        orderpoints = self.env['stock.warehouse.orderpoint'].search(domain)
        if orderpoints:
            orderpoints.update_product_consumption_history()
        action = self.env.ref('setu_advance_reordering_extended.product_consumption_history_action').sudo().read()[0]
        return action

    def update_resupply_history(self):
        domain = self.prepare_orderpoint_domain()
        domain.append(('parent_orderpoint_ids', '=', False))
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
        domain.append(('parent_orderpoint_ids', '=', False))
        orderpoints = self.env['stock.warehouse.orderpoint'].search(domain)
        if orderpoints:
            orderpoints.update_product_scrap_history()
        action = self.env.ref('setu_advance_reordering_extended.product_scrap_history_action').sudo().read()[0]
        return action


