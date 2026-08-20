# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from statistics import mean
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

_logger = logging.getLogger(__name__)


class AdvanceReorderProductRealDemand(models.Model):
    _name = 'advance.reorder.product.wise.process'
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
        tracking=True,
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
        tracking=True,
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
        tracking=True,
        help='Set the vendor to whom you want to place an order',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        tracking=True,
        required=True,
        check_company=True,
    )
    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Product Template',
        related='product_id.product_tmpl_id',
        store=True,
    )
    reorder_product_classification = fields.Selection(related="product_id.reorder_product_classification",
                                                      string="Reorder Classification", store=True)
    bom_id = fields.Many2one(
        'mrp.bom',
        string='BOM',
        tracking=True,
        check_company=True,
        domain="[('type', 'in', ('normal', 'phantom', 'subcontract')), '|', ('company_id', '=', company_id), ('company_id', '=', False), '|', ('product_id', '=', product_id), '&', ('product_id', '=', False), ('product_tmpl_id', '=', product_tmpl_id)]",
    )
    component_line_ids = fields.One2many(
        'advance.reorder.product.component.line',
        'product_wise_reorder_id',
        string='Component Lines',
        copy=False,
        readonly=True,
    )
    demand_line_ids = fields.One2many(
        'advance.reorder.product.wise.process.line',
        'product_wise_reorder_id',
        string='Demand Lines',
        copy=False,
        readonly=True,
    )
    summary_ids = fields.One2many(
        'advance.reorder.product.wise.order.summary',
        'product_wise_reorder_id',
        string='Summary',
        copy=False,
    )

    purchase_ids = fields.One2many(
        'purchase.order',
        'product_wise_reorder_id',
        copy=False,
        string='Purchase Orders',
    )
    purchase_count = fields.Integer(
        string='Purchase order count',
        compute='_compute_purchase_count',
    )
    production_ids = fields.One2many(
        'mrp.production',
        'product_wise_reorder_id',
        string='Manufacturing Orders',
    )
    production_count = fields.Integer(
        string='Manufacturing order count',
        compute='_compute_production_count',
    )
    has_purchase_action_summary = fields.Boolean(
        string='Has Purchase Action',
        compute='_compute_summary_action_flags',
    )
    has_production_action_summary = fields.Boolean(
        string='Has Production Action',
        compute='_compute_summary_action_flags',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='company_id.currency_id',
        store=True,
    )
    reorder_amount = fields.Monetary(
        string='Reorder amount',
        help='Reorder amount will be calculated from the generated demands',
        copy=False,
    )
    minimum_reorder_amount = fields.Monetary(
        string='Min order amount',
        related='vendor_id.minimum_reorder_amount',
        help='Minimum reorder amount defined by vendors',
    )
    buffer_security_days = fields.Integer(
        string='Coverage days',
        help=(
            'Place order for next x days, system will generate demands for next x '
            'days after order transit time'
        ),
    )
    sales_start_date = fields.Date(string='From date')
    sales_end_date = fields.Date(string='End date')
    reorder_demand_growth = fields.Float(
        string='Expected growth (%)',
        help='Add percentage value if you want to calculate demand with growth',
    )

    @api.onchange('product_id', 'company_id')
    def _onchange_product_id(self):
        for record in self:
            record.bom_id = False
            if not record.product_id:
                continue
            bom_id = record._get_product_bom(record.product_id)
            if bom_id:
                record.bom_id = bom_id.id

    @api.onchange('vendor_selection_strategy')
    def _onchange_vendor_selection_strategy(self):
        for record in self:
            if record.vendor_selection_strategy != 'specific_vendor':
                record.vendor_id = False

    def _compute_purchase_count(self):
        for record in self:
            record.purchase_count = len(record.purchase_ids)

    def _compute_production_count(self):
        for record in self:
            record.production_count = len(record.production_ids)

    @api.depends('summary_ids', 'summary_ids.order_action')
    def _compute_summary_action_flags(self):
        for record in self:
            actions = set(record.summary_ids.mapped('order_action'))
            record.has_purchase_action_summary = 'purchase' in actions
            record.has_production_action_summary = 'production' in actions

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'advance.reorder.product.wise.process'
                ) or _('New')
        return super().create(vals_list)

    def _get_product_bom(self, product):
        """Return header BOM for the main product, otherwise company-wise BOM."""
        self.ensure_one()
        if product == self.product_id and self.bom_id:
            return self.bom_id
        return (
                product.with_company(self.company_id).reorder_bom_id
                or product.get_default_bom(company_id=self.company_id.id)
                or self.env['mrp.bom']
        )

    def _get_purchase_lead_days(self, product):
        """
        Calculate raw material lead days from purchase order moves.
        """
        self.ensure_one()
        lead_days = []
        move_domain = [
            ('product_id', '=', product.id),
            ('state', '=', 'done'),
            ('purchase_line_id', '!=', False),
            ('company_id', '=', self.company_id.id),
        ]
        start_dt = fields.Datetime.to_datetime(self.sales_start_date)
        move_domain.append(('date', '>=', start_dt))
        end_dt = fields.Datetime.to_datetime(self.sales_end_date) + relativedelta(days=1)
        move_domain.append(('date', '<', end_dt))

        done_moves = self.env['stock.move'].search(move_domain)
        for move in done_moves:
            purchase_line = move.purchase_line_id
            purchase_order = purchase_line.order_id
            approve_date = purchase_order.date_approve
            receipt_date = move.picking_id.date_done or move.date
            if not receipt_date or not approve_date:
                continue
            delay = (receipt_date.date() - approve_date.date()).days
            if delay > 0:
                lead_days.append(delay)

        return mean(lead_days) if lead_days else 0.0

    def _calculate_product_lead_days(
            self,
            product,
            parent_product=False,
            level=0,
            visited_products=None,
    ):
        """Calculate product lead days and prepare its BOM node."""
        self.ensure_one()

        visited_products = set(visited_products or set())

        if product.id in visited_products:
            raise ValidationError(_(
                'Circular BOM detected while calculating lead time for "%s".'
            ) % product.display_name)

        is_manufactured = product.reorder_product_classification in (
            'finished_good',
            'semi_finished_good',
        )

        if level == 0 and is_manufactured and not self.bom_id:
            raise ValidationError(_('Please select BOM first.'))

        if is_manufactured:
            bom = self._get_product_bom(product)
            own_lead_days = bom.produce_delay or 0.0
        else:
            bom = False
            own_lead_days = self._get_purchase_lead_days(product)

        node = {
            'product': product,
            'parent_product': parent_product,
            'bom': bom,
            'level': level,
            'own_lead_days': own_lead_days,
            'children': [],
            'lead_days': own_lead_days,
        }
        next_visited_products = visited_products | {product.id}

        if bom:
            self._calculate_child_lead_days(
                node=node,
                visited_products=next_visited_products,
            )

        return node

    def _calculate_child_lead_days(self, node, visited_products):
        """Calculate all child lead days and update parent lead days."""
        bom = node['bom']
        for bom_line in bom.bom_line_ids:
            component = bom_line.product_id

            child_node = self._calculate_product_lead_days(
                product=component,
                parent_product=node['product'],
                level=node['level'] + 1,
                visited_products=visited_products,
            )

            node['children'].append(child_node)

        max_child_lead_days = max(
            (
                child['lead_days']
                for child in node['children']
            ),
            default=0.0,
        )

        # Update parent lead days after all children are calculated
        node['lead_days'] = (
                node['own_lead_days'] + max_child_lead_days
        )

    def _create_component_tree_lines(self, node, parent_line=False):
        """Create hierarchical component lines (parent → children)."""
        self.ensure_one()
        ComponentLine = self.env['advance.reorder.product.component.line']
        line = ComponentLine.create({
            'product_wise_reorder_id': self.id,
            'parent_id': parent_line.id if parent_line else False,
            'level': node.get('level', 0),
            'product_id': node['product'].id,
            'actual_lead_days': node.get('lead_days') or 0.0,
            'lead_days': round(node.get('lead_days') or 0.0, 0),
            'manufacture_lead_days': (
                    node['bom'].produce_delay or 0.0
            ) if node.get('bom') else 0.0,
        })
        for child in node['children']:
            self._create_component_tree_lines(child, parent_line=line)

    def action_load_components(self):
        for record in self:
            if not record.product_id:
                raise UserError(_('Please select a product before loading components.'))

            root_node = record._calculate_product_lead_days(record.product_id)
            record._create_component_tree_lines(root_node)
        return True

    def _get_product_lead_days(self, product):
        """Lead days from the matching component line only."""
        self.ensure_one()
        component_line = self.component_line_ids.filtered(
            lambda line: line.product_id == product
        )[:1]
        if component_line:
            return int(round(component_line.lead_days)) or 1
        return 1

    def _get_company_warehouses(self):
        """All warehouses of the company set on this product-wise reorder."""
        self.ensure_one()
        warehouses = self.env['stock.warehouse'].search([
            ('company_id', '=', self.company_id.id),
        ])
        if not warehouses:
            raise UserError(_(
                'No warehouse found for company "%s".'
            ) % self.company_id.display_name)
        return warehouses

    def get_sales_data(self, warehouses, line_product_ids, ):
        """Company-wise sales data for all warehouses of this reorder company."""
        if not self.sales_start_date or not self.sales_end_date or not line_product_ids:
            return []
        sales_driven_products = line_product_ids
        products = sales_driven_products and set(sales_driven_products.ids) or {}
        if not products:
            return []
        warehouse_ids = set(warehouses.ids or [])
        start_date = self.sales_start_date.strftime('%Y-%m-%d')
        end_date = self.sales_end_date.strftime('%Y-%m-%d')
        query = """
                    Select product_id, product_name,
                        sum(sales) as sales,
                        sum(sales_return) as sales_return,
                        sum(total_sales) as total_sales,
                        sum(ads) as ads
                    from get_products_sales_warehouse_group_wise('%s', '%s', '%s', '%s', '%s', '%s')
                    group by product_id, product_name
                """ % ('{}', products, '{}', warehouse_ids, start_date, end_date)
        self._cr.execute(query)
        return self._cr.dictfetchall()

    def get_production_data(self, warehouses, line_product_ids):
        """Company-wise production data for all warehouses of this reorder company."""
        if not self.sales_start_date or not self.sales_end_date or not line_product_ids:
            return []

        production_driven_products = line_product_ids
        products = set(production_driven_products.ids) if production_driven_products else set()
        if not products:
            return []

        warehouse_ids = set(warehouses.ids or [])
        start_date = self.sales_start_date.strftime('%Y-%m-%d')
        end_date = self.sales_end_date.strftime('%Y-%m-%d')
        query = """
            Select product_id, product_name,
                sum(consumed_qty) as consumed_qty,
                sum(ads) as ads
            from get_products_production_warehouse_group_wise('%s', '%s', '%s', '%s', '%s', '%s')
            group by product_id, product_name
        """ % ('{}', products, '{}', warehouse_ids, start_date, end_date)
        self._cr.execute(query)
        return self._cr.dictfetchall()

    def get_resupply_data(self, warehouses, line_product_ids):
        """Company-wise subcontract/resupply data for this reorder company."""
        if not self.sales_start_date or not self.sales_end_date or not line_product_ids:
            return []
        if not self.company_id.use_subcontracting_for_demand:
            return []

        production_driven_products = line_product_ids
        products = set(production_driven_products.ids) if production_driven_products else set()
        if not products:
            return []

        warehouse_ids = set(warehouses.ids or [])
        start_date = self.sales_start_date.strftime('%Y-%m-%d')
        end_date = self.sales_end_date.strftime('%Y-%m-%d')
        query = """
            Select product_id, product_name,
                sum(resupply_qty) as resupply_qty,
                sum(resupply_return_qty) as resupply_return_qty,
                sum(ads) as ads
            from get_products_subcontracting_warehouse_group_wise('%s', '%s', '%s', '%s', '%s', '%s')
            group by product_id, product_name
        """ % ('{}', products, '{}', warehouse_ids, start_date, end_date)
        self._cr.execute(query)
        return self._cr.dictfetchall()

    def get_scrap_data(self, warehouses, line_product_ids):
        """Company-wise scrap data for this reorder company."""
        if not self.sales_start_date or not self.sales_end_date or not line_product_ids:
            return []
        if not self.company_id.use_scrap_for_demand:
            return []

        products = set(line_product_ids.ids)
        if not products:
            return []

        warehouse_ids = set(warehouses.ids or [])
        start_date = self.sales_start_date.strftime('%Y-%m-%d')
        end_date = self.sales_end_date.strftime('%Y-%m-%d')
        query = """
            Select product_id, product_name,
                sum(scrap_qty) as scrap_qty,
                sum(ads) as ads
            from get_products_scrap_warehouse_group_wise('%s', '%s', '%s', '%s', '%s', '%s')
            group by product_id, product_name
        """ % ('{}', products, '{}', warehouse_ids, start_date, end_date)
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

    def get_stock_move(self, product, warehouses):
        """Incoming moves for all warehouses of this reorder company."""
        stock_location_ids = warehouses.mapped('lot_stock_id').ids
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

    def _prepare_base_line_vals(self, warehouses, product):
        """Prepare base demand line values for one product, company-wise."""
        wh_summary = self._get_warehouse_qty_summary(product, warehouses)
        moves = self.get_stock_move(product, warehouses)
        return {
            'product_id': product.id,
            'available_stock': wh_summary['available'],
            'incoming_qty': wh_summary['incoming'],
            'stock_move_ids': [(6, 0, moves)],
        }

    def prepare_reorder_line_vals(self, warehouses, demand_data, is_mto_route=False):
        """Company-wise demand using each product's component-line lead days."""
        vals = []
        reorder_demand_growth = (
                self.reorder_demand_growth and self.reorder_demand_growth / 100 or 0.0
        )

        for data in demand_data:
            product = self.env['product.product'].browse(data.get('product_id'))
            reorder_line_vals = self._prepare_base_line_vals(warehouses, product)
            net_on_hand = reorder_line_vals.get('available_stock', 0.0)
            ads = data.get('ads', 0.0)
            lead_days = self._get_product_lead_days(product)

            ads = reorder_demand_growth and ads + (ads * reorder_demand_growth) or ads
            lead_days_demand = round(ads * lead_days, 2)
            expected_sales = self.buffer_security_days * ads

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
                lambda line: line.product_id == product
            )
            if existing_line:
                existing_line.write(reorder_line_vals)
                continue
            vals.append((0, 0, reorder_line_vals))
        return vals

    def action_reorder_confirm(self):
        """
        Company-wise demand generation for all warehouses of this reorder company.
        Lead days come from each product's component line.
        """
        self.ensure_one()
        self.demand_line_ids.unlink()
        self.summary_ids.unlink()
        vals = []
        warehouses = self._get_company_warehouses()
        product_ids = self.component_line_ids.product_id

        line_product_ids = product_ids.filtered(lambda product: not product.is_kit_product)
        kit_product_ids = product_ids.filtered(lambda product: product.is_kit_product)
        line_product_ids |= self._get_kit_component(kit_product_ids)

        sales_data = self.get_sales_data(warehouses, line_product_ids)
        production_data = self.get_production_data(warehouses, line_product_ids)
        scrap_data = self.get_scrap_data(warehouses, line_product_ids)
        resupply_data = self.get_resupply_data(warehouses, line_product_ids)

        demand_data = self._merge_ads_data(
            sales_data, production_data, resupply_data, scrap_data
        )
        vals.extend(self.prepare_reorder_line_vals(warehouses, demand_data, is_mto_route=False))

        write_vals = {'state': 'no_data'}
        if vals:
            write_vals = {
                'demand_line_ids': vals,
                'state': 'inprogress',
            }
        self.write(write_vals)
        return True

    def action_recalculate_demand(self):
        """Recalculate Demand after Validate."""
        for record in self:
            record.action_reorder_confirm()
        return True

    def action_validate(self):
        """Validate button: calculate demand and move to In Progress."""
        for record in self:
            if not record.component_line_ids:
                raise UserError(_('Please load components before validating demand.'))
            if not record.sales_start_date or not record.sales_end_date:
                raise UserError(_('Please set From date and End date before validating demand.'))
            if not record.buffer_security_days:
                raise UserError(_('Please set Coverage days before validating demand.'))
            record.action_reorder_confirm()
        return True

    def action_reorder_cancel(self):
        """Cancel product-wise demand."""
        for record in self:
            if record.state not in ('done', 'cancel', 'verified'):
                record.write({'state': 'cancel'})
        return True

    def action_reorder_reset_to_draft(self):
        """Reset to Draft and clear generated lines."""
        for record in self:
            record.demand_line_ids.unlink()
            record.summary_ids.unlink()
            record.component_line_ids.unlink()
            record.write({
                'state': 'draft',
                'reorder_amount': 0.0,
            })
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

    def _compute_to_be_ordered_in_purchase_uom(self, product, demanded_qty, order_qty, vendor_moq=0):
        """Purchase UOM quantity — same rules as Reorder with Real Demand summary."""
        purchase_qty = round(
            product.uom_id._compute_quantity(qty=order_qty, to_unit=product.uom_po_id)
        )
        if vendor_moq and demanded_qty < vendor_moq:
            purchase_qty = vendor_moq
        return purchase_qty

    def _get_purchase_details(self, product, company_id, demanded_qty, order_qty):
        """Same purchase MOQ/qty/price details as Reorder with Real Demand."""
        vendor_moq = 0
        price = product.standard_price or 0.0
        ps_info = self._get_product_supplier_info(product, company_id, demanded_qty)
        if ps_info:
            vendor_moq = ps_info.reorder_minimum_quantity
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
        purchase_qty = self._compute_to_be_ordered_in_purchase_uom(
            product,
            demanded_qty,
            order_qty,
            vendor_moq if ps_info else 0,
        )
        return vendor_moq, purchase_qty, price

    def _is_mto_buy_or_manufacture_product(self, product):
        """True when product has MTO with Buy and/or Manufacture routes."""
        route_names = set(product.route_ids.mapped('name'))
        return (
                {'Buy', 'Replenish on Order (MTO)'} <= route_names
                or {'Manufacture', 'Replenish on Order (MTO)'} <= route_names
        )

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
            self, product, order_qty, demanded_qty, order_action, company_id=None
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
        }

    def prepare_reorder_summary_vals(self):
        """Create summary lines from demand lines."""
        self.ensure_one()
        summary_vals = []
        reorder_total_amount = 0.0
        for line in self.demand_line_ids:
            product = line.product_id
            summary_by_product = self._get_summary_vals_by_product(summary_vals)
            if not product or product.id in summary_by_product:
                continue

            product_lines = self.demand_line_ids.filtered(
                lambda demand_line: demand_line.product_id.id == product.id
            )
            demanded_qty = sum(product_lines.mapped('demand_adjustment_qty'))

            if product.reorder_product_classification == "semi_finished_good" and self._is_mto_buy_or_manufacture_product(
                    product):
                warehouses = self._get_company_warehouses()
                sales_data = self.get_sales_data(warehouses, product)
                demanded_qty = self.prepare_reorder_line_vals(warehouses, sales_data,
                                                              is_mto_route=True) if sales_data else 0.0

            if demanded_qty <= 0:
                continue

            order_action = self._get_order_action(product)
            line_vals = self._prepare_net_demand_summary_line_vals(
                product=product,
                order_qty=demanded_qty,
                demanded_qty=demanded_qty,
                order_action=order_action,
                company_id=self.company_id,
            )
            if order_action == 'purchase':
                _vendor_moq, _purchase_qty, price = self._get_purchase_details(
                    product, self.company_id, demanded_qty, demanded_qty
                )
                reorder_total_amount += round(demanded_qty) * (price or 0.0)
            else:
                reorder_total_amount += round(demanded_qty) * (line.product_id.standard_price or 0.0)
            summary_vals.append((0, 0, line_vals))
        return summary_vals, reorder_total_amount

    def action_verify(self):
        """Verify button: create summary lines with Action, then set state to verified."""
        for record in self:
            if not record.demand_line_ids:
                raise UserError(_('Please validate demand before verifying.'))
            summary_vals, reorder_amount = record.prepare_reorder_summary_vals()
            record.summary_ids.unlink()
            write_vals = {
                'state': 'no_data',
                'reorder_amount': 0.0,
            }
            if summary_vals:
                write_vals = {
                    'summary_ids': summary_vals,
                    'state': 'verified',
                    'reorder_amount': reorder_amount,
                }
            record.write(write_vals)
        return True

    # ------------------------------------------
    # Purchase / Manufacturing order generation
    # -----------------------------------------

    def _get_date_planned(self, partner_id, product_id, product_qty, start_date):
        """Same planned date calculation as Reorder with Real Demand."""
        days = self.company_id.po_lead or 0
        days += product_id._select_seller(
            partner_id=partner_id,
            quantity=product_qty,
            date=fields.Date.context_today(self, start_date),
            uom_id=product_id.uom_po_id,
        ).delay or 0.0
        date_planned = start_date + relativedelta(days=days)
        return date_planned.strftime(DEFAULT_SERVER_DATETIME_FORMAT)

    def _prepare_purchase_order_line_vals(self, fpos, partner=None, summary_lines=None):
        """Prepare PO lines from company-wise summary lines."""
        partner = partner or self.vendor_id
        if not partner:
            raise UserError(_('A vendor is required to prepare purchase order lines.'))

        summaries = summary_lines if summary_lines is not None else self.summary_ids
        company_for_tax = self.company_id or self.env.company
        po_line_vals = []

        for summary_line in summaries:
            product_id = summary_line.product_id
            if not product_id:
                continue

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
                    lambda seller, pid=partner.id, cid=company_id: (
                            seller.partner_id.id == pid
                            and seller.company_id == cid
                            and seller.currency_id == cid.currency_id
                    )
                )
            else:
                ps_info = product_id.seller_ids.filtered(
                    lambda seller, pid=partner.id: seller.partner_id.id == pid
                )

            ps_info_have_min_qty = ps_info.filtered(lambda seller: seller.reorder_minimum_quantity > 0)
            if ps_info_have_min_qty:
                ps_info_have_min_qty = ps_info_have_min_qty.filtered(
                    lambda seller, qty=quantity: seller.reorder_minimum_quantity <= qty
                ).sorted(key=lambda seller: seller.reorder_minimum_quantity, reverse=True)
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
                taxes_id = taxes_id.filtered(lambda tax: tax.company_id.id == company_for_tax.id)

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

    def create_purchase_order(self, default_warehouse, partner=None, summary_lines=None):
        """Same purchase order creation as Reorder with Real Demand, company-wise."""
        partner = partner or self.vendor_id
        if not partner:
            raise UserError(_('A vendor is required to create a purchase order.'))
        origins = self.name
        purchase_date = datetime.today()
        company_id = self.company_id
        fpos = self.env['account.fiscal.position'].with_company(company_id)._get_fiscal_position(partner)
        fpos = fpos or False
        order_line_vals = self._prepare_purchase_order_line_vals(
            fpos, partner=partner, summary_lines=summary_lines
        )
        if not order_line_vals:
            return True

        dates = [fields.Datetime.from_string(value[2]['date_planned']) for value in order_line_vals]
        procurement_date_planned = dates and max(dates) or False
        purchase_order_obj = self.env['purchase.order'].with_user(self.user_id).with_company(company_id)
        existing_po = purchase_order_obj.search([
            ('product_wise_reorder_id', '=', self.id),
            ('partner_id', '=', partner.id),
            ('company_id', '=', company_id.id),
            ('state', 'in', ['draft', 'sent']),
        ], limit=1)
        if existing_po:
            updated_date_planned = existing_po.date_planned
            if procurement_date_planned and existing_po.date_planned:
                updated_date_planned = max(existing_po.date_planned, procurement_date_planned)
            elif procurement_date_planned and not existing_po.date_planned:
                updated_date_planned = procurement_date_planned
            existing_po.write({
                'order_line': order_line_vals,
                'date_planned': updated_date_planned,
            })
            return existing_po

        vals = {
            'partner_id': partner.id,
            'user_id': self.user_id and self.user_id.id or self.env.user.id,
            'picking_type_id': default_warehouse.in_type_id.id,
            'company_id': company_id.id,
            'currency_id': partner.with_company(
                company_id
            ).property_purchase_currency_id.id or company_id.currency_id.id,
            'origin': origins,
            'payment_term_id': partner.with_company(company_id).property_supplier_payment_term_id.id,
            'date_order': purchase_date,
            'fiscal_position_id': fpos.id if fpos else False,
            'order_line': order_line_vals,
            'product_wise_reorder_id': self.id,
            'date_planned': procurement_date_planned,
        }
        return purchase_order_obj.create(vals)

    def get_vendor_product_mapping_dict(self, purchase_summaries):
        """Same vendor/product mapping as Reorder with Real Demand."""
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
        """Opens the PO vendor wizard to select a warehouse and create purchase orders."""
        self.ensure_one()
        purchase_summaries = self.summary_ids.filtered(lambda summary: summary.order_action == 'purchase')
        if not purchase_summaries:
            raise UserError(_('No summary lines are set to Generate Purchase Orders.'))

        wizard = self.env['advance.reorder.po.vendor.wizard'].create({
            'product_wise_reorder_id': self.id,
            'company_id': self.company_id.id,
        })
        wizard_name = _('Select vendors for purchase') if wizard.show_vendor_selection else _(
            'Select Warehouse To Create Purchase Order'
        )
        return {
            'name': wizard_name,
            'type': 'ir.actions.act_window',
            'res_model': 'advance.reorder.po.vendor.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
            'context': dict(self.env.context),
        }

    def create_purchase_orders_for_warehouse(self, warehouse):
        """Creates purchase orders on the selected warehouse using vendor selection strategy."""
        self.ensure_one()
        if not warehouse:
            raise UserError(_('Please select a warehouse to create purchase orders.'))
        if self.state != 'verified':
            raise UserError(_(
                'Purchase orders can only be created from a verified product-wise demand.'
            ))

        purchase_summaries = self.summary_ids.filtered(lambda summary: summary.order_action == 'purchase')
        if not purchase_summaries:
            raise UserError(_('No summary lines are set to Generate Purchase Orders.'))

        vendor_product_dict = self.get_vendor_product_mapping_dict(purchase_summaries)
        for vendor_id, product_list in vendor_product_dict.items():
            partner = self.env['res.partner'].browse(vendor_id)
            summary_lines = purchase_summaries.filtered(
                lambda summary, products=product_list: summary.product_id.id in products
            )
            if (
                    self.vendor_selection_strategy == 'specific_vendor'
                    and partner.vendor_rule in ['both', 'minimum_order_value']
                    and self.reorder_amount < self.minimum_reorder_amount
            ):
                raise UserError(_(
                    "Can not create purchase order because reorder doesn't fulfil "
                    "vendor's minimum order amount's rule."
                ))
            self.create_purchase_order(
                warehouse,
                partner=partner,
                summary_lines=summary_lines,
            )

        if self.purchase_ids:
            self.write({'state': 'done'})
        return True

    def action_create_reorder_manufacturing_orders(self):
        """Opens the wizard to select a warehouse for creating manufacturing orders."""
        self.ensure_one()
        wizard = self.env['advance.reorder.mrp.wizard'].create({
            'product_wise_reorder_id': self.id,
            'company_id': self.company_id.id,
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
            raise UserError(_(
                'Manufacturing orders can only be created from a verified product-wise demand.'
            ))
        production_summaries = self.summary_ids.filtered(
            lambda summary: summary.order_action == 'production' and summary.order_qty > 0
        )
        if self.production_ids:
            raise UserError(_(
                'Manufacturing orders have already been created for this product-wise demand.'
            ))

        Production = self.env['mrp.production'].with_user(self.user_id).with_company(self.company_id)
        mo_vals_list = self._prepare_manufacturing_order_vals_from_summary(
            production_summaries, warehouse_id
        )
        if not mo_vals_list:
            raise UserError(_('No manufacturing orders to create.'))

        Production.create(mo_vals_list)
        return True

    def _prepare_manufacturing_order_vals_from_summary(self, production_summaries, warehouse):
        """Prepares manufacturing order values from production summary lines."""
        mo_vals_list = []
        for summary_line in production_summaries:
            product = summary_line.product_id
            if not product:
                continue
            picking_type = warehouse.manu_type_id
            if not picking_type:
                raise UserError(_(
                    'No manufacturing operation type configured for warehouse %s.',
                    warehouse.display_name,
                ))
            bom = self._get_product_bom(product)
            if not bom:
                _logger.warning(
                    "No BOM found for product %s (ID: %s).",
                    product.display_name,
                    product.id,
                )
                continue
            mo_vals_list.append({
                'product_id': product.id,
                'product_qty': summary_line.order_qty,
                'bom_id': bom.id,
                'picking_type_id': picking_type.id,
                'company_id': self.company_id.id,
                'origin': self.name,
                'product_wise_reorder_id': self.id,
            })
        return mo_vals_list

    def action_purchase_count(self):
        """Opens linked purchase orders."""
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('purchase.purchase_form_action')
        purchases = self.mapped('purchase_ids')
        if len(purchases) > 1:
            action['domain'] = [('id', 'in', purchases.ids)]
        elif purchases:
            form_view = [(self.env.ref('purchase.purchase_order_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [
                    (state, view) for state, view in action['views'] if view != 'form'
                ]
            else:
                action['views'] = form_view
            action['res_id'] = purchases.id
        return action

    def action_production_count(self):
        """Opens linked manufacturing orders."""
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
