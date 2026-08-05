# -*- coding: utf-8 -*-
import logging
from collections import defaultdict
from datetime import datetime
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from decimal import Decimal, ROUND_HALF_UP

_logger = logging.getLogger(__name__)


class AdvanceReorderOrderProcess(models.Model):
    _inherit = 'advance.reorder.orderprocess'

    generate_demand_with = fields.Selection([('history_sales', 'Historical Sources'),
                                             ('forecast_sales', 'Forecast Sources')],
                                            string="Demand calculation by",
                                            help="Demand generate based on past sales or forecasted sales",
                                            default='history_sales')

    calculate_demand_based_on = fields.Selection(
        [
            ('bom', 'Based on BOM'),
            ('without_bom', 'Without BOM'),
        ],
        string='Calculate Demand Based On',
        default='bom',
        required=True,
        help='Based on BOM: explode using the product Reorder BOM. '
             'Without BOM: split FG/SFG demand across BOMs using completed MO '
             'usage ratios, then explode each BOM for component demand.',
    )

    component_demand_line_ids = fields.One2many(
        'advance.reorder.component.demand.line',
        'reorder_process_id',
        string='Component Demand Lines',
    )
    to_be_produced_line_ids = fields.One2many(
        'advance.reorder.to.be.produced.line',
        'reorder_process_id',
        string='To Be Produced Lines',
    )
    by_product_line_ids = fields.One2many(
        'advance.reorder.by.product.line',
        'reorder_process_id',
        string='By Product Lines',
    )
    production_ids = fields.One2many(
        'mrp.production',
        'reorder_process_id',
        string='Manufacturing Orders',
    )
    production_count = fields.Integer(
        string='Manufacturing Order Count',
        compute='_compute_production_count',
    )
    fg_count = fields.Integer(compute='_compute_fg_count')
    sfg_count = fields.Integer(compute='_compute_sfg_count')
    component_count = fields.Integer(compute='_compute_component_count')

    has_purchase_action_summary = fields.Boolean(
        string='Has Purchase Action Summary',
        compute='_compute_summary_action_flags',
        store=True,
    )
    has_production_action_summary = fields.Boolean(
        string='Has Production Action Summary',
        compute='_compute_summary_action_flags',
        store=True,
    )
    show_subcontracting_qty = fields.Boolean(
        string="Show Resupply Qty",
        related='company_id.use_subcontracting_for_demand',
        store=True,
    )
    show_scrap_qty = fields.Boolean(
        string="Show Scrap Qty",
        related='company_id.use_scrap_for_demand',
        store=True,
    )

    @api.onchange('product_ids', 'calculate_demand_based_on')
    def _onchange_product_ids(self):
        """Updates demand planning type and set the default BOM when products or demand calculation method changes."""
        for product in self.product_ids:
            if not product.demand_planning_type:
                product._compute_demand_planning_type()
            if self.calculate_demand_based_on == 'bom' and not product.reorder_bom_id:
                product.reorder_bom_id = product.get_default_bom()

    def _compute_production_count(self):
        """Computes the total number of linked manufacturing orders."""
        for record in self:
            record.production_count = len(record.production_ids)

    def _compute_fg_count(self):
        """Computes the total number of finished goods (FG) demand lines."""
        for record in self:
            record.fg_count = len(
                record.line_ids.filtered(lambda l: l.product_id.reorder_product_classification == 'finished_good'))

    def _compute_sfg_count(self):
        """Computes the total number of semi-finished goods (SFG) demand lines."""
        for record in self:
            line_count = len(
                record.line_ids.filtered(lambda l: l.product_id.reorder_product_classification == 'semi_finished_good'))
            tbp_count = len(record.to_be_produced_line_ids)
            record.sfg_count = line_count + tbp_count

    def _compute_component_count(self):
        """Computes the total number of component demand lines."""
        for record in self:
            line_count = len(
                record.line_ids.filtered(lambda l: l.product_id.reorder_product_classification == 'raw_material'))
            comp_count = len(record.component_demand_line_ids)
            record.component_count = line_count + comp_count

    def action_view_fg(self):
        """Opens the Finished Goods (FG) demand calculation lines."""
        self.ensure_one()
        fg_lines = self.line_ids.filtered(lambda l: l.product_id.reorder_product_classification == 'finished_good')
        return {
            'name': _('FG Demand Calculation'),
            'type': 'ir.actions.act_window',
            'res_model': 'advance.reorder.orderprocess.line',
            'view_mode': 'list',
            'views': [(self.env.ref('setu_advance_reordering_extended.view_fg_demand_planning_tree').id, 'list')],
            'domain': [('id', 'in', fg_lines.ids)],
            'target': 'current',
        }

    def action_view_sfg(self):
        """Prepares and opens the Semi-Finished Goods (SFG) demand planning lines."""
        self.ensure_one()
        self.env['advance.reorder.planning.line'].search(
            [('reorder_process_id', '=', self.id), ('line_type', '=', 'sfg'), ]).unlink()
        planning_vals = []
        for line in self.to_be_produced_line_ids:
            planning_vals.append({
                'reorder_process_id': self.id,
                'product_id': line.product_id.id,
                'net_demand': line.net_demand,
                'line_type': 'sfg',
            })
        sfg_lines = self.line_ids.filtered(
            lambda l: l.product_id.reorder_product_classification == 'semi_finished_good')
        for line in sfg_lines:
            planning_vals.append({
                'reorder_process_id': self.id,
                'product_id': line.product_id.id,
                'net_demand': line.demanded_qty,
                'line_type': 'sfg',
            })
        if planning_vals:
            self.env['advance.reorder.planning.line'].create(planning_vals)

        return {
            'name': _('SFG Demand Calculation'),
            'type': 'ir.actions.act_window',
            'res_model': 'advance.reorder.planning.line',
            'view_mode': 'list',
            'views': [
                (self.env.ref('setu_advance_reordering_extended.view_advance_reorder_planning_line_tree').id, 'list')],
            'domain': [('reorder_process_id', '=', self.id), ('line_type', '=', 'sfg')],
            'target': 'current',
        }

    def action_view_components(self):
        """Prepares and opens the Component demand planning lines."""
        self.ensure_one()
        self.env['advance.reorder.planning.line'].search(
            [('reorder_process_id', '=', self.id), ('line_type', '=', 'component'), ]).unlink()
        planning_vals = []
        for line in self.component_demand_line_ids:
            planning_vals.append({
                'reorder_process_id': self.id,
                'product_id': line.product_id.id,
                'net_demand': line.net_demand,
                'line_type': 'component',
            })
        comp_lines = self.line_ids.filtered(lambda l: l.product_id.reorder_product_classification == 'raw_material')
        for line in comp_lines:
            planning_vals.append({
                'reorder_process_id': self.id,
                'product_id': line.product_id.id,
                'net_demand': line.demanded_qty,
                'line_type': 'component',
            })
        if planning_vals:
            self.env['advance.reorder.planning.line'].create(planning_vals)

        return {
            'name': _('Components Demand Calculation'),
            'type': 'ir.actions.act_window',
            'res_model': 'advance.reorder.planning.line',
            'view_mode': 'list',
            'views': [
                (self.env.ref('setu_advance_reordering_extended.view_advance_reorder_planning_line_tree').id, 'list')],
            'domain': [('reorder_process_id', '=', self.id), ('line_type', '=', 'component')],
            'target': 'current',
        }

    @api.depends('summary_ids', 'summary_ids.order_action')
    def _compute_summary_action_flags(self):
        """Computes whether the summary contains purchase and/or production actions."""
        for record in self:
            actions = set(record.summary_ids.mapped('order_action'))
            record.has_purchase_action_summary = 'purchase' in actions
            record.has_production_action_summary = 'production' in actions

    def _get_warehouse_qty_summary(self, product, warehouses):
        """Calculates the total available, incoming, and outgoing quantities across the selected warehouses."""
        wh_available = sum(
            product.with_context(warehouse_id=warehouse.id).virtual_available
            for warehouse in warehouses
        )
        wh_outgoing = sum(
            product.with_context(warehouse_id=warehouse.id).outgoing_qty
            for warehouse in warehouses
        )
        wh_incoming = sum(
            product.with_context(warehouse_id=warehouse.id).incoming_qty
            for warehouse in warehouses
        )

        return {
            'available': max(0, wh_available),
            'outgoing': wh_outgoing,
            'incoming': wh_incoming,
        }

    def get_sales_data(self, config, line_product_ids, is_sfg=False):
        """Retrieves sales or forecast demand data for eligible products based on the configured demand source"""
        """"DP"""
        sales_driven_products = line_product_ids
        if not is_sfg:
            sales_driven_products = line_product_ids.filtered(
                lambda pr: pr.is_kit_component or pr.demand_planning_type in ('sales_driven', 'combined'))
        products = sales_driven_products and set(sales_driven_products.ids) or {}
        if not products:
            return []
        warehouses = config.warehouse_group_id and set(config.warehouse_group_id.warehouse_ids.ids) or {}
        if self.generate_demand_with == 'history_sales':
            return self.get_history_sales(products, warehouses, self.sales_start_date, self.sales_end_date)
        else:
            return self.get_forecast_sales(products, warehouses, config)

    def get_production_data(self, config, line_product_ids):
        """"DP"""
        """Retrieves production consumption history and ADS for production-driven products."""
        if not self.sales_start_date or not self.sales_end_date or not line_product_ids:
            return []

        production_driven_products = line_product_ids.filtered(
            lambda pr: pr.demand_planning_type != 'sales_driven')
        products = set(production_driven_products.ids) if production_driven_products else set()
        if not products:
            return []

        warehouse_ids = config.warehouse_group_id.warehouse_ids.ids
        warehouses = set(warehouse_ids) if warehouse_ids else {}
        start_date = self.sales_start_date.strftime('%Y-%m-%d')
        end_date = self.sales_end_date.strftime('%Y-%m-%d')

        query = """
            Select product_id, product_name,
                sum(consumed_qty) as consumed_qty,
                sum(ads) as ads
            from get_products_production_warehouse_group_wise('%s', '%s', '%s', '%s', '%s', '%s')
            group by product_id, product_name
        """ % ('{}', products, '{}', warehouses, start_date, end_date)
        self._cr.execute(query)
        return self._cr.dictfetchall()

    def get_resupply_data(self, config, line_product_ids):
        """Retrieves subcontracting resupply history and ADS for production-driven products."""
        if not self.sales_start_date or not self.sales_end_date or not line_product_ids:
            return []

        if not self.company_id.use_subcontracting_for_demand:
            return []

        production_driven_products = line_product_ids.filtered(
            lambda pr: pr.is_kit_component or  pr.demand_planning_type != 'sales_driven')
        products = set(production_driven_products.ids) if production_driven_products else set()
        if not products:
            return []

        warehouse_ids = config.warehouse_group_id.warehouse_ids.ids
        warehouses = set(warehouse_ids) if warehouse_ids else {}
        start_date = self.sales_start_date.strftime('%Y-%m-%d')
        end_date = self.sales_end_date.strftime('%Y-%m-%d')

        query = """
            Select product_id, product_name,
                sum(resupply_qty) as resupply_qty,
                sum(resupply_return_qty) as resupply_return_qty,
                sum(ads) as ads
            from get_products_subcontracting_warehouse_group_wise('%s', '%s', '%s', '%s', '%s', '%s')
            group by product_id, product_name
        """ % ('{}', products, '{}', warehouses, start_date, end_date)
        self._cr.execute(query)
        return self._cr.dictfetchall()

    def get_scrap_data(self, config, line_product_ids, ):
        """Retrieves scrap history and ADS for the selected products."""
        if not self.sales_start_date or not self.sales_end_date or not line_product_ids:
            return []

        if not self.company_id.use_scrap_for_demand:
            return []

        products = set(line_product_ids.ids)
        if not products:
            return []

        warehouse_ids = config.warehouse_group_id.warehouse_ids.ids
        warehouses = set(warehouse_ids) if warehouse_ids else {}
        start_date = self.sales_start_date.strftime('%Y-%m-%d')
        end_date = self.sales_end_date.strftime('%Y-%m-%d')

        query = """
            Select product_id, product_name,
                sum(scrap_qty) as scrap_qty,
                sum(ads) as ads
            from get_products_scrap_warehouse_group_wise('%s', '%s', '%s', '%s', '%s', '%s')
            group by product_id, product_name
        """ % ('{}', products, '{}', warehouses, start_date, end_date)
        self._cr.execute(query)
        return self._cr.dictfetchall()

    def _merge_ads_data(self, sales_data, production_data, resupply_data, scrap_data):
        """
        Merges sales, production, resupply, and scrap data into a single product-wise demand summary with calculated ADS.
        """

        if not any((sales_data, production_data, resupply_data, scrap_data)):
            return []

        # Create lookup dictionaries
        sales_map = {r['product_id']: r for r in sales_data}
        production_map = {r['product_id']: r for r in production_data}
        resupply_map = {r['product_id']: r for r in resupply_data}
        scrap_map = {r['product_id']: r for r in scrap_data}

        # Get all products available in any source
        product_ids = (
                set(sales_map)
                | set(production_map)
                | set(resupply_map)
                | set(scrap_map)
        )

        merged = []

        for product_id in product_ids:
            sales = sales_map.get(product_id, {})
            production = production_map.get(product_id, {})
            resupply = resupply_map.get(product_id, {})
            scrap = scrap_map.get(product_id, {})
            ads_values = []

            if sales:
                ads_values.append(sales.get('ads', 0.0))
            if production:
                ads_values.append(production.get('ads', 0.0))
            if resupply:
                ads_values.append(resupply.get('ads', 0.0))
            if scrap:
                ads_values.append(scrap.get('ads', 0.0))

            avg_ads = sum(ads_values) if ads_values else 0.0

            merged.append({
                'product_id': product_id,
                'product_name': (
                        sales.get('product_name')
                        or production.get('product_name')
                        or resupply.get('product_name')
                        or scrap.get('product_name')
                ),
                'sales_qty': sales.get('sales', 0.0),
                'sales_return': sales.get('sales_return', 0.0),
                'total_sales': sales.get('total_sales', 0.0),
                'consumed_qty': production.get('consumed_qty', 0.0),
                'resupply_qty': resupply.get('resupply_qty', 0.0),
                'resupply_return_qty': resupply.get('resupply_return_qty', 0.0),
                'scrap_qty': scrap.get('scrap_qty', 0.0),
                'ads': avg_ads,
            })
        return merged

    def _prepare_base_line_vals(self, config, product):
        """Prepares the base values for creating reorder line, including warehouse stock and related stock moves."""
        wh_summary = self._get_warehouse_qty_summary(
            product, config.warehouse_group_id.warehouse_ids
        )
        moves = self.get_stock_move(product, config)
        return {
            'config_id': config.id,
            'warehouse_group_id': config.warehouse_group_id.id,
            'reorder_process_id': self.id,
            'product_id': product.id,
            'available_stock': wh_summary['available'],
            'incoming_qty': wh_summary['incoming'],
            'stock_move_ids': [(6, 0, moves)],
        }

    def prepare_reorder_line_vals(self, config, demand_data, is_mto_route):
        """
        Calculates product demand quantities and prepares reorder line values based on demand, stock, and configuration.
        """
        vals = []
        reorder_demand_growth = self.reorder_demand_growth and self.reorder_demand_growth / 100 or 0.0
        reorder_rounding_method = self.company_id.reorder_rounding_method
        reorder_round_quantity = self.company_id.reorder_round_quantity

        for data in demand_data:
            product = self.env['product.product'].browse(data.get('product_id'))
            reorder_line_vals = self._prepare_base_line_vals(config, product)

            net_on_hand = reorder_line_vals.get('available_stock', 0.0)
            ads = data.get('ads', 0.0)

            if self.generate_demand_with == 'history_sales':
                ads = reorder_demand_growth and ads + (ads * reorder_demand_growth) or ads
                lead_days_demand = round(ads * config.vendor_lead_days, 2)
                expected_sales = self.buffer_security_days * ads
            else:
                lead_days_demand = data.get('lead_days_demand_stock', 0.0)
                expected_sales = data.get('expected_sales_stock', 0.0)

            transit_demand = lead_days_demand if net_on_hand > lead_days_demand else net_on_hand
            transit_demand = transit_demand if transit_demand > 0.0 else 0.0
            stock_after_transit = net_on_hand - transit_demand

            demand_qty = round(0 if stock_after_transit > expected_sales
                               else expected_sales - stock_after_transit, 2)
            demand_adjustment_qty = demand_qty

            if reorder_round_quantity and not demand_adjustment_qty % reorder_round_quantity == 0.0:
                if reorder_rounding_method == 'round_up' and not demand_qty == 0.0:
                    # c2 = (a + b) - (a % b);
                    demand_adjustment_qty = (demand_qty + reorder_round_quantity) - (
                            demand_qty % reorder_round_quantity)
                elif reorder_rounding_method == 'round_down' and not demand_qty == 0.0:
                    # c1 = a - (a % b);
                    demand_adjustment_qty = demand_qty - (demand_qty % reorder_round_quantity)

            if is_mto_route:
                return round(demand_adjustment_qty, 0)

            reorder_line_vals.update({
                'average_daily_sale': ads,
                'transit_time_sales': transit_demand,
                'stock_after_transit': stock_after_transit,
                'expected_sales': expected_sales,
                'sales_qty': data.get('sales_qty', 0),
                'sales_return_qty': data.get('sales_return', 0),
                'consumed_qty': data.get('consumed_qty', 0),
                'resupply_qty': data.get('resupply_qty', 0),
                'resupply_return_qty': data.get('resupply_return_qty', 0),
                'scrap_qty': data.get('scrap_qty', 0),
                'demanded_qty': demand_qty,
                'demand_adjustment_qty': round(demand_adjustment_qty, 0),
            })

            line_id = self.line_ids.filtered(lambda x: x.product_id == product and
                                                       x.warehouse_group_id == config.warehouse_group_id)
            if line_id:
                line_id.write(reorder_line_vals)
                continue
            vals.append((0, 0, reorder_line_vals))
        return vals

    def _get_kit_component(self, products):
        """Return the component products for the given kit products."""
        component_products = self.env['product.product']

        for product in products:
            bom = self._get_product_bom(product)
            if bom:
                component_products |= bom.bom_line_ids.mapped('product_id')

        return component_products

    def action_reorder_confirm(self):
        """"DP"""
        """
        Override to merge sales and production consumption ADS per product planning type.
        Generates reorder demand lines by collecting, merging, and processing demand data from sales, production,
        subcontracting, scrap, and kit products.

        For each config:
          1. Fetch sales data (via super's get_sales_data).
          2. Fetch production consumption data (via get_production_data).
          3. Fetch Scrap data (via get_scrap_data).
          4. Fetch Resupply data (via get_resupply_data).
          5. Merge all datasets per product demand_planning_type:
               - sales_driven     → sales data only (unchanged behaviour), adding kit component
               - production_driven → production consumption(production + resupply) ADS replaces sales ADS
               - combined         → combined ADS = sales_ads + production_ads + scrap_ads
          6. Pass merged data to prepare_reorder_line_vals as usual.
          7. Calculate demand of to be produced product, component and by product.
        """
        self.check_configuration_product()
        vals = []
        reorder_vals = {}
        resupply_data = []
        production_data = []
        scrap_data = []
        for config in self.config_ids:
            line_product_ids = self.product_ids.filtered(lambda x: not x.is_kit_product)
            kit_product_ids = self.product_ids.filtered(lambda x: x.is_kit_product)
            line_product_ids |= self._get_kit_component(kit_product_ids)
            sales_data = self.get_sales_data(config, line_product_ids,)
            if self.generate_demand_with == 'history_sales' and line_product_ids:
                production_data = self.get_production_data(config, line_product_ids)
                scrap_data = self.get_scrap_data(config, line_product_ids,)
                resupply_data = self.get_resupply_data(config, line_product_ids)
            demand_data = self._merge_ads_data(sales_data, production_data, resupply_data, scrap_data)
            vals.extend(
                self.prepare_reorder_line_vals(config, demand_data, is_mto_route=False))
        if not self.state == 'inprogress':
            reorder_vals = {'state': 'no_data'}
        vals and reorder_vals.update({'line_ids': vals, 'state': 'inprogress'})
        self.write(reorder_vals)
        self.invalidate_recordset(['line_ids'])
        if self.line_ids:
            self.to_be_produced_line_ids.unlink()
            self.component_demand_line_ids.unlink()
            self.by_product_line_ids.unlink()
            self._collect_mrp_tab_requirements()
        return True

    def _collect_mrp_tab_requirements(self, ):
        """Generates the To Be Produced, Component Demand, and By-Product lines by exploding product BOMs."""
        produced_data = defaultdict(float)
        component_data = defaultdict(
            lambda: {
                'qty': 0.0,
                'source_line_ids': [],
            }
        )
        by_product_data = []
        warehouse_groups = self.config_ids.mapped('warehouse_group_id')
        use_bom = self.calculate_demand_based_on == 'bom'

        for config in self.config_ids:
            lines = self.line_ids.filtered(lambda x: x.config_id.id == config.id)
            mo_bom_wise_data = {}
            if not use_bom:
                product_ids = lines.filtered(
                    lambda line: (
                            line.demand_adjustment_qty > 0
                            and line.product_id.reorder_product_classification in (
                                'finished_good',
                                'semi_finished_good',
                            )
                    )
                ).mapped('product_id')
                mo_bom_wise_data = self._get_bom_wise_mo_count(config.warehouse_group_id, product_ids)
            for line in lines:
                product = line.product_id
                qty = line.demand_adjustment_qty

                if qty <= 0 or product.is_kit_product:
                    continue

                if (use_bom
                        and product.reorder_product_classification in ('finished_good', 'semi_finished_good')
                        and not product.reorder_bom_id
                ):
                    _logger.warning(
                        "Reorder BOM not found for product '%s' (ID: %s). Skipping demand generation.",
                        product.display_name,
                        product.id,
                    )
                    continue

                classification = product.reorder_product_classification
                if classification in ('finished_good', 'semi_finished_good'):
                    self._explode_bom_into_tabs(
                        product,
                        qty,
                        component_data,
                        produced_data,
                        config,
                        by_product_data=by_product_data,
                        parent_product=product,
                        warehouse_groups=warehouse_groups,
                        mo_bom_wise_data=mo_bom_wise_data,
                    )

            component_data = dict(component_data)
            self._generate_component_demand_lines(config, component_data, )
            self._generate_by_product_lines(config, by_product_data)

    def _explode_bom_into_tabs(
            self, product, quantity, component_data, produced_data, config,
            bom=None, by_product_data=None,
            parent_product=None, warehouse_groups=None, mo_bom_wise_data={},
    ):
        """Recursively explodes a product BOM and distributes its requirements into the appropriate MRP tabs."""
        if quantity <= 0:
            return

        if self.calculate_demand_based_on == 'without_bom':
            bom_wise_demand = self._get_bom_wise_demand_by_mo_ratio(
                product,
                quantity,
                mo_bom_wise_data=mo_bom_wise_data,
            )
        else:
            default_bom = bom or self._get_product_bom(product)
            bom_wise_demand = [(default_bom, quantity)] if default_bom else []

        if not bom_wise_demand:
            _logger.warning(
                "No BOM found for product %s (ID: %s).",
                product.display_name,
                product.id,
            )
            return

        bom_parent = parent_product or product

        for bom, qty in bom_wise_demand:
            self._collect_bom_by_products(product, qty, by_product_data, bom=bom,)

            bom_qty = bom.product_qty or 1.0

            for bom_line in bom.bom_line_ids:
                component = bom_line.product_id
                if not component:
                    continue

                required_qty = qty * (bom_line.product_qty / bom_qty)

                self._process_product_by_classification(
                    component, required_qty, component_data, produced_data, config, bom,
                    by_product_data=by_product_data,
                    source_product=bom_parent, source_qty=qty,
                    warehouse_groups=warehouse_groups, mo_bom_wise_data=mo_bom_wise_data,
                )

    def _process_product_by_classification(
            self, product, qty, component_data, produced_data, config, bom,
            by_product_data=None, source_product=None, source_qty=0,
            warehouse_groups=None, mo_bom_wise_data=None,
    ):
        """Processes each BOM component based on its product classification."""
        if not product or qty <= 0:
            return

        classification = product.reorder_product_classification
        mo_bom_wise_data = mo_bom_wise_data or {}

        if classification == 'raw_material':
            self._add_to_component_tab(component_data, product, qty, bom, source_product, source_qty)

        elif classification == 'semi_finished_good':
            line, qty = self._create_or_update_to_be_produced_line(
                product, qty, bom, source_product, source_qty, warehouse_groups, produced_data, config,
            )

            if product.id not in mo_bom_wise_data:
                mo_bom_wise_data.update(self._get_bom_wise_mo_count(config.warehouse_group_id, product))

            self._explode_bom_into_tabs(
                product, qty, component_data, produced_data, config, line.bom_id,
                by_product_data=by_product_data,
                parent_product=product, warehouse_groups=warehouse_groups,
                mo_bom_wise_data=mo_bom_wise_data,
            )

    def _get_bom_wise_mo_count(self, warehouse_group_id, product_ids):
        """ Call get_product_mo_bom_wise once and return {product_id: {bom_id: mo_count}}.
            Retrieves BOM-wise manufacturing order counts for products within the selected period.
        """
        if not self.sales_start_date or not self.sales_end_date:
            return {}

        if not product_ids:
            return {}

        company_ids = {self.company_id.id} if self.company_id else {}
        products = set(product_ids.ids)
        category_ids = {}
        warehouse_ids = warehouse_group_id.warehouse_ids.ids
        warehouses = set(warehouse_ids) if warehouse_ids else {}
        start_date = self.sales_start_date.strftime('%Y-%m-%d')
        end_date = self.sales_end_date.strftime('%Y-%m-%d')

        query = """
            SELECT product_id, bom_id, mo_ids
            FROM get_product_mo_bom_wise('%s', '%s', '%s', '%s', '%s', '%s', '%s')
        """ % (company_ids, products, category_ids, warehouses, '{}', start_date, end_date)
        self._cr.execute(query)
        rows = self._cr.dictfetchall()

        mo_bom_data = defaultdict(dict)
        for row in rows:
            product_id = row.get('product_id')
            bom_id = row.get('bom_id')
            if not product_id or not bom_id:
                continue
            mo_ids = row.get('mo_ids') or []
            mo_bom_data[product_id][bom_id] = (
                    mo_bom_data[product_id].get(bom_id, 0) + len(mo_ids)
            )
        return dict(mo_bom_data)

    def _get_bom_wise_demand_by_mo_ratio(self, product, quantity, mo_bom_wise_data=None):
        """
        Splits product demand across BOMs based on completed manufacturing order ratios.

        Returns list of (bom, allocated_qty). Falls back to reorder/default BOM
        when no completed MOs exist for the product in the period.
        """
        if quantity <= 0 or not product:
            return []

        bom_counts = (mo_bom_wise_data or {}).get(product.id, {})
        total_mos = sum(bom_counts.values())
        if not bom_counts or total_mos <= 0:
            bom = self._get_product_bom(product)
            return [(bom, quantity)] if bom else []

        Bom = self.env['mrp.bom']
        bom_wise_demand = []
        for bom_id, mo_count in bom_counts.items():
            bom = Bom.browse(bom_id)
            if not bom.exists():
                continue

            bom_demand_qty = quantity * (mo_count / total_mos)
            bom_demand_qty = int(
                Decimal(str(bom_demand_qty)).quantize(
                    Decimal('1'),
                    rounding=ROUND_HALF_UP,
                )
            )
            if bom_demand_qty > 0:
                bom_wise_demand.append((bom, bom_demand_qty))
        return bom_wise_demand

    def _collect_bom_by_products(self, product, parent_mo_qty, by_product_data, bom=None):
        """Collects by-product quantities generated from a BOM based on the parent production quantity."""
        if parent_mo_qty <= 0 or by_product_data is None:
            return

        bom = bom or self._get_product_bom(product)
        if not bom or not bom.byproduct_ids:
            return

        bom_qty = bom.product_qty or 1.0
        for byproduct in bom.byproduct_ids:
            if not byproduct.product_id:
                continue
            byproduct_qty = parent_mo_qty * (byproduct.product_qty / bom_qty)
            self._add_to_by_product_tab(
                by_product_data, byproduct.product_id, byproduct_qty,
                source_product=product, source_product_demand=parent_mo_qty,
            )

    def _add_to_by_product_tab(
            self, by_product_data, product, qty, source_product=None, source_product_demand=0.0,
    ):
        """Adds a by-product entry to the by-product demand collection."""
        if product and qty > 0:
            by_product_data.append({
                'product_id': product.id,
                'source_product_id': source_product.id if source_product else False,
                'source_product_demand': source_product_demand,
                'quantity': qty,
            })

    def _add_to_component_tab(self, component_data, product, qty, bom, source_product, source_qty):
        """Adds a component requirement and its source details to the component demand collection."""
        if not product or qty <= 0:
            return

        component = component_data[product.id]
        component['qty'] += qty
        component['source_line_ids'].append(
            (0, 0, {
                'source_product_id': source_product.id,
                'bom_id': bom.id,
                'source_qty': source_qty,
                'required_qty': qty,
            })
        )

    def _prepare_to_be_produced_line_vals(self, product, required_qty, bom, source_product, source_qty,
                                          warehouse_groups, config):
        """Prepares values for creating a "To Be Produced" demand line."""
        warehouse_ids = warehouse_groups.mapped('warehouse_ids').ids
        warehouse_qty = self._get_warehouse_qty_summary(
            product, self.env['stock.warehouse'].browse(warehouse_ids)
        )
        scrap_data = self.get_scrap_data(config, product, )
        return {
            'reorder_process_id': self.id,
            'config_id': config.id,
            'warehouse_group_id': config.warehouse_group_id.id,
            'product_id': product.id,
            'bom_id': product.reorder_bom_id.id or product.get_default_bom().id,
            'available_qty': warehouse_qty['available'],
            'required_qty': required_qty,
            'incoming_qty': warehouse_qty['incoming'],
            'scrap_qty': scrap_data[0].get('scrap_qty', 0) if scrap_data else 0,
            'net_demand': max(
                0.0,
                required_qty - warehouse_qty['available'],
            ),
            'source_line_ids': [
                (0, 0, {
                    'source_product_id': source_product.id,
                    'bom_id': bom.id,
                    'source_qty': source_qty,
                    'required_qty': required_qty,
                })
            ],
        }

    def _create_or_update_to_be_produced_line(self, product, qty, bom, source_product, source_qty, warehouse_groups,
                                              produced_data, config):
        """Create a to-be-produced line when an SFG is found; update if the same SFG appears again."""
        ProducedLine = self.env['advance.reorder.to.be.produced.line']
        if not product or qty <= 0:
            return ProducedLine

        produced_data[product.id] += qty
        match_line = self.to_be_produced_line_ids.filtered(lambda l: l.product_id.id == product.id)[:1]
        if match_line:
            match_line = self.to_be_produced_line_ids.filtered(lambda x: x.product_id.id == product.id)
            required_qty = qty
            if match_line.net_demand <= 0:
                required_qty = abs(min(0, match_line.available_qty - match_line.required_qty - qty))

            match_line.write({
                'required_qty': match_line.required_qty + qty,
                'net_demand': max(
                    0.0,
                    (match_line.required_qty + qty) - match_line.available_qty,
                ),
                'source_line_ids': [
                    (0, 0, {
                        'source_product_id': source_product.id,
                        'bom_id': bom.id,
                        'source_qty': source_qty,
                        'required_qty': qty,
                    })
                ],
            })
            return match_line, required_qty

        vals = self._prepare_to_be_produced_line_vals(product, qty, bom, source_product, source_qty, warehouse_groups,
                                                      config)
        produced_line = ProducedLine.create(vals)
        return produced_line, produced_line.net_demand

    def _generate_component_demand_lines(self, config, component_data=None, ):
        """Creates component demand lines from the accumulated BOM component requirements."""
        if not component_data:
            return

        ComponentLine = self.env['advance.reorder.component.demand.line']
        warehouse_ids = self.config_ids.mapped('warehouse_group_id.warehouse_ids').ids

        for product_id, bom_required_qty in component_data.items():
            product = self.env['product.product'].browse(product_id)
            warehouse_qty = self._get_warehouse_qty_summary(
                product, self.env['stock.warehouse'].browse(warehouse_ids)
            )
            qty = bom_required_qty.get('qty')
            scrap_data = self.get_scrap_data(config, product, )
            ComponentLine.create({
                'reorder_process_id': self.id,
                'warehouse_group_id': config.warehouse_group_id.id,
                'product_id': product_id,
                'available_qty': warehouse_qty['available'],
                'required_qty': qty,
                'incoming_qty': warehouse_qty['incoming'],
                'scrap_qty': scrap_data[0].get('scrap_qty', 0) if scrap_data else 0,
                'net_demand': max(0.0, (qty - warehouse_qty['available']), ),
                'source_line_ids': bom_required_qty.get('source_line_ids'),
            })

    def _generate_by_product_lines(self, config, by_product_data=None):
        """Creates by-product demand lines from the collected by-product data."""
        if not by_product_data:
            return

        ByProductLine = self.env['advance.reorder.by.product.line']
        for entry in by_product_data:
            quantity = entry.get('quantity', 0.0)
            if quantity <= 0:
                continue
            ByProductLine.create({
                'reorder_process_id': self.id,
                'warehouse_group_id': config.warehouse_group_id.id,
                'product_id': entry['product_id'],
                'source_product_id': entry.get('source_product_id'),
                'source_product_demand': entry.get('source_product_demand', 0.0),
                'quantity': quantity,
            })

    def _get_product_bom(self, product):
        """Returns the configured reorder BOM or the product's default BOM."""
        return product.reorder_bom_id or (product.bom_ids[:1] if product.bom_ids else self.env['mrp.bom'])

    def action_reorder_reset_to_draft(self):
        """Clears all generated MRP demand lines and resets the reorder process to draft."""
        self.to_be_produced_line_ids.unlink()
        self.component_demand_line_ids.unlink()
        self.by_product_line_ids.unlink()
        return super().action_reorder_reset_to_draft()

    def _get_summary_vals_by_product(self, summary_vals):
        """Creates a product-wise dictionary from summary line values."""
        return {
            command[2]['product_id']: command[2]
            for command in summary_vals
            if command[0] == 0 and command[2].get('product_id')
        }

    def _get_purchase_details(self, product, company_id, demanded_qty, order_qty):
        """Retrieves vendor MOQ, purchase quantity, and purchase price for a product."""
        vendor_moq = 0
        purchase_qty = 0
        price = product.standard_price or 0.0

        ps_info = self._get_product_supplier_info(product, company_id, demanded_qty)

        if ps_info:
            vendor_moq = ps_info.reorder_minimum_quantity

            purchase_qty = round(
                product.uom_id._compute_quantity(
                    qty=order_qty,
                    to_unit=product.uom_po_id,
                )
            )

            if demanded_qty < vendor_moq:
                purchase_qty = vendor_moq

            if company_id and ps_info.currency_id != company_id.currency_id:
                price = ps_info.currency_id._convert(
                    ps_info.price,
                    company_id.currency_id,
                    company_id,
                    self.reorder_date or fields.Date.context_today(self),
                    False,
                )
            else:
                price = ps_info.price

        return vendor_moq, purchase_qty, price

    def _get_order_action(self, product):
        """Determines whether a product should be purchased or manufactured based on its routes and classification."""

        route_names = set(product.route_ids.mapped('name'))
        if {'Manufacture', 'Replenish on Order (MTO)'} <= route_names:
            return 'production'
        if {'Buy', 'Replenish on Order (MTO)'} <= route_names:
            return 'purchase'

        if product.reorder_product_classification in (
                'finished_good',
                'semi_finished_good',
        ):
            return 'production'

        return 'purchase'

    def _prepare_net_demand_summary_line_vals(self, product, order_qty, demanded_qty, order_action, warehouse_group,
                                              company_id=None,):
        """Prepares summary line values for the net demand calculation."""
        weight = max(product.weight or 1.0, 1.0)
        line_volume = order_qty * (product.volume or 0.0) * weight

        company_id = company_id or self.env.company

        vendor_moq = 0
        purchase_qty = 0
        price = product.standard_price or 0.0

        if order_action == "purchase":
            vendor_moq, purchase_qty, price = self._get_purchase_details(
                product,
                company_id,
                demanded_qty,
                order_qty,
            )
        line_amount = round(order_qty) * price
        return (
            {
                "product_id": product.id,
                "demanded_qty": demanded_qty,
                "vendor_moq": vendor_moq,
                "order_qty": order_qty,
                "total_volume": line_volume,
                "to_be_ordered_in_purchase_uom": purchase_qty,
                "order_action": order_action,
                "warehouse_group_id": warehouse_group.id,

            },
            line_volume,
            line_amount,
        )

    def _is_mto_buy_or_manufacture_product(self, product):
        """True when product has MTO with Buy and/or Manufacture routes."""
        route_names = set(product.route_ids.mapped('name'))
        return (
                {'Buy', 'Replenish on Order (MTO)'} <= route_names
                or {'Manufacture', 'Replenish on Order (MTO)'} <= route_names
        )

    def _append_net_demand_summary_from_tab_lines(
            self,
            summary_vals,
            total_volume,
            total_amount,
            tab_lines,
            order_action,
    ):
        """Adds products from MRP tab lines to the reorder summary."""
        summary_by_product = self._get_summary_vals_by_product(summary_vals)

        for tab_line in tab_lines:
            product = tab_line.product_id

            if (not product or product.id in summary_by_product):
                continue

            # MTO + Buy/Manufacture: summary demand from own sales qty only.
            if product.reorder_product_classification == "semi_finished_good" and self._is_mto_buy_or_manufacture_product(
                    product):
                sales_data = self.get_sales_data(tab_line.config_id, product, is_sfg=True)
                mto_sales_qty = self.prepare_reorder_line_vals(tab_line.config_id, sales_data,
                                                               is_mto_route=True, ) if sales_data else 0.0
                if mto_sales_qty <= 0:
                    continue

            order_qty = round(tab_line.net_demand)
            if order_qty <= 0:
                continue

            line_vals, line_volume, line_amount = (
                self._prepare_net_demand_summary_line_vals(
                    product=product,
                    order_qty=order_qty,
                    demanded_qty=order_qty,
                    order_action=order_action,
                    warehouse_group=tab_line.warehouse_group_id,
                )
            )
            summary_vals.append((0, 0, line_vals))
            summary_by_product[product.id] = line_vals
            total_volume += line_volume
            total_amount += line_amount

        return summary_vals, total_volume, total_amount

    def prepare_reorder_demand_summary_vals(self):
        """Prepares net demand summary lines from the reorder demand lines."""
        summary_vals = []
        total_volume = 0.0
        total_amount = 0.0

        for line in self.line_ids:
            summary_by_product = self._get_summary_vals_by_product(summary_vals)

            if (not line.product_id or line.product_id.id in summary_by_product):
                continue

            lines = self.line_ids.filtered(
                lambda l: l.product_id.id == line.product_id.id
            )
            demanded_qty = sum(lines.mapped("demand_adjustment_qty"))

            if demanded_qty <= 0:
                continue

            line.wh_sharing_percentage = round(
                (line.demand_adjustment_qty / demanded_qty) * 100
            )
            company_id = self.company_id

            line_vals, line_volume, line_amount = (
                self._prepare_net_demand_summary_line_vals(
                    product=line.product_id,
                    order_qty=demanded_qty,
                    demanded_qty=demanded_qty,
                    order_action=self._get_order_action(line.product_id),
                    warehouse_group=line.warehouse_group_id,
                    company_id=company_id,
                )
            )

            summary_vals.append((0, 0, line_vals))
            total_volume += line_volume
            total_amount += line_amount

        return summary_vals, total_volume, total_amount

    def prepare_reorder_summary_vals(self):
        """Prepares the complete reorder summary, including demand, production, and component lines."""
        summary_vals, total_volume, total_amount = self.prepare_reorder_demand_summary_vals()

        summary_vals, total_volume, total_amount = (
            self._append_net_demand_summary_from_tab_lines(
                summary_vals=summary_vals,
                total_volume=total_volume,
                total_amount=total_amount,
                tab_lines=self.to_be_produced_line_ids,
                order_action="production",
            )
        )

        return self._append_net_demand_summary_from_tab_lines(
            summary_vals=summary_vals,
            total_volume=total_volume,
            total_amount=total_amount,
            tab_lines=self.component_demand_line_ids,
            order_action="purchase",
        )

    def get_vendor_product_mapping_dict(self, purchase_summaries):
        """Groups products by vendor according to the selected vendor selection strategy."""
        product_ids = purchase_summaries.mapped('product_id')
        vendor_product_dict = {}
        if self.vendor_selection_strategy == 'specific_vendor':
            if not self.vendor_id:
                raise UserError(_('Please select a vendor for the specific vendor strategy.'))
            vendor_product_dict.update({self.vendor_id.id: product_ids.ids})
        elif self.vendor_selection_strategy in ('on_po_creation', 'without_vendor'):
            return vendor_product_dict
        elif self.vendor_selection_strategy in ('sequence', 'price', 'delay'):
            products_without_vendor = self.env['product.product']
            for product in product_ids:
                seller = product.with_context({
                    'sort_by': self.vendor_selection_strategy,
                    'op_company': self.company_id,
                })._select_seller(quantity=None)
                if not seller or not seller.partner_id:
                    products_without_vendor |= product
                    continue
                partner_id = seller.partner_id.id
                vendor_product_dict.setdefault(partner_id, []).append(product.id)
            if products_without_vendor:
                strategy_label = dict(
                    self._fields['vendor_selection_strategy'].selection
                ).get(self.vendor_selection_strategy, self.vendor_selection_strategy)
                raise ValidationError(_(
                    'No vendor found for the following product(s) with vendor selection '
                    'strategy "%(strategy)s":\n%(products)s',
                    strategy=strategy_label,
                    products='\n'.join(
                        '- %s' % product.display_name for product in products_without_vendor
                    ),
                ))
        else:
            for product in product_ids:
                seller = product.with_context({
                    'sort_by': self.vendor_selection_strategy,
                    'op_company': self.company_id,
                })._select_seller(quantity=None)
                if not seller or not seller.partner_id:
                    continue
                partner_id = seller.partner_id.id
                vendor_product_dict.setdefault(partner_id, []).append(product.id)
        return vendor_product_dict

    def action_create_reorder_purchase_order(self):
        """Creates purchase orders from purchase summary lines based on the vendor selection strategy."""
        self.ensure_one()
        purchase_summaries = self.summary_ids.filtered(lambda summary: summary.order_action == 'purchase')
        if not purchase_summaries:
            raise UserError(_('No summary lines are set to Generate Purchase Orders.'))

        if self.vendor_selection_strategy in ('on_po_creation', 'without_vendor'):
            return self.action_open_po_vendor_wizard()

        vendor_product_dict = self.get_vendor_product_mapping_dict(purchase_summaries)

        for vendor_id, product_list in vendor_product_dict.items():
            partner = self.env['res.partner'].browse(vendor_id)
            summary_lines = purchase_summaries.filtered(
                lambda summary, products=product_list: summary.product_id.id in products
            )
            if self.vendor_selection_strategy == 'specific_vendor' and \
                    partner.vendor_rule in ['both', 'minimum_order_value'] and \
                    self.reorder_amount < self.minimum_reorder_amount:
                raise UserError(_("Can not create purchase order because reorder doesn't fulfil "
                                  "vendor's minimum order amount's rule."))
            for config_id in self.config_ids:
                self.create_purchase_order(
                    config_id.default_warehouse_id,
                    config_id.warehouse_group_id,
                    partner=partner,
                    summary_lines=summary_lines,
                )

        if self.purchase_ids:
            self.write({'state': 'done'})
        return True

    def _prepare_purchase_order_line_vals(self, fpos, warehouse_group_id, partner=None, summary_lines=None):
        """Override to handle summary lines that have no matching reorder line.

        In the extended module, summary lines can originate from:
          - Regular demand lines (in self.line_ids) — handled by super().
          - Component demand lines / to-be-produced lines that are not present
            in self.line_ids (e.g. raw-material components from BOM explosion).

        """
        partner = partner or self.vendor_id
        if not partner:
            raise UserError(_('A vendor is required to prepare purchase order lines.'))

        summaries = summary_lines if summary_lines is not None else self.summary_ids
        company_for_tax = self.company_id or self.env.company

        # Split summaries into two buckets:
        #   - backed_summaries: product exists in line_ids for this warehouse_group → use super()
        #   - standalone_summaries: product is NOT in line_ids (e.g. component demand lines)
        backed_summaries = self.env['advance.reorder.orderprocess.summary']
        standalone_summaries = self.env['advance.reorder.orderprocess.summary']

        for summary in summaries:
            reorder_line = self.line_ids.filtered(
                lambda x, pid=summary.product_id.id, wgid=warehouse_group_id.id: (
                        x.product_id.id == pid
                        and x.warehouse_group_id.id == wgid
                        and x.demand_adjustment_qty > 0.0
                )
            )
            if reorder_line:
                backed_summaries |= summary
            else:
                standalone_summaries |= summary

        # 1. Get PO lines for summaries backed by reorder lines (base behaviour).
        po_line_vals = super()._prepare_purchase_order_line_vals(
            fpos, warehouse_group_id, partner=partner, summary_lines=backed_summaries,
        ) if backed_summaries else []

        # 2. Build PO lines for standalone summary lines (no matching reorder line).
        for summary_line in standalone_summaries:
            product_id = summary_line.product_id
            if not product_id:
                continue

            # Apply vendor MOQ: if demand is below MOQ, order at least vendor_moq.
            # (Mirrors the base module's MOQ check; no wh_sharing_percentage here
            #  since standalone lines have no backing reorder_line to prorate against.)
            if summary_line.vendor_moq > 0 and summary_line.demanded_qty <= summary_line.vendor_moq:
                quantity = summary_line.vendor_moq
            else:
                quantity = (
                    summary_line.to_be_ordered_in_purchase_uom
                    if summary_line.to_be_ordered_in_purchase_uom > 0
                    else summary_line.order_qty
                )
            if not quantity:
                continue

            date_planned = self._get_date_planned(partner, product_id, quantity, datetime.today())
            product_lang = product_id.with_prefetch().with_context(
                lang=partner.lang,
                partner_id=partner.id,
            )

            company_id = self.company_id or False

            if company_id:
                ps_info = product_id.seller_ids.filtered(
                    lambda x, pid=partner.id, cid=company_id: (
                            x.partner_id.id == pid
                            and x.company_id == cid
                            and x.currency_id == cid.currency_id
                    )
                )
            else:
                ps_info = product_id.seller_ids.filtered(
                    lambda x, pid=partner.id: x.partner_id.id == pid
                )

            ps_info_have_min_qty = ps_info.filtered(lambda x: x.reorder_minimum_quantity > 0)
            if ps_info_have_min_qty:
                ps_info_have_min_qty = ps_info_have_min_qty.filtered(
                    lambda x, qty=quantity: x.reorder_minimum_quantity <= qty
                ).sorted(key=lambda x: x.reorder_minimum_quantity, reverse=True)
                if ps_info_have_min_qty:
                    ps_info = ps_info_have_min_qty[0]

            ps_info = ps_info and len(ps_info) > 1 and ps_info[0] or ps_info
            price_unit = ps_info.price if ps_info else product_id.standard_price

            name = product_lang.display_name
            if product_lang.description_purchase:
                name += '\n' + product_lang.description_purchase

            taxes = product_id.supplier_taxes_id
            taxes_id = fpos.map_tax(taxes) if fpos else taxes
            if taxes_id:
                taxes_id = taxes_id.filtered(lambda x: x.company_id.id == company_for_tax.id)

            po_line_vals.append((0, 0, {
                'name': name,
                'product_id': product_id.id,
                'product_qty': round(quantity),
                'price_unit': price_unit,
                'product_uom': (
                    product_id.uom_po_id.id
                    if summary_line.to_be_ordered_in_purchase_uom > 0
                    else product_id.uom_id.id
                ),
                'date_planned': date_planned,
                'taxes_id': [(6, 0, taxes_id.ids)],
            }))

        return po_line_vals

    def action_create_reorder_manufacturing_orders(self):
        """Opens the wizard to select a warehouse for creating manufacturing orders."""
        self.ensure_one()
        wizard = self.env['advance.reorder.mrp.wizard'].create({
            'reorder_process_id': self.id,
        })
        return {
            'name': _('Select Warehouse To Create Manufacturing Order'),
            'type': 'ir.actions.act_window',
            'res_model': 'advance.reorder.mrp.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
            'context': dict(self.env.context),
        }

    def create_manufacturing_orders(self, warehouse_id):
        """Creates manufacturing orders from verified production summary lines."""
        self.ensure_one()
        if self.state != 'verified':
            raise UserError(_('Manufacturing orders can only be created from a verified reorder process.'))
        production_summaries = self.summary_ids.filtered(
            lambda summary: summary.order_action == 'production' and summary.order_qty > 0)
        if self.production_ids:
            raise UserError(_('Manufacturing orders have already been created for this reorder process.'))

        Production = self.env['mrp.production'].with_user(self.user_id).with_company(self.company_id)
        mo_vals_list = []

        for config in self.config_ids:
            production_summaries = production_summaries.filtered(
                lambda x: x.warehouse_group_id.id == config.warehouse_group_id.id)

            mo_bom_wise_data = self._get_bom_wise_mo_count(config.warehouse_group_id,
                                                           production_summaries.mapped('product_id'))

            mo_vals_list.extend(
                self._prepare_manufacturing_order_vals_from_summary(production_summaries, warehouse_id, mo_bom_wise_data)
            )

        if not mo_vals_list:
            raise UserError(_(
                'No manufacturing orders to create. '
            ))

        Production.create(mo_vals_list)
        return True

    def _prepare_manufacturing_order_vals_from_summary(self, production_summaries, warehouse, mo_bom_wise_data):
        """Prepares manufacturing order values from production summary lines based on BOM ratio demand."""
        mo_vals_list = []
        for summary_line in production_summaries:
            product = summary_line.product_id
            picking_type = warehouse.manu_type_id
            if not picking_type:
                raise UserError(_(
                    'No manufacturing operation type configured for warehouse %s.',
                    warehouse.display_name,
                ))

            if self.calculate_demand_based_on == 'without_bom':
                bom_wise_demand = self._get_bom_wise_demand_by_mo_ratio(
                    product,
                    summary_line.order_qty,
                    mo_bom_wise_data=mo_bom_wise_data,
                )

            if not bom_wise_demand:
                default_bom = self._get_product_bom(product)
                bom_wise_demand = [(default_bom, summary_line.order_qty)] if default_bom else []

            if not bom_wise_demand:
                _logger.warning(
                    "No BOM found for product %s (ID: %s).",
                    product.display_name,
                    product.id,
                )

            for bom, qty in bom_wise_demand:
                mo_vals_list.append({
                    'product_id': product.id,
                    'product_qty': qty,
                    'bom_id': bom.id,
                    'picking_type_id': picking_type.id,
                    'company_id': self.company_id.id,
                    'origin': self.name,
                    'reorder_process_id': self.id,
                })

        return mo_vals_list

    def action_production_count(self):
        """Opens the linked manufacturing orders from the reorder."""
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('mrp.mrp_production_action')
        productions = self.mapped('production_ids')
        if len(productions) > 1:
            action['domain'] = [('id', 'in', productions.ids)]
        elif productions:
            form_view = [(self.env.ref('mrp.mrp_production_form_view').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [
                    (state, view) for state, view in action['views'] if view != 'form'
                ]
            else:
                action['views'] = form_view
            action['res_id'] = productions.id
        return action
