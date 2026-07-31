# -*- coding: utf-8 -*-
import logging
from collections import defaultdict
from datetime import datetime
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

STOCK_DATA_TRANSACTIONS = (
    ('sales', 'sales_qty'),
    ('sales_return', 'sales_return_qty'),
)


class AdvanceReorderOrderProcess(models.Model):
    _inherit = 'advance.reorder.orderprocess'

    generate_demand_with = fields.Selection([('history_sales', 'Historical Sources'),
                                             ('forecast_sales', 'Forecast Sources')],
                                            string="Demand calculation by",
                                            help="Demand generate based on past sales or forecasted sales",
                                            default='history_sales')

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
    has_purchase_action_summary = fields.Boolean(
        string='Has Purchase Action Summary',
        compute='_compute_summary_action_flags',
    )
    has_production_action_summary = fields.Boolean(
        string='Has Production Action Summary',
        compute='_compute_summary_action_flags',
    )

    @api.onchange('product_ids')
    def _onchange_product_ids(self):
        self.product_ids._compute_demand_planning_type()

    def _compute_production_count(self):
        for record in self:
            record.production_count = len(record.production_ids)

    @api.depends('summary_ids', 'summary_ids.order_action')
    def _compute_summary_action_flags(self):
        for record in self:
            actions = set(record.summary_ids.mapped('order_action'))
            record.has_purchase_action_summary = 'purchase' in actions
            record.has_production_action_summary = 'production' in actions

    def get_sales_data(self, config, line_product_ids):
        """"DP"""
        """
              added by: Aastha Vora | On: Oct - 15 - 2024 | Task: 998
              use: use to get sales data on basis of demand_with.
        """
        sales_driven_products = line_product_ids.filtered(
            lambda pr: pr.demand_planning_type in ('sales_driven', 'combined'))
        products = sales_driven_products and set(sales_driven_products.ids) or {}
        warehouses = config.warehouse_group_id and set(config.warehouse_group_id.warehouse_ids.ids) or {}
        if self.generate_demand_with == 'history_sales':
            return self.get_history_sales(products, warehouses, self.sales_start_date, self.sales_end_date)
        else:
            return self.get_forecast_sales(products, warehouses, config)

    def get_production_data(self, config, line_product_ids):
        """"DP"""
        """Fetch MO consumption history for ADS calculation.

        Calls get_products_production_warehouse_group_wise (DB function) in the
        same way get_history_sales calls get_products_sales_warehouse_group_wise.

        Returns a list of dicts: product_id, product_name, consumed_qty, ads
        """
        if not self.sales_start_date or not self.sales_end_date:
            return []

        production_driven_products = line_product_ids.filtered(
            lambda pr: pr.demand_planning_type != 'sales_driven')
        products = set(production_driven_products.ids) if production_driven_products else set()
        if not products:
            return []

        warehouse_ids = self._get_warehouse_ids(config)
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
        if not self.sales_start_date or not self.sales_end_date:
            return []

        production_driven_products = line_product_ids.filtered(
            lambda pr: pr.demand_planning_type != 'sales_driven')
        products = set(production_driven_products.ids) if production_driven_products else set()
        if not products:
            return []

        warehouse_ids = self._get_warehouse_ids(config)
        warehouses = set(warehouse_ids) if warehouse_ids else {}
        start_date = self.sales_start_date.strftime('%Y-%m-%d')
        end_date = self.sales_end_date.strftime('%Y-%m-%d')

        query = """
            Select product_id, product_name,
                sum(consumed_qty) as resupply_qty,
                sum(ads) as ads
            from get_products_subcontracting_warehouse_group_wise('%s', '%s', '%s', '%s', '%s', '%s')
            group by product_id, product_name
        """ % ('{}', products, '{}', warehouses, start_date, end_date)
        self._cr.execute(query)
        return self._cr.dictfetchall()

    def get_scrap_data(self, config, line_product_ids, reorder_configuration):
        if not self.sales_start_date or not self.sales_end_date:
            return []

        if not any([
            reorder_configuration.consider_both,
            reorder_configuration.consider_production_rejection,
            reorder_configuration.consider_component_loss,
        ]):
            return []

        production_driven_products = line_product_ids.filtered(
            lambda p: p.demand_planning_type != 'sales_driven'
        )

        if reorder_configuration.consider_both:
            pass
        elif reorder_configuration.consider_production_rejection:
            production_driven_products = production_driven_products.filtered(
                lambda p: p.reorder_product_classification in (
                    'finished_good',
                    'semi_finished_good',
                )
            )
        elif reorder_configuration.consider_component_loss:
            production_driven_products = production_driven_products.filtered(
                lambda p: p.reorder_product_classification == 'raw_material'
            )

        products = set(production_driven_products.ids) if production_driven_products else set()
        if not products:
            return []

        warehouse_ids = self._get_warehouse_ids(config)
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
        """Merge sales, production, resupply and scrap data product-wise.
        ADS is calculated as the average of the available ADS values.
        """

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
            product = self.env['product.product'].browse(product_id)

            ads_values = []

            if product:
                # Include Sales ADS unless production driven
                if product.demand_planning_type != 'production_driven' and sales:
                    ads_values.append(sales.get('ads', 0.0))

                # Include Production, Resupply and Scrap ADS unless sales driven
                if product.demand_planning_type != 'sales_driven':
                    if production:
                        ads_values.append(production.get('ads', 0.0))
                    if resupply:
                        ads_values.append(resupply.get('ads', 0.0))
                    if scrap:
                        ads_values.append(scrap.get('ads', 0.0))

            avg_ads = sum(ads_values) / len(ads_values) if ads_values else 0.0

            merged.append({
                'product_id': product_id,
                'product_name': (
                        sales.get('product_name')
                        or production.get('product_name')
                        or resupply.get('product_name')
                        or scrap.get('product_name')
                ),
                'sales': sales.get('sales', 0.0),
                'sales_return': sales.get('sales_return', 0.0),
                'total_sales': sales.get('total_sales', 0.0),
                'consumed_qty': production.get('consumed_qty', 0.0),
                'resupply_qty': resupply.get('resupply_qty', 0.0),
                'scrap_qty': scrap.get('scrap_qty', 0.0),
                'ads': avg_ads,
            })
        return merged


    def action_reorder_confirm(self):
        """"DP"""
        """Override to merge sales and production consumption ADS per product planning type.

        For each config:
          1. Fetch sales data (via super's get_sales_data).
          2. Fetch production consumption data (via get_production_data).
          3. Merge both datasets per product demand_planning_type:
               - sales_driven     → sales data only (unchanged behaviour)
               - production_driven → production consumption ADS replaces sales ADS
               - combined         → combined ADS = sales_ads + production_ads
          4. Pass merged data to prepare_reorder_line_vals as usual.
        """
        self.check_configuration_product()
        vals = []
        reorder_vals = {}
        reorder_configuration = self.env['advance.reordering.settings'].search([], limit=1)
        resupply_data = []
        for config in self.config_ids:
            line_product_ids, kit_product_ids, kit_component_ratios = self._resolve_demand_line_products(
                self.product_ids,
            )
            sales_data = self.get_sales_data(config, line_product_ids)
            production_data = self.get_production_data(config, line_product_ids)
            if reorder_configuration.use_subcontracting:
                resupply_data = self.get_resupply_data(config, line_product_ids)
            scrap_data = self.get_scrap_data(config, line_product_ids, reorder_configuration)
            demand_data = self._merge_ads_data(sales_data, production_data, resupply_data,scrap_data)
            vals.extend(self.prepare_reorder_line_vals(config, demand_data, self.generate_demand_with))
        if not self.state == 'inprogress':
            reorder_vals = {'state': 'no_data'}
        vals and reorder_vals.update({'line_ids': vals, 'state': 'inprogress'})
        self.write(reorder_vals)
        self.invalidate_recordset(['line_ids'])
        component_data, by_product_data, warehouse_groups = self._collect_mrp_tab_requirements()
        self._generate_component_demand_lines(component_data, warehouse_groups)
        self._generate_by_product_lines(by_product_data)
        return True

    def _get_summary_lines_for_action(self, action):
        self.ensure_one()
        return self.summary_ids.filtered(lambda summary: summary.order_action == action)

    def _get_warehouse_ids(self, config):
        return config.warehouse_group_id.warehouse_ids.ids

    def _get_stock_data_date_range(self, config, generate_demand_with):
        if generate_demand_with == 'history_sales':
            return self.sales_start_date, self.sales_end_date
        return config.advance_stock_start_date, config.advance_stock_end_date

    def _get_stock_data_qty_map(self, config, product_ids, generate_demand_with):
        if not product_ids:
            return {}

        start_date, end_date = self._get_stock_data_date_range(config, generate_demand_with)
        if not start_date or not end_date:
            return {}

        start_date = start_date.strftime('%Y-%m-%d')
        end_date = end_date.strftime('%Y-%m-%d')
        warehouse_ids = self._get_warehouse_ids(config)
        products = set(product_ids)
        warehouses = set(warehouse_ids) if warehouse_ids else {}
        qty_map = defaultdict(dict)

        for transaction_type, field_name in STOCK_DATA_TRANSACTIONS:
            query = """
                SELECT product_id, COALESCE(SUM(product_qty), 0) AS product_qty
                FROM get_stock_data('{}', '%s', '{}', '%s', '%s', '%s', '%s')
                GROUP BY product_id
            """ % (products, warehouses, transaction_type, start_date, end_date)
            self._cr.execute(query)
            for row in self._cr.dictfetchall():
                qty_map[row['product_id']][field_name] = row['product_qty'] or 0.0

        return qty_map

    def _get_warehouse_qty_summary(self, product, warehouses):
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

    def _get_mo_sales_date_range(self):
        return self.sales_start_date, self.sales_end_date

    def _get_sales_data_map(self, sales_data):
        sales_data_map = {}
        for data in sales_data or []:
            product_id = data.get('product_id')
            if product_id:
                sales_data_map[product_id] = data
        return sales_data_map


    def get_stock_move(self, product, config):
        stock_location_ids = config.warehouse_group_id.warehouse_ids.mapped('lot_stock_id').ids
        stock_move_ids = self.env['stock.move'].search([('product_id', '=', product.id),
                                                        ('state', 'not in', ['draft', 'cancel', 'done']),
                                                        ('location_dest_id', 'in', stock_location_ids)])
        if product.reorder_product_classification != 'semi_finished_good':
            return stock_move_ids
        planning_type = product._get_effective_demand_planning_type()
        if planning_type == 'sales_driven':
            stock_move_ids = stock_move_ids.filtered(lambda x: x.location_id.usage != 'production')
        elif planning_type == 'production_driven':
            stock_move_ids = stock_move_ids.filtered(lambda x: x.location_id.usage == 'production')
        return stock_move_ids

    def _get_sales_planning_updates(self, config, product, stock_qty_map):
        stock_data = stock_qty_map.get(product.id, {})
        return {
            'sales_qty': stock_data.get('sales_qty', 0.0),
            'sales_return_qty': stock_data.get('sales_return_qty', 0.0),
        }


    def _prepare_base_line_vals(self, config, product):
        wh_summary = self._get_warehouse_qty_summary(
            product, config.warehouse_group_id.warehouse_ids
        )
        moves = self.get_stock_move(product, config)
        return {
            'warehouse_group_id': config.warehouse_group_id.id,
            'reorder_process_id': self.id,
            'product_id': product.id,
            'available_stock': wh_summary['available'] if wh_summary['available'] > 0 else 0.0,
            'incoming_qty': sum(moves.mapped('quantity')) if moves else 0.0,
            'stock_move_ids': [(6, 0, moves.ids)],
        }

    def _prepare_sales_driven_line_vals(self, config, data, generate_demand_with, net_on_hand, product, stock_qty_map):
        reorder_demand_growth = self.reorder_demand_growth and self.reorder_demand_growth / 100 or 0.0
        settings = self.env['advance.reordering.settings'].search([], limit=1)
        reorder_rounding_method = settings.reorder_rounding_method
        reorder_round_quantity = int(settings.reorder_round_quantity or 0)

        ads = data.get('ads', 0.0)

        if generate_demand_with == 'history_sales':
            ads = reorder_demand_growth and ads + (ads * reorder_demand_growth) or ads
            lead_days_demand = round(ads * config.vendor_lead_days, 2)
            expected_sales = self.buffer_security_days * ads
        else:
            lead_days_demand = data.get('lead_days_demand_stock', 0.0)
            expected_sales = data.get('expected_sales_stock', 0.0)

        transit_demand = lead_days_demand if net_on_hand > lead_days_demand else net_on_hand
        transit_demand = max(0.0, transit_demand)
        stock_after_transit = net_on_hand - transit_demand

        demand_qty = round(
            0 if stock_after_transit > expected_sales else expected_sales - stock_after_transit,
            2,
        )
        demand_adjustment_qty = demand_qty

        if reorder_round_quantity and demand_adjustment_qty % reorder_round_quantity != 0.0:
            if reorder_rounding_method == 'round_up' and demand_qty != 0.0:
                demand_adjustment_qty = (
                        (demand_qty + reorder_round_quantity) - (demand_qty % reorder_round_quantity)
                )
            elif reorder_rounding_method == 'round_down' and demand_qty != 0.0:
                demand_adjustment_qty = demand_qty - (demand_qty % reorder_round_quantity)

        line_vals = {
            'average_daily_sale': ads,
            'transit_time_sales': transit_demand,
            'stock_after_transit': stock_after_transit,
            'expected_sales': expected_sales,
            'demanded_qty': demand_qty,
            'demand_adjustment_qty': round(demand_adjustment_qty, 0),
        }
        line_vals.update(self._get_sales_planning_updates(config, product, stock_qty_map))
        return line_vals


    def _prepare_product_line_vals(
            self, config, product, product_id, demand_data_map,
            stock_qty_map, generate_demand_with,
    ):
        """Build demand line vals for one product using its demand_planning_type.

        - available_stock and incoming_qty are always computed from the warehouse.
        - The ADS / sales fields come from demand_data_map which has already been
          merged by _merge_ads_data() in action_reorder_confirm.
        - All products (FG, SFG, RM) now use the same sales-formula path;
          the distinction between sales/production/combined is handled upstream
          by the ADS merge before this method is called.
        """
        data = demand_data_map.get(product_id, {})
        line_vals = self._prepare_base_line_vals(config, product)
        net_on_hand = line_vals['available_stock']
        line_vals.update(self._prepare_sales_driven_line_vals(
            config, data, generate_demand_with, net_on_hand, product, stock_qty_map,
        ))
        # consumed_qty comes from production data merged upstream by _merge_ads_data().
        # It is non-zero only for production_driven / combined planning types.
        line_vals['consumed_qty'] = data.get('consumed_qty', 0.0)
        return line_vals

    def _resolve_demand_line_products(self, product_ids):
        kit_product_ids = set()
        kit_component_ratios = {}
        line_product_ids = set()

        for product_id in product_ids:
            product = self.env['product.product'].browse(product_id)
            if product.is_kit_product():
                if product.reorder_bom_id:
                    kit_product_ids.add(product_id)
                    kit_component_ratios[product_id] = product.get_kit_component_ratios()
                    line_product_ids.update(kit_component_ratios[product_id].keys())
            else:
                line_product_ids.add(product_id)
        return line_product_ids, kit_product_ids, kit_component_ratios

    def prepare_reorder_line_vals(self, config, demand_data, generate_demand_with):
        vals = []
        product_ids = self.product_ids.ids
        if not product_ids:
            return vals

        line_product_ids, kit_product_ids, kit_component_ratios = self._resolve_demand_line_products(
            product_ids,
        )
        demand_data_map = self._get_sales_data_map(demand_data)
        stock_qty_map = self._get_stock_data_qty_map(
            config, product_ids, generate_demand_with,
        )

        for product_id in line_product_ids:
            product = self.env['product.product'].browse(product_id)
            line_vals = self._prepare_product_line_vals(
                config, product, product_id, demand_data_map,
                stock_qty_map, generate_demand_with,
            )
            vals.append((0, 0, line_vals))

        return vals

    def _is_component_on_demand_line(self, product):
        return bool(self.line_ids.filtered(
            lambda line: line.product_id.id == product.id
                         and (line.demand_adjustment_qty or 0.0) > 0
                         and line.product_id.reorder_product_classification == 'semi_finished_good'
                         and line.product_id._get_effective_demand_planning_type() != 'sales_driven'
        ))

    def _should_add_rm_to_component_tab(self, component, parent_product):
        """Add RM to component tab based on parent product demand planning type."""
        if self._is_component_on_demand_line(component):
            return False
        if not parent_product:
            return True
        parent_classification = parent_product.reorder_product_classification
        if parent_classification == 'finished_good':
            return True
        if parent_classification == 'semi_finished_good':
            return parent_product._get_effective_demand_planning_type() != 'sales_driven'
        return True

    def _add_to_component_tab(self, component_data, product, qty):
        if product and qty > 0:
            component_data[product.id] += qty

    def _prepare_to_be_produced_line_vals(self, product, required_qty, warehouse_groups):
        warehouse_ids = warehouse_groups.mapped('warehouse_ids').ids
        warehouse_qty = self._get_warehouse_qty_summary(
            product, self.env['stock.warehouse'].browse(warehouse_ids)
        )
        return {
            'reorder_process_id': self.id,
            'product_id': product.id,
            'available_qty': warehouse_qty['available'],
            'required_qty': required_qty,
            'incoming_qty': warehouse_qty['incoming'],
            'net_demand': max(
                0.0,
                required_qty - warehouse_qty['available'] - warehouse_qty['incoming'],
            ),
        }

    def _create_or_update_to_be_produced_line(self, product, qty, warehouse_groups, produced_data):
        """Create a to-be-produced line when an SFG is found; update if the same SFG appears again."""
        ProducedLine = self.env['advance.reorder.to.be.produced.line']
        if not product or qty <= 0:
            return ProducedLine

        produced_data[product.id] += qty
        vals = self._prepare_to_be_produced_line_vals(product, qty, warehouse_groups)
        return ProducedLine.create(vals)

    def _add_sfg_bom_components_for_produced_demand(
            self, sfg_product, demand_qty, component_data, produced_data,
            warehouse_groups, by_product_data=None,
    ):
        """Add SFG BOM components to the component tab for a to-be-produced demand quantity."""
        if demand_qty <= 0:
            return

        bom = self._get_product_bom(sfg_product)
        if not bom:
            _logger.warning(
                'No BOM configured for SFG %s (ID: %s) during to-be-produced component routing.',
                sfg_product.display_name,
                sfg_product.id,
            )
            return

        bom_qty = bom.product_qty or 1.0
        for bom_line in bom.bom_line_ids:
            component = bom_line.product_id
            if not component:
                continue
            bom_required_qty = demand_qty * (bom_line.product_qty / bom_qty)
            classification = component.reorder_product_classification
            if classification == 'raw_material':
                if self._should_add_rm_to_component_tab(component, sfg_product):
                    self._add_to_component_tab(component_data, component, bom_required_qty)
            elif classification == 'semi_finished_good':
                self._collect_bom_by_products(component, bom_required_qty, by_product_data)
                self._create_or_update_to_be_produced_line(
                    component, bom_required_qty, warehouse_groups, produced_data,
                )
                self._add_sfg_bom_components_for_produced_demand(
                    component, bom_required_qty, component_data, produced_data,
                    warehouse_groups, by_product_data=by_product_data,
                )
            elif classification == 'finished_good':
                self._collect_bom_by_products(component, bom_required_qty, by_product_data)
                self._explode_bom_into_tabs(
                    component, bom_required_qty, component_data, produced_data,
                    by_product_data=by_product_data,
                    parent_product=component, warehouse_groups=warehouse_groups,
                )

    def _add_to_by_product_tab(self, by_product_data, product, qty):
        if product and qty > 0:
            by_product_data[product.id] += qty

    def _get_product_bom(self, product):
        return product.reorder_bom_id or (product.bom_ids[:1] if product.bom_ids else self.env['mrp.bom'])

    def _collect_bom_by_products(self, product, parent_mo_qty, by_product_data, bom=None):
        """Collect by-product qty using parent MO qty × BOM ratio.

        Case 1: parent_mo_qty = reorder line production_out_demand
        Case 2 (nested SFG): parent_mo_qty = propagated qty from FG explosion
        """
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
            self._add_to_by_product_tab(by_product_data, byproduct.product_id, byproduct_qty)

    def _explode_bom_into_tabs(
            self, product, quantity, component_data, produced_data,
            bom=None, by_product_data=None,
            parent_product=None, warehouse_groups=None,
    ):
        """Explode BOM using parent MO qty × BOM component ratios.

        Case 1 (direct component): required_qty = parent_mo_qty × (bom_line_qty / bom_qty)
        Case 2 (nested SFG): required_qty = root_mo_qty × fg_sfg_ratio × sfg_component_ratio
        achieved by propagating exploded qty through recursive calls.
        """
        bom = bom or self._get_product_bom(product)
        if not bom:
            _logger.warning(
                'No BOM configured for product %s (ID: %s) during MRP tab generation.',
                product.display_name,
                product.id,
            )
            return

        bom_parent = parent_product or product
        bom_qty = bom.product_qty or 1.0
        for bom_line in bom.bom_line_ids:
            component = bom_line.product_id
            if not component:
                continue
            bom_required_qty = quantity * (bom_line.product_qty / bom_qty)
            self._route_product_to_mrp_tabs(
                component, bom_required_qty, component_data, produced_data,
                to_be_produced=True, by_product_data=by_product_data,
                parent_product=bom_parent, warehouse_groups=warehouse_groups,
            )

    def _route_product_to_mrp_tabs(
            self, product, qty, component_data, produced_data,
            to_be_produced=False, by_product_data=None, parent_product=None,
            warehouse_groups=None,
    ):
        if not product or qty <= 0:
            return

        classification = product.reorder_product_classification

        if classification == 'raw_material':
            if self._should_add_rm_to_component_tab(product, parent_product):
                self._add_to_component_tab(component_data, product, qty)
        elif classification == 'semi_finished_good':
            if to_be_produced:
                if warehouse_groups is None:
                    warehouse_groups = self.config_ids.mapped('warehouse_group_id')
                line = self._create_or_update_to_be_produced_line(
                    product, qty, warehouse_groups, produced_data,
                )
                qty = line.net_demand
            self._collect_bom_by_products(product, qty, by_product_data)
            self._explode_bom_into_tabs(
                product, qty, component_data, produced_data,
                by_product_data=by_product_data,
                parent_product=product, warehouse_groups=warehouse_groups,
            )
        elif classification == 'finished_good':
            self._collect_bom_by_products(product, qty, by_product_data)
            self._explode_bom_into_tabs(
                product, qty, component_data, produced_data,
                by_product_data=by_product_data,
                parent_product=product, warehouse_groups=warehouse_groups,
            )

    def _process_finished_good_line(
            self, line, component_data, produced_data, by_product_data, warehouse_groups,
    ):
        source_qty = line.demand_adjustment_qty or 0.0
        if source_qty <= 0:
            return
        self._collect_bom_by_products(line.product_id, source_qty, by_product_data)
        self._explode_bom_into_tabs(
            line.product_id, source_qty, component_data, produced_data,
            by_product_data=by_product_data,
            parent_product=line.product_id, warehouse_groups=warehouse_groups,
        )

    def _process_semi_finished_good_line(
            self, line, component_data, produced_data, by_product_data,
            warehouse_groups=None,
    ):
        product = line.product_id

        if line.demand_adjustment_qty > 0:
            self._collect_bom_by_products(product, line.demand_adjustment_qty, by_product_data)
            self._explode_bom_into_tabs(
                product, line.demand_adjustment_qty, component_data, produced_data,
                by_product_data=by_product_data,
                parent_product=product, warehouse_groups=warehouse_groups,
            )

    def _process_raw_material_line(self, line, component_data):
        source_qty = line.demand_adjustment_qty
        if source_qty <= 0:
            return
        self._add_to_component_tab(component_data, line.product_id, source_qty)

    def _should_process_line_for_mrp_tabs(self, line):
        product = line.product_id
        if not product:
            return False
        classification = product.reorder_product_classification
        if classification == 'semi_finished_good':
            return product._get_effective_demand_planning_type() != 'sales_driven'
        return classification in ('finished_good', 'raw_material')

    def _collect_mrp_tab_requirements(self):
        self._clear_to_be_produced_lines()
        produced_data = defaultdict(float)
        component_data = defaultdict(float)
        by_product_data = defaultdict(float)
        warehouse_groups = self.config_ids.mapped('warehouse_group_id')

        for line in self.line_ids.filtered(self._should_process_line_for_mrp_tabs):
            product = line.product_id
            if product.is_kit_product():
                continue

            classification = product.reorder_product_classification
            if classification == 'finished_good':
                self._process_finished_good_line(
                    line, component_data, produced_data, by_product_data, warehouse_groups,
                )
            elif classification == 'semi_finished_good':
                self._process_semi_finished_good_line(
                    line, component_data, produced_data,
                    by_product_data=by_product_data, warehouse_groups=warehouse_groups,
                )
            elif classification == 'raw_material':
                self._process_raw_material_line(line, component_data)

        return dict(component_data), dict(by_product_data), warehouse_groups

    def _generate_component_demand_lines(self, component_data=None, warehouse_groups=None):
        self._clear_component_demand_lines()
        if component_data is None or warehouse_groups is None:
            component_data, _, warehouse_groups = self._collect_mrp_tab_requirements()
        if not component_data:
            return

        ComponentLine = self.env['advance.reorder.component.demand.line']
        warehouse_ids = warehouse_groups.mapped('warehouse_ids').ids

        for product_id, bom_required_qty in component_data.items():
            product = self.env['product.product'].browse(product_id)
            warehouse_qty = self._get_warehouse_qty_summary(
                product, self.env['stock.warehouse'].browse(warehouse_ids)
            )
            ComponentLine.create({
                'reorder_process_id': self.id,
                'product_id': product_id,
                'available_qty': warehouse_qty['available'],
                'required_qty': bom_required_qty,
                'incoming_qty': warehouse_qty['incoming'],
                'net_demand': max(
                    0.0,
                    bom_required_qty - warehouse_qty['available'],
                ),
            })

    def _generate_by_product_lines(self, by_product_data=None):
        self._clear_by_product_lines()
        if by_product_data is None:
            _, by_product_data, _ = self._collect_mrp_tab_requirements()
        if not by_product_data:
            return

        ByProductLine = self.env['advance.reorder.by.product.line']
        for product_id, quantity in by_product_data.items():
            if quantity <= 0:
                continue
            ByProductLine.create({
                'reorder_process_id': self.id,
                'product_id': product_id,
                'quantity': quantity,
            })

    def _clear_to_be_produced_lines(self):
        self.env['advance.reorder.to.be.produced.line'].search([
            ('reorder_process_id', '=', self.id),
        ]).unlink()

    def _clear_component_demand_lines(self):
        self.env['advance.reorder.component.demand.line'].search([
            ('reorder_process_id', '=', self.id),
        ]).unlink()

    def _clear_by_product_lines(self):
        self.env['advance.reorder.by.product.line'].search([
            ('reorder_process_id', '=', self.id),
        ]).unlink()

    def action_reorder_reset_to_draft(self):
        self._clear_component_demand_lines()
        self._clear_to_be_produced_lines()
        self._clear_by_product_lines()
        return super().action_reorder_reset_to_draft()

    def _get_reorder_line_product_ids(self):
        return set(self.line_ids.mapped('product_id').ids)

    def _get_summary_vals_by_product(self, summary_vals):
        return {
            command[2]['product_id']: command[2]
            for command in summary_vals
            if command[0] == 0 and command[2].get('product_id')
        }

    def _get_summary_company_id(self):
        config = self.config_ids[:1]
        if not config or not config.warehouse_group_id:
            return self.env.company
        warehouse = config.warehouse_group_id.warehouse_ids[:1]
        return warehouse.company_id if warehouse else self.env.company

    def _prepare_net_demand_summary_line_vals(self, product, order_qty, demanded_qty, order_action):
        weight = product.weight or 1.0
        if weight <= 0:
            weight = 1.0
        line_volume = order_qty * (product.volume or 0.0) * weight
        company_id = self._get_summary_company_id()
        vendor_moq = 0
        order_qty_in_purchase_uom = 0
        line_amount = round(order_qty) * (product.standard_price or 0.0)

        if order_action == 'purchase':
            ps_info = self._get_product_supplier_info(product, company_id, demanded_qty)
            order_qty_in_purchase_uom = round(
                product.uom_id._compute_quantity(qty=order_qty, to_unit=product.uom_po_id)
            )
            if ps_info:
                vendor_moq = ps_info.reorder_minimum_quantity
                if demanded_qty < ps_info.reorder_minimum_quantity:
                    order_qty_in_purchase_uom = ps_info.reorder_minimum_quantity
                if company_id and ps_info.currency_id != company_id.currency_id:
                    supplier_info_price = ps_info.currency_id._convert(
                        ps_info.price,
                        company_id.currency_id,
                        company_id,
                        self.reorder_date or fields.Date.context_today(self),
                        False,
                    )
                else:
                    supplier_info_price = ps_info.price
                line_amount = round(order_qty) * supplier_info_price

        return {
            'product_id': product.id,
            'demanded_qty': demanded_qty,
            'vendor_moq': vendor_moq,
            'order_qty': order_qty,
            'total_volume': line_volume,
            'to_be_ordered_in_purchase_uom': order_qty_in_purchase_uom,
            'order_action': order_action,
        }, line_volume, line_amount

    def _append_net_demand_summary_from_tab_lines(
            self,
            summary_vals,
            reorder_total_volume,
            reorder_total_amount,
            tab_lines,
            excluded_product_ids,
            order_action=None,
    ):
        """Append summary lines for tab products not already covered by reorder lines."""
        summary_by_product = self._get_summary_vals_by_product(summary_vals)
        total_volume = reorder_total_volume or 0.0
        total_amount = reorder_total_amount or 0.0

        for tab_line in tab_lines:
            product = tab_line.product_id
            if not product or product.id in excluded_product_ids:
                continue
            if product.id in summary_by_product:
                continue

            order_qty = round(tab_line.net_demand)
            if order_qty <= 0:
                continue

            demanded_qty = round(tab_line.required_qty) or order_qty
            action = order_action or product.get_reorder_order_action_from_routes()
            line_vals, line_volume, line_amount = self._prepare_net_demand_summary_line_vals(
                product, order_qty, demanded_qty, action,
            )
            summary_vals.append((0, 0, line_vals))
            summary_by_product[product.id] = line_vals
            total_volume += line_volume
            total_amount += line_amount

        return summary_vals, total_volume, total_amount

    def _append_to_be_produced_summary_vals(self, summary_vals, reorder_total_volume, reorder_total_amount):
        return self._append_net_demand_summary_from_tab_lines(
            summary_vals,
            reorder_total_volume,
            reorder_total_amount,
            self.to_be_produced_line_ids,
            self._get_reorder_line_product_ids(),
            order_action='production',
        )

    def _append_component_demand_summary_vals(self, summary_vals, reorder_total_volume, reorder_total_amount):
        return self._append_net_demand_summary_from_tab_lines(
            summary_vals,
            reorder_total_volume,
            reorder_total_amount,
            self.component_demand_line_ids,
            self._get_reorder_line_product_ids(),
        )

    def prepare_reorder_summary_vals(self):
        summary_vals, reorder_total_volume, reorder_total_amount = super().prepare_reorder_summary_vals()
        product_model = self.env['product.product']
        for command in summary_vals:
            if command[0] != 0:
                continue
            product_id = command[2].get('product_id')
            if not product_id:
                continue
            product = product_model.browse(product_id)
            command[2]['order_action'] = product.get_reorder_order_action_from_routes()

        summary_vals, reorder_total_volume, reorder_total_amount = self._append_to_be_produced_summary_vals(
            summary_vals, reorder_total_volume, reorder_total_amount,
        )
        return self._append_component_demand_summary_vals(
            summary_vals, reorder_total_volume, reorder_total_amount,
        )

    def get_vendor_product_mapping_dict(self):
        purchase_summaries = self._get_summary_lines_for_action('purchase')
        if not purchase_summaries:
            return {}
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
                    'op_company': self.user_id.company_id,
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
                    'op_company': self.user_id.company_id,
                })._select_seller(quantity=None)
                if not seller or not seller.partner_id:
                    continue
                partner_id = seller.partner_id.id
                vendor_product_dict.setdefault(partner_id, []).append(product.id)
        return vendor_product_dict

    def action_create_reorder_purchase_order(self):
        self.ensure_one()
        purchase_summaries = self._get_summary_lines_for_action('purchase')
        if not purchase_summaries:
            raise UserError(_('No summary lines are set to Generate Purchase Orders.'))

        if self.vendor_selection_strategy in ('on_po_creation', 'without_vendor'):
            return self.action_open_po_vendor_wizard()

        vendor_product_dict = self.get_vendor_product_mapping_dict()

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

    def action_open_po_vendor_wizard(self):
        self.ensure_one()
        purchase_summaries = self._get_summary_lines_for_action('purchase')
        if not purchase_summaries:
            raise UserError(_('No summary lines are set to Generate Purchase Orders.'))
        return super().action_open_po_vendor_wizard()

    def create_purchase_order(self, default_warehouse, warehouse_group_id, partner=None, summary_lines=None):
        summaries = summary_lines if summary_lines is not None else self.summary_ids
        summaries = summaries.filtered(lambda line: line.order_action == 'purchase')
        if not summaries:
            return True
        return super().create_purchase_order(
            default_warehouse,
            warehouse_group_id,
            partner=partner,
            summary_lines=summaries,
        )

    def _prepare_purchase_order_line_vals(self, fpos, warehouse_group_id, partner=None, summary_lines=None):
        """Override to handle summary lines that have no matching reorder line.

        In the extended module, summary lines can originate from:
          - Regular demand lines (in self.line_ids) — handled by super().
          - Component demand lines / to-be-produced lines that are not present
            in self.line_ids (e.g. raw-material components from BOM explosion).

        For lines WITH a matching reorder line, we delegate to super() so the
        base module logic (wh_sharing_percentage, moq, etc.) is unchanged.

        For lines WITHOUT a matching reorder line, we build the PO line vals
        directly from the summary line's order_qty / to_be_ordered_in_purchase_uom.
        """
        partner = partner or self.vendor_id
        if not partner:
            raise UserError(_('A vendor is required to prepare purchase order lines.'))

        summaries = summary_lines if summary_lines is not None else self.summary_ids
        company_for_tax = warehouse_group_id.warehouse_ids[:1].company_id or self.env.company

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

            company_id = warehouse_group_id.warehouse_ids[:1].company_id or False

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

    def _get_default_mo_warehouse(self):
        self.ensure_one()
        config = self.config_ids[:1]
        if not config or not config.default_warehouse_id:
            raise UserError(_('No default warehouse configured for manufacturing orders.'))
        return config.default_warehouse_id

    def _prepare_manufacturing_order_vals_from_summary(self, summary_line, warehouse):
        product = summary_line.product_id
        bom = self._get_product_bom(product)
        if not bom:
            raise UserError(_(
                'No BOM configured for product %s.',
                product.display_name,
            ))
        picking_type = warehouse.manu_type_id
        if not picking_type:
            raise UserError(_(
                'No manufacturing operation type configured for warehouse %s.',
                warehouse.display_name,
            ))
        return {
            'product_id': product.id,
            'product_qty': summary_line.order_qty,
            'bom_id': bom.id,
            'picking_type_id': picking_type.id,
            'company_id': warehouse.company_id.id,
            'origin': self.name,
            'reorder_process_id': self.id,
        }

    def action_create_manufacturing_orders(self):
        self.ensure_one()
        if self.state != 'verified':
            raise UserError(_('Manufacturing orders can only be created from a verified reorder process.'))
        production_summaries = self._get_summary_lines_for_action('production')
        if not production_summaries:
            raise UserError(_('No summary lines are set to Generate Production Orders.'))
        if self.production_ids:
            raise UserError(_('Manufacturing orders have already been created for this reorder process.'))

        warehouse = self._get_default_mo_warehouse()
        Production = self.env['mrp.production'].with_user(self.user_id).with_company(warehouse.company_id)
        mo_vals_list = []
        for summary_line in production_summaries:
            if summary_line.order_qty <= 0:
                continue
            mo_vals_list.append(
                self._prepare_manufacturing_order_vals_from_summary(summary_line, warehouse)
            )

        if not mo_vals_list:
            raise UserError(_(
                'No manufacturing orders to create. '
                'All production summary lines have zero quantity to order.'
            ))

        Production.create(mo_vals_list)
        return True

    def action_production_count(self):
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
