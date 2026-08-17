# -*- coding: utf-8 -*-
import logging
from statistics import mean
from types import SimpleNamespace

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class AdvanceReorderProductRealDemand(models.Model):
    _name = 'advance.reorder.product.real.demand'
    _description = 'Product-Wise Real Demand'
    _order = 'create_date desc, id desc'
    _check_company_auto = True
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Name',
        help='Reorder number',
        required=True,
        readonly=True,
        default=lambda self: _('New'),
        copy=False,
    )
    reorder_date = fields.Datetime(
        string='Reorder date',
        help='Reorder date',
        default=fields.Datetime.now,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Responsible',
        default=lambda self: self.env.user,
        help='Responsible user',
    )
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('inprogress', 'InProgress'),
            ('verified', 'Verified'),
            ('waiting_for_approval', 'Waiting for Approval'),
            ('approved', 'Approved'),
            ('reject', 'Rejected'),
            ('done', 'Done'),
            ('no_data', 'No Data'),
            ('cancel', 'Cancel'),
        ],
        default='draft',
        string='Status',
        help='To identify process status',
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )
    vendor_selection_strategy = fields.Selection(
        [
            ('sequence', 'Sequence Of Vendor'),
            ('price', 'Cheapest vendor'),
            ('delay', 'Quickest vendor'),
            ('specific_vendor', 'Specific vendor'),
            ('on_po_creation', 'On PO Creation'),
        ],
        string='Vendor selection strategy',
        default='sequence',
        help=(
            'This field is useful when purchase order is created from order points '
            'that time system checks about the vendor which is suitable for placing an order '
            'according to need. Whether quickest vendor, cheapest vendor or specific vendor is suitable '
            'for the product'
        ),
    )
    vendor_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        help='Set the vendor to whom you want to place an order',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        check_company=True,
    )
    bom_id = fields.Many2one(
        'mrp.bom',
        string='BOM',
        check_company=True,
    )
    calculated_lead_days = fields.Float(
        string='Calculated Lead Days',
        readonly=True,
        help='Recursive critical-path lead time for the selected product.',
    )
    component_line_ids = fields.One2many(
        'advance.reorder.product.component.line',
        'real_demand_id',
        string='Component Lines',
        readonly=True,
    )
    demand_line_ids = fields.One2many(
        'advance.reorder.product.real.demand.line',
        'real_demand_id',
        string='Demand Lines',
        readonly=True,
    )
    summary_ids = fields.One2many(
        'advance.reorder.product.real.demand.summary',
        'real_demand_id',
        string='Summary',
        readonly=True,
    )
    buffer_security_days = fields.Integer(
        string='Coverage days',
        help=(
            'Place order for next x days, system will generate demands for next x '
            'days after order transit time'
        ),
    )
    generate_demand_with = fields.Selection(
        [
            ('history_sales', 'History Sales'),
            ('forecast_sales', 'Forecast Sales'),
        ],
        string='Demand calculation by',
        help='Demand generate based on past sales or forecasted sales',
        default='history_sales',
    )
    sales_start_date = fields.Date(string='From date')
    sales_end_date = fields.Date(string='End date')
    reorder_demand_growth = fields.Float(
        string='Expected growth (%)',
        help='Add percentage value if you want to calculate demand with growth',
    )

    @api.onchange('product_id')
    def _onchange_product_id(self):
        self.bom_id = False
        self.calculated_lead_days = 0.0
        self.component_line_ids = [(5, 0, 0)]
        self.demand_line_ids = [(5, 0, 0)]
        self.summary_ids = [(5, 0, 0)]
        self.state = 'draft'

    @api.onchange('vendor_selection_strategy')
    def _onchange_vendor_selection_strategy(self):
        if self.vendor_selection_strategy != 'specific_vendor':
            self.vendor_id = False

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.name == _('New'):
                record.name = _('PWD-%s') % record.id
        return records

    # -------------------------------------------------------------------------
    # Lead time / component loading
    # -------------------------------------------------------------------------

    def _get_product_bom(self, product):
        self.ensure_one()
        return (
            product.reorder_bom_id
            or product.get_default_bom(company_id=self.company_id.id)
            or self.env['mrp.bom']
        )

    def _get_purchase_lead_days(self, product, subcontractors=False):
        self.ensure_one()
        purchase_lines = self.env['purchase.order.line'].search([
            ('product_id', '=', product.id),
            ('order_id.state', 'in', ('purchase', 'done')),
            ('order_id.company_id', '=', self.company_id.id),
        ])
        lead_days = []
        for purchase_line in purchase_lines:
            if subcontractors and purchase_line.order_id.partner_id not in subcontractors:
                continue
            receipt_dates = purchase_line.move_ids.filtered(
                lambda move: move.state == 'done' and move.date
            ).mapped('date')
            if receipt_dates and purchase_line.order_id.date_order:
                delay = (
                    min(receipt_dates) - purchase_line.order_id.date_order
                ).total_seconds() / 86400
                if delay >= 0:
                    lead_days.append(delay)
        if lead_days:
            return mean(lead_days)

        sellers = product.seller_ids
        if subcontractors:
            sellers = sellers.filtered(lambda seller: seller.partner_id in subcontractors)
        if sellers:
            return mean(sellers.mapped('delay'))
        return 0.0

    def _get_procurement_method(self, product, bom):
        if bom and bom.type == 'subcontract':
            return 'subcontract'
        if bom:
            return 'manufacture'
        return 'purchase'

    def _get_own_lead_days(self, product, bom, procurement_method):
        if procurement_method == 'purchase':
            return self._get_purchase_lead_days(product)
        if procurement_method == 'subcontract':
            return self._get_purchase_lead_days(product, bom.subcontractor_ids)
        return (bom.produce_delay if bom else 0.0) or 0.0

    def _build_lead_tree(self, product, required_qty, parent_product=False, level=0, ancestors=None):
        self.ensure_one()
        ancestors = set(ancestors or set())
        if product.id in ancestors:
            raise ValidationError(_(
                'Circular BOM detected while calculating lead time for "%s".'
            ) % product.display_name)

        bom = self._get_product_bom(product)
        procurement_method = self._get_procurement_method(product, bom)
        node = {
            'product': product,
            'parent_product': parent_product,
            'bom': bom,
            'required_qty': required_qty,
            'level': level,
            'procurement_method': procurement_method,
            'production_lead_days': (bom.produce_delay if bom else 0.0) or 0.0,
            'purchase_lead_days': 0.0,
            'subcontract_lead_days': 0.0,
            'children': [],
            'critical_children': [],
        }
        next_ancestors = ancestors | {product.id}

        if procurement_method == 'purchase':
            node['purchase_lead_days'] = self._get_purchase_lead_days(product)
            node['calculated_lead_days'] = node['purchase_lead_days']
            return node

        if procurement_method == 'subcontract':
            node['subcontract_lead_days'] = self._get_own_lead_days(
                product, bom, procurement_method
            )

        if bom:
            bom_qty = bom.product_qty or 1.0
            for bom_line in bom.bom_line_ids.filtered('product_id'):
                component_qty = required_qty * (bom_line.product_qty / bom_qty)
                node['children'].append(self._build_lead_tree(
                    bom_line.product_id,
                    component_qty,
                    parent_product=product,
                    level=level + 1,
                    ancestors=next_ancestors,
                ))

        max_child_lead = max(
            (child['calculated_lead_days'] for child in node['children']),
            default=0.0,
        )
        node['critical_children'] = [
            child for child in node['children']
            if child['calculated_lead_days'] == max_child_lead and max_child_lead > 0.0
        ]
        own_lead_days = (
            node['subcontract_lead_days']
            if procurement_method == 'subcontract'
            else node['production_lead_days']
        )
        node['calculated_lead_days'] = own_lead_days + max_child_lead
        return node

    def _mark_critical_path(self, node):
        node['is_critical_path'] = True
        for child in node['critical_children']:
            self._mark_critical_path(child)

    def _flatten_tree(self, node, line_vals):
        line_vals.append({
            'product_id': node['product'].id,
            'calculated_lead_days': node['calculated_lead_days'],
        })
        for child in node['children']:
            self._flatten_tree(child, line_vals)

    def action_load_components(self):
        for record in self:
            if not record.product_id:
                raise UserError(_('Please select a product before loading components.'))

            root_node = record._build_lead_tree(record.product_id, required_qty=1.0)
            record._mark_critical_path(root_node)
            line_vals = []
            record._flatten_tree(root_node, line_vals)
            if not line_vals:
                raise UserError(_(
                    'No component structure could be loaded for "%s".'
                ) % record.product_id.display_name)

            record.component_line_ids.unlink()
            record.demand_line_ids.unlink()
            record.summary_ids.unlink()
            record.write({
                'bom_id': root_node['bom'].id,
                'calculated_lead_days': root_node['calculated_lead_days'],
                'component_line_ids': [(0, 0, values) for values in line_vals],
            })
        return True

    # -------------------------------------------------------------------------
    # Demand calculation (same logic as Reorder with Real Demand)
    # -------------------------------------------------------------------------

    def _get_demand_configs(self):
        """Build warehouse-group configs using calculated lead days."""
        self.ensure_one()
        warehouse_groups = self.env['stock.warehouse.group'].search([
            ('company_id', '=', self.company_id.id),
        ])
        if not warehouse_groups:
            raise UserError(_(
                'Please configure at least one Warehouse Group for company "%s".'
            ) % self.company_id.display_name)

        reorder_date = fields.Datetime.to_datetime(self.reorder_date).date()
        lead_days = int(round(self.calculated_lead_days)) or 1
        arrival_offset = lead_days - 1 if lead_days > 0 else lead_days
        order_arrival_date = reorder_date + relativedelta(days=arrival_offset)
        coverage_start = order_arrival_date + relativedelta(days=1)
        buffer_days = self.buffer_security_days
        coverage_offset = buffer_days - 1 if buffer_days > 0 else buffer_days
        coverage_end = coverage_start + relativedelta(days=coverage_offset)

        configs = []
        for warehouse_group in warehouse_groups:
            if not warehouse_group.warehouse_ids:
                continue
            configs.append(SimpleNamespace(
                warehouse_group_id=warehouse_group,
                vendor_lead_days=lead_days,
                order_date=reorder_date,
                order_arrival_date=order_arrival_date,
                advance_stock_start_date=coverage_start,
                advance_stock_end_date=coverage_end,
            ))
        if not configs:
            raise UserError(_(
                'Warehouse Groups must contain at least one warehouse before validating demand.'
            ))
        return configs

    def get_history_sales(self, products, warehouses, start_date, end_date):
        """Same as Reorder with Real Demand history sales query."""
        start_date = start_date.strftime('%Y-%m-%d')
        end_date = end_date and end_date.strftime('%Y-%m-%d')
        query = """
            Select product_id, product_name,
                sum(sales) as sales,
                sum(sales_return) as sales_return,
                sum(total_sales) as total_sales,
                sum(ads) as ads
            from get_products_sales_warehouse_group_wise('%s', '%s', '%s', '%s', '%s', '%s')
            group by product_id, product_name
        """ % ('{}', products, '{}', warehouses, start_date, end_date)
        self._cr.execute(query)
        return self._cr.dictfetchall()

    def get_forecast_sales(self, products, warehouses, config):
        """Same as Reorder with Real Demand forecast sales query."""
        query = """
            Select * from get_reorder_forecast_data('%s', '%s', '%s', '%s', '%s', '%s')
        """ % (
            str(config.order_date),
            str(config.order_arrival_date),
            str(config.advance_stock_start_date),
            str(config.advance_stock_end_date),
            products,
            warehouses,
        )
        self._cr.execute(query)
        return self._cr.dictfetchall()

    def get_sales_data(self, config, line_product_ids, is_sfg=False):
        """Same as extended Reorder with Real Demand sales data selection."""
        sales_driven_products = line_product_ids
        if not is_sfg:
            sales_driven_products = line_product_ids.filtered(
                lambda pr: pr.is_kit_component or pr.demand_planning_type in ('sales_driven', 'combined')
            )
        products = sales_driven_products and set(sales_driven_products.ids) or {}
        if not products:
            return []
        warehouses = (
            config.warehouse_group_id
            and set(config.warehouse_group_id.warehouse_ids.ids)
            or {}
        )
        if self.generate_demand_with == 'history_sales':
            return self.get_history_sales(
                products, warehouses, self.sales_start_date, self.sales_end_date
            )
        return self.get_forecast_sales(products, warehouses, config)

    def get_production_data(self, config, line_product_ids):
        """Same as extended Reorder with Real Demand production data."""
        if not self.sales_start_date or not self.sales_end_date or not line_product_ids:
            return []

        production_driven_products = line_product_ids.filtered(
            lambda pr: pr.demand_planning_type != 'sales_driven'
        )
        products = set(production_driven_products.ids) if production_driven_products else set()
        if not products:
            return []

        warehouses = set(config.warehouse_group_id.warehouse_ids.ids or [])
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
        """Same as extended Reorder with Real Demand resupply data."""
        if not self.sales_start_date or not self.sales_end_date or not line_product_ids:
            return []
        if not self.company_id.use_subcontracting_for_demand:
            return []

        production_driven_products = line_product_ids.filtered(
            lambda pr: pr.is_kit_component or pr.demand_planning_type != 'sales_driven'
        )
        products = set(production_driven_products.ids) if production_driven_products else set()
        if not products:
            return []

        warehouses = set(config.warehouse_group_id.warehouse_ids.ids or [])
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

    def get_scrap_data(self, config, line_product_ids):
        """Same as extended Reorder with Real Demand scrap data."""
        if not self.sales_start_date or not self.sales_end_date or not line_product_ids:
            return []
        if not self.company_id.use_scrap_for_demand:
            return []

        products = set(line_product_ids.ids)
        if not products:
            return []

        warehouses = set(config.warehouse_group_id.warehouse_ids.ids or [])
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

    def _get_kit_component(self, products):
        """Same as extended Reorder with Real Demand kit component expansion."""
        component_products = self.env['product.product']
        for product in products:
            bom = self._get_product_bom(product)
            if bom:
                component_products |= bom.bom_line_ids.mapped('product_id')
        return component_products

    def _merge_ads_data(self, sales_data, production_data, resupply_data, scrap_data):
        """Same as extended Reorder with Real Demand ADS merge."""
        if not any((sales_data, production_data, resupply_data, scrap_data)):
            return []

        sales_map = {row['product_id']: row for row in sales_data}
        production_map = {row['product_id']: row for row in production_data}
        resupply_map = {row['product_id']: row for row in resupply_data}
        scrap_map = {row['product_id']: row for row in scrap_data}
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
                'ads': sum(ads_values) if ads_values else 0.0,
            })
        return merged

    def _get_warehouse_qty_summary(self, product, warehouses):
        """Same warehouse free/incoming summary as Reorder with Real Demand."""
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

    def get_stock_move(self, product, config):
        """Same incoming move lookup as Reorder with Real Demand."""
        stock_location_ids = config.warehouse_group_id.warehouse_ids.mapped('lot_stock_id').ids
        return self.env['stock.move'].search([
            ('product_id', '=', product.id),
            ('state', 'not in', ['draft', 'cancel', 'done']),
            ('location_dest_id', 'in', stock_location_ids),
        ]).ids

    def _rounding_demand_quantity(self, quantity):
        """Same rounding as Reorder with Real Demand."""
        self.ensure_one()
        round_qty = self.company_id.reorder_round_quantity
        rounding_method = self.company_id.reorder_rounding_method
        if not round_qty or quantity == 0.0:
            return quantity
        if quantity % round_qty == 0.0:
            return quantity
        if rounding_method == 'round_up':
            return (quantity + round_qty) - (quantity % round_qty)
        if rounding_method == 'round_down':
            return quantity - (quantity % round_qty)
        return quantity

    def _prepare_base_line_vals(self, config, product):
        """Prepare base demand line values for one product/warehouse group."""
        wh_summary = self._get_warehouse_qty_summary(
            product, config.warehouse_group_id.warehouse_ids
        )
        return {
            'warehouse_group_id': config.warehouse_group_id.id,
            'product_id': product.id,
            'available_stock': wh_summary['available'],
            'incoming_qty': wh_summary['incoming'],
        }

    def prepare_reorder_line_vals(self, config, demand_data, is_mto_route=False):
        """Same demand quantity calculation as Reorder with Real Demand."""
        vals = []
        reorder_demand_growth = (
            self.reorder_demand_growth and self.reorder_demand_growth / 100 or 0.0
        )

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
            demand_qty = round(
                0 if stock_after_transit > expected_sales
                else expected_sales - stock_after_transit,
                2,
            )
            demand_adjustment_qty = self._rounding_demand_quantity(demand_qty)

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

            existing_line = self.demand_line_ids.filtered(
                lambda line: (
                    line.product_id == product
                    and line.warehouse_group_id == config.warehouse_group_id
                )
            )
            if existing_line:
                existing_line.write(reorder_line_vals)
                continue
            vals.append((0, 0, reorder_line_vals))
        return vals

    def action_reorder_confirm(self):
        """
        Same demand generation flow as Reorder with Real Demand Validate:
        merge sales/production/resupply/scrap ADS and create demand lines.
        """
        self.ensure_one()
        vals = []
        configs = self._get_demand_configs()
        product_ids = self.product_id

        for config in configs:
            line_product_ids = product_ids.filtered(lambda product: not product.is_kit_product)
            kit_product_ids = product_ids.filtered(lambda product: product.is_kit_product)
            line_product_ids |= self._get_kit_component(kit_product_ids)

            sales_data = self.get_sales_data(config, line_product_ids)
            production_data = []
            scrap_data = []
            resupply_data = []
            if self.generate_demand_with == 'history_sales' and line_product_ids:
                production_data = self.get_production_data(config, line_product_ids)
                scrap_data = self.get_scrap_data(config, line_product_ids)
                resupply_data = self.get_resupply_data(config, line_product_ids)

            demand_data = self._merge_ads_data(
                sales_data, production_data, resupply_data, scrap_data
            )
            vals.extend(self.prepare_reorder_line_vals(config, demand_data, is_mto_route=False))

        self.demand_line_ids.unlink()
        self.summary_ids.unlink()
        write_vals = {'state': 'no_data'}
        if vals:
            write_vals = {
                'demand_line_ids': vals,
                'state': 'inprogress',
            }
        self.write(write_vals)
        return True

    def action_validate(self):
        """Validate button: calculate demand and move to In Progress."""
        for record in self:
            if not record.component_line_ids:
                raise UserError(_('Please load components before validating demand.'))
            if record.generate_demand_with == 'history_sales' and (
                not record.sales_start_date or not record.sales_end_date
            ):
                raise UserError(_('Please set From date and End date before validating demand.'))
            if not record.buffer_security_days:
                raise UserError(_('Please set Coverage days before validating demand.'))
            record.action_reorder_confirm()
        return True

    def _filter_supplier_info_by_moq(self, ps_info, total_demand):
        """Same supplier MOQ filter as Reorder with Real Demand."""
        ps_info_have_min_qty = ps_info.filtered(lambda info: info.reorder_minimum_quantity > 0)
        if ps_info_have_min_qty:
            ps_info_have_min_qty = ps_info_have_min_qty.filtered(
                lambda info: info.reorder_minimum_quantity <= total_demand
            ).sorted(key=lambda info: info.reorder_minimum_quantity, reverse=True)
            if ps_info_have_min_qty:
                return ps_info_have_min_qty[0]
        if ps_info and len(ps_info) > 1:
            return ps_info[0]
        return ps_info

    def _get_product_supplier_info(self, product, company_id, total_demand):
        """Same supplier resolution as Reorder with Real Demand."""
        self.ensure_one()
        partner = False
        if self.vendor_selection_strategy == 'specific_vendor':
            partner = self.vendor_id
            if not partner:
                return self.env['product.supplierinfo']
        elif self.vendor_selection_strategy == 'on_po_creation':
            return self.env['product.supplierinfo']
        else:
            seller = product.with_context({
                'sort_by': self.vendor_selection_strategy,
                'op_company': company_id or self.company_id or self.env.company,
            })._select_seller(quantity=total_demand)
            if not seller or not seller.partner_id:
                return self.env['product.supplierinfo']
            partner = seller.partner_id

        if company_id:
            ps_info = product.seller_ids.filtered(
                lambda info: info.partner_id == partner and (
                    info.company_id == company_id or not info.company_id
                )
            )
        else:
            ps_info = product.seller_ids.filtered(lambda info: info.partner_id == partner)
        return self._filter_supplier_info_by_moq(ps_info, total_demand)

    def _get_purchase_details(self, product, company_id, demanded_qty, order_qty):
        """Same purchase MOQ/qty/price details as Reorder with Real Demand."""
        vendor_moq = 0
        purchase_qty = 0
        price = product.standard_price or 0.0
        ps_info = self._get_product_supplier_info(product, company_id, demanded_qty)
        if ps_info:
            vendor_moq = ps_info.reorder_minimum_quantity
            purchase_qty = round(
                product.uom_id._compute_quantity(qty=order_qty, to_unit=product.uom_po_id)
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
        """Same action selection as Reorder with Real Demand."""
        route_names = set(product.route_ids.mapped('name'))
        if {'Manufacture', 'Replenish on Order (MTO)'} <= route_names:
            return 'production'
        if {'Buy', 'Replenish on Order (MTO)'} <= route_names:
            return 'purchase'
        if product.reorder_product_classification in ('finished_good', 'semi_finished_good'):
            return 'production'
        return 'purchase'

    def _get_summary_vals_by_product(self, summary_vals):
        return {
            command[2]['product_id']: command[2]
            for command in summary_vals
            if command[0] == 0 and command[2].get('product_id')
        }

    def _prepare_net_demand_summary_line_vals(
            self, product, order_qty, demanded_qty, order_action, warehouse_group, company_id=None
    ):
        """Same summary line preparation as Reorder with Real Demand."""
        weight = max(product.weight or 1.0, 1.0)
        line_volume = order_qty * (product.volume or 0.0) * weight
        company_id = company_id or self.env.company
        vendor_moq = 0
        purchase_qty = 0
        if order_action == 'purchase':
            vendor_moq, purchase_qty, _price = self._get_purchase_details(
                product, company_id, demanded_qty, order_qty
            )
        return {
            'product_id': product.id,
            'demanded_qty': demanded_qty,
            'vendor_moq': vendor_moq,
            'order_qty': round(order_qty),
            'total_volume': line_volume,
            'to_be_ordered_in_purchase_uom': purchase_qty,
            'order_action': order_action,
            'warehouse_group_id': warehouse_group.id if warehouse_group else False,
        }

    def prepare_reorder_summary_vals(self):
        """Create summary lines from demand lines, same as Reorder with Real Demand verify."""
        self.ensure_one()
        summary_vals = []
        for line in self.demand_line_ids:
            summary_by_product = self._get_summary_vals_by_product(summary_vals)
            if not line.product_id or line.product_id.id in summary_by_product:
                continue

            product_lines = self.demand_line_ids.filtered(
                lambda demand_line: demand_line.product_id.id == line.product_id.id
            )
            demanded_qty = sum(product_lines.mapped('demand_adjustment_qty'))
            if demanded_qty <= 0:
                continue

            line_vals = self._prepare_net_demand_summary_line_vals(
                product=line.product_id,
                order_qty=demanded_qty,
                demanded_qty=demanded_qty,
                order_action=self._get_order_action(line.product_id),
                warehouse_group=line.warehouse_group_id,
                company_id=self.company_id,
            )
            summary_vals.append((0, 0, line_vals))
        return summary_vals

    def action_verify(self):
        """Verify button: create summary lines with Action, then set state to verified."""
        for record in self:
            if not record.demand_line_ids:
                raise UserError(_('Please validate demand before verifying.'))
            summary_vals = record.prepare_reorder_summary_vals()
            record.summary_ids.unlink()
            write_vals = {'state': 'no_data'}
            if summary_vals:
                write_vals = {
                    'summary_ids': summary_vals,
                    'state': 'verified',
                }
            record.write(write_vals)
        return True
