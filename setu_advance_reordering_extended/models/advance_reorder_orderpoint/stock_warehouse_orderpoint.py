# -*- coding: utf-8 -*-
from odoo import fields, models, api, _, registry, SUPERUSER_ID
from odoo.exceptions import ValidationError
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from collections import defaultdict
from statistics import mean
import logging

_logger = logging.getLogger(__name__)


class StockWarehouseOrderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"

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
        string="Create",
        change_default=True,
        default='od_default',
    )
    add_mo_in_lead_calc = fields.Boolean("Production", default=False)
    add_sc_in_lead_calc = fields.Boolean("Subcontracting", default=False)
    demand_planning_type = fields.Selection([
        ('sales_driven', 'Sales Driven'),
        ('production_driven', 'Production Driven'),
        ('combined', 'Combined')
    ], string="Demand Planning Type", default="sales_driven")
    auto_create_components_orderpoint = fields.Boolean(
        string="Auto Create Components Orderpoint",
        default=False
    )
    warehouse_changed = fields.Boolean(string="Warehouse Changed", default=False)
    average_sale_calculation_base = fields.Selection(string="Get Average Data From")
    max_daily_sale_qty = fields.Float("Maximum Daily Demand")

    use_subcontracting_for_orderpoint = fields.Boolean(
        compute="_compute_subcontracting_enabled",
        string="Subcontracting Enabled in Settings"
    )
    use_scrap_for_orderpoint = fields.Boolean(
        compute="_compute_scrap_enabled",
        string="Scrap Enabled in Settings"
    )
    product_production_history_ids = fields.One2many(
        "product.production.history", "orderpoint_id", string="Production History"
    )
    product_consumption_history_ids = fields.One2many(
        "product.consumption.history", "orderpoint_id", string="Consumption History"
    )
    product_subcontract_history_ids = fields.One2many(
        "product.subcontract.history", "orderpoint_id", string="Subcontract History"
    )
    product_resupply_history_ids = fields.One2many(
        "product.resupply.history", "orderpoint_id", string="Resupply History"
    )
    product_scrap_history_ids = fields.One2many(
        "product.scrap.history", "orderpoint_id", string="Scrap History"
    )
    parent_orderpoint_ids = fields.Many2many(
        'stock.warehouse.orderpoint',
        'stock_warehouse_orderpoint_parent_rel',
        'child_orderpoint_id',
        'parent_orderpoint_id',
        string="Source Product Orderpoints",
        domain="[('id', 'in', parent_orderpoint_domain_ids)]"
    )
    parent_orderpoint_domain_ids = fields.Many2many(
        'stock.warehouse.orderpoint',
        compute="_compute_parent_orderpoint_domain_ids",
        string="Parent Orderpoints Domain Helper"
    )

    parent_orderpoint_count = fields.Integer(
        compute="_compute_parent_orderpoint_count",
        string="Source Orderpoint Count"
    )

    reorder_bom_id = fields.Many2one(
        'mrp.bom',
        compute='_compute_reorder_bom_id',
        string='Reorder BOM',
        readonly=True
    )

    def _compute_reorder_bom_id(self):
        products = self.mapped('product_id')
        companies = self.mapped('company_id')
        planning_records = self.env['product.planning'].search([
            ('product_id', 'in', products.ids),
            ('company_id', 'in', companies.ids)
        ])
        planning_map = {(p.product_id.id, p.company_id.id): p.reorder_bom_id for p in planning_records}
        for op in self:
            bom = planning_map.get((op.product_id.id, op.company_id.id), False)
            op.reorder_bom_id = bom or op.product_id.reorder_bom_id

    consider_current_period_sales = fields.Boolean(
        string='Consider Current Period Data',
        help='Consider current period data in the calculation history'
    )
    ads_qty = fields.Float(string="Average Daily Demand")

    @api.depends('product_id')
    def _compute_parent_orderpoint_domain_ids(self):
        for rec in self:
            if not rec.product_id:
                rec.parent_orderpoint_domain_ids = self.env['stock.warehouse.orderpoint']
                continue
            bom_lines = self.env['mrp.bom.line'].search([('product_id', '=', rec.product_id.id)])
            parent_templates = bom_lines.mapped('bom_id.product_tmpl_id')
            parent_products = bom_lines.mapped('bom_id.product_id') | parent_templates.mapped('product_variant_ids')
            domain = [('product_id', 'in', parent_products.ids)]
            if rec.id:
                domain.append(('id', '!=', rec.id))
            rec.parent_orderpoint_domain_ids = self.env['stock.warehouse.orderpoint'].search(domain)

    def _compute_display_name(self):
        for rec in self:
            if rec.product_id and rec.warehouse_id:
                rec.display_name = f"{rec.product_id.display_name} - {rec.warehouse_id.name}"
            else:
                super(StockWarehouseOrderpoint, rec)._compute_display_name()

    @api.depends('parent_orderpoint_ids')
    def _compute_parent_orderpoint_count(self):
        for rec in self:
            rec.parent_orderpoint_count = len(rec.parent_orderpoint_ids)

    def action_view_parent_orderpoints(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("stock.action_orderpoint")
        action['domain'] = [('id', 'in', self.parent_orderpoint_ids.ids)]
        action['context'] = {'create': False}
        return action

    def _compute_subcontracting_enabled(self):
        enabled = self.env.company.use_subcontracting_for_orderpoint or False
        for op in self:
            op.use_subcontracting_for_orderpoint = enabled

    def _compute_scrap_enabled(self):
        enabled = self.env.company.use_scrap_for_orderpoint or False
        for op in self:
            op.use_scrap_for_orderpoint = enabled

    def write(self, vals):
        if 'wizard_add_mo_in_lead_calc' in self.env.context:
            vals['add_mo_in_lead_calc'] = self.env.context.get('wizard_add_mo_in_lead_calc')
        if 'wizard_add_sc_in_lead_calc' in self.env.context:
            vals['add_sc_in_lead_calc'] = self.env.context.get('wizard_add_sc_in_lead_calc')
        if 'wizard_auto_create_components_orderpoint' in self.env.context:
            vals['auto_create_components_orderpoint'] = self.env.context.get('wizard_auto_create_components_orderpoint')
        if 'wizard_demand_planning_type' in self.env.context:
            vals['demand_planning_type'] = self.env.context.get('wizard_demand_planning_type')
        if 'warehouse_id' in vals:
            changed_records = self.env['stock.warehouse.orderpoint']
            for record in self:
                old_warehouse = record.warehouse_id
                new_warehouse_id = vals['warehouse_id']
                if old_warehouse.id != new_warehouse_id:
                    new_warehouse = self.env['stock.warehouse'].browse(new_warehouse_id)
                    user_name = self.env.user.name
                    body = _("Warehouse changed from %s to %s by %s.") % (
                        old_warehouse.display_name or _("None"),
                        new_warehouse.display_name,
                        user_name
                    )
                    record.message_post(body=body)
                    changed_records |= record
            res = super().write(vals)
            if changed_records:
                super(StockWarehouseOrderpoint, changed_records).write({'warehouse_changed': True})
            return res

        return super().write(vals)

    def get_sales_data(self, start_date, end_date):
        number_of_sales_days = (end_date - start_date).days + 1
        if number_of_sales_days <= 0:
            number_of_sales_days = 1
        sales_qty_sum = 0.0
        max_daily_qtys = []
        # 1. Sales history (if sales_driven or combined)
        if self.demand_planning_type in ('sales_driven', 'combined'):
            sales_data = self.product_sales_history_ids.filtered(
                lambda x: start_date <= x.start_date <= end_date)
            sales_qty_sum += sum(sales_data.mapped('sales_qty'))
            max_daily_qtys += sales_data.mapped('max_daily_sale_qty')
        # 2. Consumption / Resupply history (if production_driven or combined)
        if self.demand_planning_type in ('production_driven', 'combined'):
            consumption_data = self.product_consumption_history_ids.filtered(
                lambda x: start_date <= x.start_date <= end_date)
            resupply_data = self.product_resupply_history_ids.filtered(
                lambda x: start_date <= x.start_date <= end_date)
            if self.use_scrap_for_orderpoint:
                scrap_data = self.product_scrap_history_ids.filtered(
                    lambda x: start_date <= x.start_date <= end_date)
                sales_qty_sum += sum(scrap_data.mapped('scrap_qty'))
                max_daily_qtys += scrap_data.mapped('maximum_daily_scrap')
            sales_qty_sum += sum(consumption_data.mapped('consumed_qty'))
            sales_qty_sum += sum(resupply_data.mapped('resupply_qty'))
            max_daily_qtys += consumption_data.mapped('maximum_daily_consumption')
            max_daily_qtys += resupply_data.mapped('maximum_daily_resupply')
        avg_sale = sales_qty_sum / number_of_sales_days if sales_qty_sum > 0 else 0.0
        calc_method = self.company_id.max_sales_calc_method
        if calc_method == 'avg_extra_percentage':
            extra_percentage = float(self.company_id.extra_sales_percentage or 0.0) + 1.0
            max_sale = avg_sale * extra_percentage
        else:
            max_sale = max(max_daily_qtys) if max_daily_qtys else 0.0
        return avg_sale, max_sale

    def update_product_production_history(self):
        products = self.mapped('product_id')
        warehouses = self.mapped('warehouse_id')
        if not products or not warehouses:
            return True
        today = date.today()
        start_date = today - relativedelta(days=365)
        query = """
            SELECT update_product_production_history(%s, %s, %s, %s)
        """
        self._cr.execute(query, [self.ids, start_date, today, self.env.user.id])
        return True

    def update_product_subcontract_history(self):
        products = self.mapped('product_id')
        warehouses = self.mapped('warehouse_id')
        if not products or not warehouses:
            return True
        today = date.today()
        start_date = today - relativedelta(days=365)
        query = """
            SELECT update_product_subcontract_history(%s, %s, %s, %s)
        """
        self._cr.execute(query, [self.ids, start_date, today, self.env.user.id])
        return True

    def update_product_resupply_history(self):
        orderpoints = self.filtered(lambda op: not op.parent_orderpoint_ids)
        if not orderpoints:
            return True
        products = orderpoints.mapped('product_id')
        warehouses = orderpoints.mapped('warehouse_id')
        if not products or not warehouses:
            return True
        today = date.today()
        start_date_limit = today - relativedelta(days=365)
        period_ids = self.env['reorder.fiscalperiod'].search([
            ('fpstartdate', '>=', start_date_limit),
            ('fpstartdate', '<=', today)
        ])
        if not period_ids:
            return True
        min_start = min(period_ids.mapped('fpstartdate'))
        max_end = max(period_ids.mapped('fpenddate'))
        query = """
            SELECT update_product_resupply_history(%s, %s, %s, %s)
        """
        self._cr.execute(query, [orderpoints.ids, min_start, max_end, self.env.user.id])
        return True

    def update_product_consumption_history(self):
        orderpoints = self.filtered(lambda op: not op.parent_orderpoint_ids)
        if not orderpoints:
            return True
        products = orderpoints.mapped('product_id')
        warehouses = orderpoints.mapped('warehouse_id')
        if not products or not warehouses:
            return True
        today = date.today()
        start_date_limit = today - relativedelta(days=365)
        period_ids = self.env['reorder.fiscalperiod'].search([
            ('fpstartdate', '>=', start_date_limit),
            ('fpstartdate', '<=', today)
        ])
        if not period_ids:
            return True
        min_start = min(period_ids.mapped('fpstartdate'))
        max_end = max(period_ids.mapped('fpenddate'))
        query = """
            SELECT update_product_consumption_history(%s, %s, %s, %s)
        """
        self._cr.execute(query, [orderpoints.ids, min_start, max_end, self.env.user.id])
        return True

    def update_product_scrap_history(self):
        orderpoints = self.filtered(lambda op: not op.parent_orderpoint_ids)
        if not orderpoints:
            return True
        products = orderpoints.mapped('product_id')
        warehouses = orderpoints.mapped('warehouse_id')
        if not products or not warehouses:
            return True
        today = date.today()
        start_date_limit = today - relativedelta(days=365)
        period_ids = self.env['reorder.fiscalperiod'].search([
            ('fpstartdate', '>=', start_date_limit),
            ('fpstartdate', '<=', today)
        ])
        if not period_ids:
            return True
        min_start = min(period_ids.mapped('fpstartdate'))
        max_end = max(period_ids.mapped('fpenddate'))
        query = """
            SELECT update_product_scrap_history(%s, %s, %s, %s)
        """
        self._cr.execute(query, [orderpoints.ids, min_start, max_end, self.env.user.id])
        return True

    def update_product_sales_history(self):
        orderpoints = self.filtered(lambda op: not op.parent_orderpoint_ids)
        if not orderpoints:
            return True
        return super(StockWarehouseOrderpoint, orderpoints).update_product_sales_history()

    def _calculate_lead_time(self):
        purchase_base = self.company_id.purchase_lead_calc_base_on or 'vendor_lead_time'
        subcontract_base = self.company_id.subcontract_lead_calc_base_on or 'vendor_lead_time'
        purchase_calc_method = self.company_id.max_lead_days_calc_method or 'max_lead_days'
        purchase_extra_percentage = float(self.company_id.extra_lead_percentage or 0.0) + 1.0 or 1.0
        subcontract_calc_method = self.company_id.subcontract_max_lead_days_calc_method or 'max_lead_days'
        subcontract_extra_percentage = float(self.company_id.subcontract_extra_lead_percentage or 0.0) + 1.0 or 1.0
        for orderpoint in self:
            source_averages = []
            max_lead_times = []
            # Purchase
            if orderpoint.add_purchase_in_lead_calc and purchase_base != 'static_lead_time':
                if purchase_base == 'vendor_lead_time':
                    purchase_delays = orderpoint.product_id.seller_ids.mapped('delay')
                else:
                    purchase_delays = orderpoint.product_purchase_history_ids.mapped('lead_time')
                if purchase_delays:
                    purchase_avg = mean(purchase_delays)
                    source_averages.append(purchase_avg)
                    if purchase_calc_method == 'avg_extra_percentage':
                        max_lead_times.append(round(purchase_avg * purchase_extra_percentage) or 1)
                    else:
                        max_lead_times.append(max(purchase_delays))
            # IWT
            if orderpoint.add_iwt_in_lead_calc:
                iwt_delays = orderpoint.product_warehouse_movement_history_ids.mapped('lead_time')
                if iwt_delays:
                    iwt_avg = mean(iwt_delays)
                    source_averages.append(iwt_avg)
                    max_lead_times.append(max(iwt_delays))
            # Production
            if orderpoint.add_mo_in_lead_calc:
                mo_delays = orderpoint.product_production_history_ids.mapped('lead_time')
                if mo_delays:
                    mo_avg = mean(mo_delays)
                    source_averages.append(mo_avg)
                    max_lead_times.append(max(mo_delays))
            # Subcontracting
            if orderpoint.add_sc_in_lead_calc and subcontract_base != 'static_lead_time':
                if subcontract_base == 'vendor_lead_time':
                    subcontractors = orderpoint.product_id.bom_ids.mapped('subcontractor_ids')
                    sellers = orderpoint.product_id.seller_ids
                    if subcontractors:
                        sellers = sellers.filtered(lambda s: s.partner_id in subcontractors)
                    subcontract_delays = sellers.mapped('delay')
                else:
                    subcontract_delays = orderpoint.product_subcontract_history_ids.mapped('lead_time')
                if subcontract_delays:
                    subcontract_avg = mean(subcontract_delays)
                    source_averages.append(subcontract_avg)
                    if subcontract_calc_method == 'avg_extra_percentage':
                        max_lead_times.append(round(subcontract_avg * subcontract_extra_percentage) or 1)
                    else:
                        max_lead_times.append(max(subcontract_delays))
            if source_averages:
                avg_lead_time = round(mean(source_averages)) or 1
                max_lead_time = max(round(max(max_lead_times)) if max_lead_times else 1, avg_lead_time)
                orderpoint.write({
                    'avg_lead_time': avg_lead_time,
                    'max_lead_time': max_lead_time
                })
        return True

    def _get_reorder_boms(self):
        self.ensure_one()
        if self.env.context.get('wizard_specific_bom') and self.reorder_bom_id:
            return self.reorder_bom_id
        return self.env['mrp.bom'].search([
            '|',
            ('company_id', '=', self.company_id.id),
            ('company_id', '=', False),
            '|',
            ('product_id', '=', self.product_id.id),
            '&',
            ('product_tmpl_id', '=', self.product_tmpl_id.id),
            ('product_id', '=', False),
        ])

    def _is_mto_product(self, product):
        mto_route = self.env.ref('stock.route_warehouse0_mto', raise_if_not_found=False)
        if mto_route:
            product_routes = product.route_ids | product.product_tmpl_id.route_ids
            return mto_route.id in product_routes.ids
        return False

    def _has_bom(self, product):
        boms = self.env['mrp.bom'].search([
            '|',
            ('product_id', '=', product.id),
            '&',
            ('product_tmpl_id', '=', product.product_tmpl_id.id),
            ('product_id', '=', False)
        ], limit=1)
        return bool(boms)

    def _find_or_create_component_orderpoint(self, product, parent_op, target_wh_id, target_loc_id):
        if parent_op.document_creation_option == 'od_default':
            doc_option = 'od_default'
        else:
            doc_option = 'po' if not self._has_bom(product) else parent_op.document_creation_option
        existing_op = self.env['stock.warehouse.orderpoint'].search([
            ('product_id', '=', product.id),
            ('warehouse_id', '=', target_wh_id),
            ('company_id', '=', parent_op.company_id.id),
        ], limit=1)
        if existing_op:
            write_vals = {}
            if parent_op.auto_create_components_orderpoint and not existing_op.auto_create_components_orderpoint:
                write_vals['auto_create_components_orderpoint'] = True
            if existing_op.document_creation_option != doc_option:
                write_vals['document_creation_option'] = doc_option
            if write_vals:
                existing_op.write(write_vals)
            if parent_op.id not in existing_op.parent_orderpoint_ids.ids:
                existing_op.write({'parent_orderpoint_ids': [(4, parent_op.id)]})
            return existing_op
        create_vals = {
            'product_id': product.id,
            'warehouse_id': target_wh_id,
            'location_id': target_loc_id,
            'company_id': parent_op.company_id.id,
            'route_id': parent_op.route_id.id if (parent_op.route_id and target_wh_id == parent_op.warehouse_id.id) else False,
            'document_creation_option': doc_option,
            'consider_current_period_sales': parent_op.consider_current_period_sales,
            'buffer_days': parent_op.buffer_days,
            'average_sale_calculation_base': parent_op.average_sale_calculation_base,
            'add_purchase_in_lead_calc': parent_op.add_purchase_in_lead_calc,
            'add_iwt_in_lead_calc': parent_op.add_iwt_in_lead_calc,
            'add_mo_in_lead_calc': parent_op.add_mo_in_lead_calc,
            'add_sc_in_lead_calc': parent_op.add_sc_in_lead_calc,
            'demand_planning_type': parent_op.demand_planning_type,
            'qty_multiple': parent_op.qty_multiple,
            'visibility_days': parent_op.visibility_days,
            'trigger': 'auto',
            'auto_create_components_orderpoint': parent_op.auto_create_components_orderpoint,
            'parent_orderpoint_ids': [(4, parent_op.id)],
        }
        return self.env['stock.warehouse.orderpoint'].create(create_vals)

    def _auto_create_components_orderpoint(self):
        if self._context.get('prevent_component_recursion'):
            return
        to_process = list(self)
        processed = set()
        all_affected_orderpoints = self.env['stock.warehouse.orderpoint']
        wizard_wh_by_company = self.env.context.get('wizard_component_warehouse_by_company') or {}
        while to_process:
            op = to_process.pop(0)
            key = (op.product_id.id, op.warehouse_id.id)
            if not op.auto_create_components_orderpoint or not op.product_id or key in processed:
                continue
            processed.add(key)
            boms = op._get_reorder_boms()
            if not boms:
                continue
            for bom in boms:
                for line in bom.bom_line_ids:
                    product = line.product_id
                    if not product or not product.active or product.type == 'combo' or not product.is_storable:
                        continue
                    if self._is_mto_product(product):
                        continue
                    if self._has_bom(product):
                        comp_wh_id = op.warehouse_id.id
                        comp_loc_id = op.location_id.id
                    else:
                        target_wh_id = wizard_wh_by_company.get(op.company_id.id)
                        if target_wh_id:
                            target_wh = self.env['stock.warehouse'].browse(target_wh_id)
                            comp_wh_id = target_wh.id
                            comp_loc_id = target_wh.lot_stock_id.id
                        else:
                            comp_wh_id = op.warehouse_id.id
                            comp_loc_id = op.location_id.id
                    comp_op = self._find_or_create_component_orderpoint(product, op, comp_wh_id, comp_loc_id)
                    all_affected_orderpoints |= comp_op
                    if (comp_op.product_id.id, comp_op.warehouse_id.id) not in processed:
                        to_process.append(comp_op)
        if all_affected_orderpoints:
            for op in all_affected_orderpoints:
                op.with_context(prevent_component_recursion=True).recalculate_data()
            all_affected_orderpoints.update_order_point_data()

    def update_order_point_data(self):
        self.env.flush_all()
        return super().update_order_point_data()

    def recalculate_data(self):
        """
              added by: Aastha Vora | On: Oct - 16 - 2024 | Task: 998
              use: Recalculate order point data.
        """
        parent_ops = self.parent_orderpoint_ids
        if parent_ops:
            self.reset_all_data()
            min_qty = 0.0
            max_qty = 0.0
            for parent_op in parent_ops:
                parent_product = parent_op.product_id
                parent_bom = parent_op.reorder_bom_id
                if not parent_bom and parent_product.bom_ids:
                    parent_bom = parent_product.bom_ids[0]
                if parent_bom:
                    bom_line = parent_bom.bom_line_ids.filtered(lambda x: x.product_id == self.product_id)
                    if bom_line:
                        bom_qty = parent_bom.product_qty or 1.0
                        ratio = bom_line.product_qty / bom_qty
                        min_qty += (parent_op.suggested_min_qty or 0.0) * ratio
                        max_qty += (parent_op.suggested_max_qty or 0.0) * ratio
            
            history_context = self._context.get('already_calculated_history', False)
            if not history_context:
                self.update_product_purchase_history()
                self.update_product_iwt_history()
                self.update_product_production_history()
                self.update_product_subcontract_history()
            self.env.invalidate_all()
            self._calculate_lead_time()

            self.write({
                'suggested_min_qty': round(min_qty, 2),
                'suggested_max_qty': round(max_qty, 2),
                'product_min_qty': round(min_qty, 2),
                'product_max_qty': round(max_qty, 2),
                'suggested_safety_stock': 0.0,
                'safety_stock': 0.0,
                'warehouse_changed': False
            })
            return True

        history_context = self._context.get('already_calculated_history', False)
        self.reset_all_data()
        if not history_context:
            if self.demand_planning_type in ('sales_driven', 'combined'):
                self.update_product_sales_history()
            self.update_product_purchase_history()
            self.update_product_iwt_history()
        if self.demand_planning_type in ('production_driven', 'combined'):
            self.update_product_consumption_history()
            self.update_product_resupply_history()
        self.update_product_production_history()
        self.update_product_subcontract_history()
        if self.use_scrap_for_orderpoint:
            self.update_product_scrap_history()
        self.env.invalidate_all()
        self._calculate_lead_time()
        self.calculate_sales_average_max()
        self.onchange_average_sale_calculation_base()
        self.onchange_safety_stock()
        self.onchange_avg_sale_lead_time()
        self.onchange_safety_stock()
        self.write({'warehouse_changed': False})

