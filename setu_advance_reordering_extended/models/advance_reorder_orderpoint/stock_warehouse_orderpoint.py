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
        setting = self.env['advance.reordering.settings'].search([], limit=1)
        if setting and setting.subcontracting_enabled:
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

    subcontracting_enabled = fields.Boolean(
        compute="_compute_subcontracting_enabled",
        string="Subcontracting Enabled in Settings"
    )
    scrap_enabled = fields.Boolean(
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

    consider_current_period_sales = fields.Boolean(
        string='Consider Current Period Data',
        help='Consider current period data in the calculation history'
    )
    ads_qty = fields.Float(string="Average Daily Demand")

    def _compute_subcontracting_enabled(self):
        setting = self.env['advance.reordering.settings'].search([], limit=1)
        enabled = setting.subcontracting_enabled if setting else False
        for op in self:
            op.subcontracting_enabled = enabled

    def _compute_scrap_enabled(self):
        setting = self.env['advance.reordering.settings'].search([], limit=1)
        enabled = setting.scrap_enabled if setting else False
        for op in self:
            op.scrap_enabled = enabled

    def write(self, vals):
        if 'wizard_add_mo_in_lead_calc' in self.env.context:
            vals['add_mo_in_lead_calc'] = self.env.context.get('wizard_add_mo_in_lead_calc')
        if 'wizard_add_sc_in_lead_calc' in self.env.context:
            vals['add_sc_in_lead_calc'] = self.env.context.get('wizard_add_sc_in_lead_calc')

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
            sales_qty_sum += sum(consumption_data.mapped('consumed_qty'))
            sales_qty_sum += sum(resupply_data.mapped('resupply_qty'))
            max_daily_qtys += consumption_data.mapped('maximum_daily_consumption')
            max_daily_qtys += resupply_data.mapped('maximum_daily_resupply')
        avg_sale = sales_qty_sum / number_of_sales_days if sales_qty_sum > 0 else 0.0
        calc_method = self.env['advance.reordering.settings'].search([]).max_sales_calc_method
        if calc_method == 'avg_extra_percentage':
            extra_percentage = float(self.env['advance.reordering.settings'].search([]).extra_sales_percentage or 0.0) + 1.0
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
        products = self.mapped('product_id')
        warehouses = self.mapped('warehouse_id')
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
        self._cr.execute(query, [self.ids, min_start, max_end, self.env.user.id])
        return True

    def update_product_consumption_history(self):
        products = self.mapped('product_id')
        warehouses = self.mapped('warehouse_id')
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
        self._cr.execute(query, [self.ids, min_start, max_end, self.env.user.id])
        return True

    def update_product_scrap_history(self):
        products = self.mapped('product_id')
        warehouses = self.mapped('warehouse_id')
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
        self._cr.execute(query, [self.ids, min_start, max_end, self.env.user.id])
        return True

    def _calculate_lead_time(self):
        settings = self.env['advance.reordering.settings'].search([], limit=1)
        purchase_base = settings.purchase_lead_calc_base_on if settings else 'vendor_lead_time'
        subcontract_base = settings.subcontract_lead_calc_base_on if settings else 'vendor_lead_time'
        purchase_calc_method = settings.max_lead_days_calc_method if settings else 'max_lead_days'
        purchase_extra_percentage = float(settings.extra_lead_percentage or 0.0) + 1.0 if settings else 1.0
        subcontract_calc_method = settings.subcontract_max_lead_days_calc_method if settings else 'max_lead_days'
        subcontract_extra_percentage = float(settings.subcontract_extra_lead_percentage or 0.0) + 1.0 if settings else 1.0
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
                max_lead_time = round(max(max_lead_times)) if max_lead_times else 1
                orderpoint.write({
                    'avg_lead_time': avg_lead_time,
                    'max_lead_time': max_lead_time
                })
        return True

    def _auto_create_components_orderpoint(self):
        if self._context.get('prevent_component_recursion'):
            return
        
        to_process = list(self)
        processed_products = set()
        all_affected_orderpoints = self.env['stock.warehouse.orderpoint']
        
        while to_process:
            op = to_process.pop(0)
            if not op.auto_create_components_orderpoint or not op.product_id or op.product_id.id in processed_products:
                continue
            
            processed_products.add(op.product_id.id)
            
            bom_dict = self.env['mrp.bom']._bom_find(op.product_id, company_id=op.company_id.id)
            bom = bom_dict.get(op.product_id)
            if not bom:
                continue
            
            for line in bom.bom_line_ids:
                product = line.product_id
                if not product or not product.active or product.type == 'combo' or not product.is_storable:
                    continue
                
                existing_op = self.env['stock.warehouse.orderpoint'].search([
                    ('product_id', '=', product.id),
                    ('warehouse_id', '=', op.warehouse_id.id),
                    ('location_id', '=', op.location_id.id),
                    ('company_id', '=', op.company_id.id),
                ], limit=1)
                
                if existing_op:
                    if op.auto_create_components_orderpoint and not existing_op.auto_create_components_orderpoint:
                        existing_op.write({'auto_create_components_orderpoint': True})
                    comp_op = existing_op
                else:
                    create_vals = {
                        'product_id': product.id,
                        'warehouse_id': op.warehouse_id.id,
                        'location_id': op.location_id.id,
                        'company_id': op.company_id.id,
                        'route_id': op.route_id.id if op.route_id else False,
                        'document_creation_option': op.document_creation_option,
                        'consider_current_period_sales': op.consider_current_period_sales,
                        'buffer_days': op.buffer_days,
                        'average_sale_calculation_base': op.average_sale_calculation_base,
                        'add_purchase_in_lead_calc': op.add_purchase_in_lead_calc,
                        'add_iwt_in_lead_calc': op.add_iwt_in_lead_calc,
                        'add_mo_in_lead_calc': op.add_mo_in_lead_calc,
                        'add_sc_in_lead_calc': op.add_sc_in_lead_calc,
                        'demand_planning_type': op.demand_planning_type,
                        'qty_multiple': op.qty_multiple,
                        'visibility_days': op.visibility_days,
                        'trigger': 'auto',
                        'auto_create_components_orderpoint': op.auto_create_components_orderpoint,
                    }
                    comp_op = self.env['stock.warehouse.orderpoint'].create(create_vals)
                
                all_affected_orderpoints |= comp_op
                
                if comp_op.product_id.id not in processed_products:
                    to_process.append(comp_op)
            
        if all_affected_orderpoints:
            all_affected_orderpoints.with_context(prevent_component_recursion=True).update_product_purchase_history()
            all_affected_orderpoints.with_context(prevent_component_recursion=True).update_product_iwt_history()
            all_affected_orderpoints.with_context(prevent_component_recursion=True).update_product_sales_history()
            
            for op in all_affected_orderpoints:
                op.with_context(prevent_component_recursion=True).recalculate_data()

    def recalculate_data(self):
        """
              added by: Aastha Vora | On: Oct - 16 - 2024 | Task: 998
              use: Recalculate order point data.
        """
        history_context = self._context.get('already_calculated_history', False)
        self.reset_all_data()
        if not history_context:
            if self.demand_planning_type in ('sales_driven', 'combined'):
                self.update_product_sales_history()
            if self.demand_planning_type in ('production_driven', 'combined'):
                self.update_product_consumption_history()
                self.update_product_resupply_history()
            self.update_product_purchase_history()
            self.update_product_iwt_history()
            self.update_product_production_history()
            self.update_product_subcontract_history()
            if self.scrap_enabled:
                self.update_product_scrap_history()
        self._calculate_lead_time()
        self.calculate_sales_average_max()
        self.onchange_average_sale_calculation_base()
        self.onchange_safety_stock()
        self.onchange_avg_sale_lead_time()
        self.onchange_safety_stock()
        self.write({'warehouse_changed': False})

