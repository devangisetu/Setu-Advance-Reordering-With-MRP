# -*- coding: utf-8 -*-
import logging
from collections import defaultdict
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
        copy=False,
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
    to_be_produced_line_ids = fields.One2many(
        'advance.reorder.productwise.produced.demand.line',
        'product_wise_reorder_id',
        string='To Be Produced Lines',
        copy=False,
    )
    component_demand_line_ids = fields.One2many(
        'advance.reorder.productwise.component.demand.line',
        'product_wise_reorder_id',
        string='Component Demand Lines',
        copy=False,
    )
    by_product_line_ids = fields.One2many(
        'advance.reorder.productwise.by.product.line',
        'product_wise_reorder_id',
        string='By Product Lines',
        copy=False,
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
    replenishment_ids = fields.One2many(
        'advance.procurement.process',
        'product_wise_reorder_id',
        string='Replenishment Order',
    )
    replenishment_count = fields.Integer(
        string='Replenishment count',
        compute='_compute_count_replenishment',
    )
    has_purchase_action_summary = fields.Boolean(
        string='Has Purchase Action',
        compute='_compute_summary_action_flags',
    )
    has_production_action_summary = fields.Boolean(
        string='Has Production Action',
        compute='_compute_summary_action_flags',
    )
    has_subcontracting_action_summary = fields.Boolean(
        string='Has Subcontracting Action',
        compute='_compute_summary_action_flags',
    )
    is_subcontracting_created = fields.Boolean(
        string='Subcontracting Orders Created',
        compute='_compute_action_done_flags',
    )
    is_purchase_action_done = fields.Boolean(
        string='Purchase Action Done',
        compute='_compute_action_done_flags',
    )
    fg_count = fields.Integer(compute='_compute_fg_count')
    sfg_count = fields.Integer(compute='_compute_sfg_count')
    component_count = fields.Integer(compute='_compute_component_count')
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
        """Set default BOM when product or company changes."""
        for record in self:
            record.bom_id = False
            if not record.product_id:
                continue
            bom_id = record._get_product_bom(record.product_id)
            if bom_id:
                record.bom_id = bom_id.id

    @api.onchange('vendor_selection_strategy')
    def _onchange_vendor_selection_strategy(self):
        """Clear vendor when strategy is not specific vendor."""
        for record in self:
            if record.vendor_selection_strategy != 'specific_vendor':
                record.vendor_id = False

    def _compute_purchase_count(self):
        """Count linked purchase orders."""
        for record in self:
            record.purchase_count = len(record.purchase_ids)

    def _compute_production_count(self):
        """Count linked manufacturing orders."""
        for record in self:
            record.production_count = len(record.production_ids)

    def _compute_count_replenishment(self):
        """Count linked warehouse replenishment records."""
        for record in self:
            record.replenishment_count = len(record.replenishment_ids)

    def _get_demand_lines_by_classification(self, classification):
        """Return demand lines matching reorder product classification."""
        self.ensure_one()
        return self.demand_line_ids.filtered(
            lambda line: line.product_id.reorder_product_classification == classification
        )

    def _compute_fg_count(self):
        """Count finished goods demand lines."""
        for record in self:
            record.fg_count = len(
                record.demand_line_ids.filtered(
                    lambda line: line.product_id.reorder_product_classification == 'finished_good'
                )
            )

    def _compute_sfg_count(self):
        """Count semi-finished goods demand lines including To Be Produced."""
        for record in self:
            line_count = len(
                record.demand_line_ids.filtered(
                    lambda line: line.product_id.reorder_product_classification == 'semi_finished_good'
                )
            )
            record.sfg_count = line_count + len(record.to_be_produced_line_ids)

    def _compute_component_count(self):
        """Count raw material / component demand lines including Component Demand tab."""
        for record in self:
            line_count = len(
                record.demand_line_ids.filtered(
                    lambda line: line.product_id.reorder_product_classification == 'raw_material'
                )
            )
            record.component_count = line_count + len(record.component_demand_line_ids)

    def action_view_fg(self):
        """Open finished goods demand calculation lines."""
        self.ensure_one()
        fg_lines = self._get_demand_lines_by_classification('finished_good')
        return {
            'name': _('FG Demand Calculation'),
            'type': 'ir.actions.act_window',
            'res_model': 'advance.reorder.product.wise.process.line',
            'view_mode': 'list',
            'views': [(
                self.env.ref(
                    'setu_advance_reordering_extended.view_product_wise_fg_demand_planning_tree'
                ).id,
                'list',
            )],
            'domain': [('id', 'in', fg_lines.ids)],
            'target': 'current',
        }

    def action_view_sfg(self):
        """Prepare and open semi-finished goods planning lines."""
        self.ensure_one()
        PlanningLine = self.env['advance.reorder.planning.line']
        PlanningLine.search([
            ('product_wise_reorder_id', '=', self.id),
            ('line_type', '=', 'sfg'),
        ]).unlink()
        planning_vals = [
            {
                'product_wise_reorder_id': self.id,
                'product_id': line.product_id.id,
                'net_demand': line.net_demand,
                'line_type': 'sfg',
            }
            for line in self.to_be_produced_line_ids
        ]
        planning_vals.extend([
            {
                'product_wise_reorder_id': self.id,
                'product_id': line.product_id.id,
                'net_demand': line.demand_adjustment_qty,
                'line_type': 'sfg',
            }
            for line in self._get_demand_lines_by_classification('semi_finished_good')
        ])
        if planning_vals:
            PlanningLine.create(planning_vals)
        return {
            'name': _('SFG Demand Calculation'),
            'type': 'ir.actions.act_window',
            'res_model': 'advance.reorder.planning.line',
            'view_mode': 'list',
            'views': [(
                self.env.ref(
                    'setu_advance_reordering_extended.view_advance_reorder_planning_line_tree'
                ).id,
                'list',
            )],
            'domain': [
                ('product_wise_reorder_id', '=', self.id),
                ('line_type', '=', 'sfg'),
            ],
            'target': 'current',
        }

    def action_view_components(self):
        """Prepare and open component demand planning lines."""
        self.ensure_one()
        PlanningLine = self.env['advance.reorder.planning.line']
        PlanningLine.search([
            ('product_wise_reorder_id', '=', self.id),
            ('line_type', '=', 'component'),
        ]).unlink()
        planning_vals = [
            {
                'product_wise_reorder_id': self.id,
                'product_id': line.product_id.id,
                'net_demand': line.net_demand,
                'line_type': 'component',
            }
            for line in self.component_demand_line_ids
        ]
        planning_vals.extend([
            {
                'product_wise_reorder_id': self.id,
                'product_id': line.product_id.id,
                'net_demand': line.demand_adjustment_qty,
                'line_type': 'component',
            }
            for line in self._get_demand_lines_by_classification('raw_material')
        ])
        if planning_vals:
            PlanningLine.create(planning_vals)
        return {
            'name': _('Components Demand Calculation'),
            'type': 'ir.actions.act_window',
            'res_model': 'advance.reorder.planning.line',
            'view_mode': 'list',
            'views': [(
                self.env.ref(
                    'setu_advance_reordering_extended.view_advance_reorder_planning_line_tree'
                ).id,
                'list',
            )],
            'domain': [
                ('product_wise_reorder_id', '=', self.id),
                ('line_type', '=', 'component'),
            ],
            'target': 'current',
        }

    @api.depends('summary_ids', 'summary_ids.order_action')
    def _compute_summary_action_flags(self):
        """Flag whether summary has purchase/production/subcontract actions."""
        for record in self:
            actions = set(record.summary_ids.mapped('order_action'))
            record.has_purchase_action_summary = 'purchase' in actions
            record.has_production_action_summary = 'production' in actions
            record.has_subcontracting_action_summary = 'subcontracting' in actions

    @api.depends(
        'summary_ids',
        'summary_ids.order_action',
        'summary_ids.is_action_done',
    )
    def _compute_action_done_flags(self):
        """Track whether all purchase/subcontracting summary lines are marked done."""
        for record in self:
            purchase_summaries = record.summary_ids.filtered(
                lambda summary: summary.order_action == 'purchase'
            )
            record.is_purchase_action_done = bool(purchase_summaries) and all(
                purchase_summaries.mapped('is_action_done')
            )
            subcontract_summaries = record.summary_ids.filtered(
                lambda summary: summary.order_action == 'subcontracting'
            )
            record.is_subcontracting_created = bool(subcontract_summaries) and all(
                subcontract_summaries.mapped('is_action_done')
            )

    def _are_all_order_actions_done(self):
        """Return True when every required summary action has been generated."""
        self.ensure_one()
        for action in ('purchase', 'production', 'subcontracting'):
            action_lines = self.summary_ids.filtered(lambda summary: summary.order_action == action)
            if action_lines and not all(action_lines.mapped('is_action_done')):
                return False
        return True

    def _mark_summary_lines_done(self, summaries):
        """Mark summary lines as done after their documents are created."""
        summaries = summaries.filtered(lambda summary: not summary.is_action_done)
        if summaries:
            summaries.write({'is_action_done': True})

    def _update_state_after_order_creation(self):
        """Mark process done only when all required order actions are complete."""
        for record in self:
            if record.state == 'verified' and record._are_all_order_actions_done():
                record.write({'state': 'done'})

    @api.model_create_multi
    def create(self, vals_list):
        """Assign sequence number on create."""
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'advance.reorder.product.wise.process'
                ) or _('New')
        return super().create(vals_list)

    def _get_product_bom(self, product):
        """Return BOM for product from header or product defaults."""
        self.ensure_one()
        if product == self.product_id and self.bom_id:
            return self.bom_id
        return (
                product.with_company(self.company_id).reorder_bom_id
                or product.get_default_bom(company_id=self.company_id.id)
                or self.env['mrp.bom']
        )


    def _get_subcontract_bom_for_product(self, product):
        """Return the subcontract BOM used to resolve subcontract vendors."""
        self.ensure_one()
        if product == self.product_id and self.bom_id and self.bom_id.type == 'subcontract':
            return self.bom_id
        bom = product.reorder_bom_id
        if not bom or bom.type != 'subcontract':
            bom = product.bom_ids.filtered(
                lambda bom_rec: bom_rec.type == 'subcontract'
                and (not bom_rec.company_id or bom_rec.company_id == self.company_id)
            )[:1]
        return bom or self.env['mrp.bom']

    def _get_subcontract_partner_for_product(self, product):
        """Return the BOM subcontractor to use for a subcontract purchase order.

        1. Single BOM subcontractor → use it.
        2. Multiple → matching product sellers by vendor strategy
           (On PO Creation uses seller sequence); else first BOM subcontractor.
        """
        self.ensure_one()
        bom = self._get_subcontract_bom_for_product(product)
        subcontractors = bom.subcontractor_ids
        if not subcontractors:
            return self.env['res.partner']
        if len(subcontractors) == 1:
            return subcontractors

        product_vendors = product.seller_ids.filtered(
            lambda seller: not seller.company_id or seller.company_id == self.company_id
        ).mapped('partner_id')
        matching_sellers = subcontractors & product_vendors
        if not matching_sellers:
            return subcontractors[:1]
        if len(matching_sellers) == 1:
            return matching_sellers

        strategy = self.vendor_selection_strategy
        if strategy == 'specific_vendor' and self.vendor_id and self.vendor_id in matching_sellers:
            return self.vendor_id
        sort_by = strategy if strategy in ('sequence', 'price', 'delay') else 'sequence'
        seller = product.with_company(self.company_id).with_context({
            'sort_by': sort_by,
            'op_company': self.company_id,
        })._select_seller(
            quantity=None,
            params={'subcontractor_ids': matching_sellers},
        )
        return seller.partner_id if seller and seller.partner_id else matching_sellers[:1]

    def get_subcontracting_vendor_product_mapping_dict(self, subcontract_summaries):
        """Group subcontract summary products by auto-resolved subcontractor vendor."""
        self.ensure_one()
        vendor_product_dict = {}
        products_without_subcontractor = self.env['product.product']
        for product in subcontract_summaries.mapped('product_id'):
            partner = self._get_subcontract_partner_for_product(product)
            if not partner:
                products_without_subcontractor |= product
                continue
            vendor_product_dict.setdefault(partner.id, []).append(product.id)
        if products_without_subcontractor:
            raise UserError(_(
                'No subcontracting BOM with a subcontractor found for the following '
                'product(s):\n%(products)s',
                products='\n'.join(
                    '- %s' % product.display_name
                    for product in products_without_subcontractor
                ),
            ))
        return vendor_product_dict

    def _get_purchase_lead_days(self, product):
        """Average purchase lead days from done receipt moves."""
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
        """Build BOM tree node with own and total lead days."""
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
        """Add child BOM lead days and update parent total."""
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
        """Create parent-child component lines from BOM tree."""
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
        """Load BOM components and compute lead days."""
        for record in self:
            if not record.product_id:
                raise UserError(_('Please select a product before loading components.'))

            root_node = record._calculate_product_lead_days(record.product_id)
            record._create_component_tree_lines(root_node)
        return True

    def _get_product_lead_days(self, product):
        """Return lead days from matching component line."""
        self.ensure_one()
        component_line = self.component_line_ids.filtered(
            lambda line: line.product_id == product
        )[:1]
        if component_line:
            return int(round(component_line.lead_days)) or 1
        return 1

    def _get_company_warehouses(self):
        """Return all warehouses for the reorder company."""
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
        """Fetch sales ADS data for products and warehouses."""
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
        """Fetch production consumption ADS data."""
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
        """Fetch subcontracting resupply ADS data."""
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
        """Fetch scrap ADS data for products and warehouses."""
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
        """Expand kit products into BOM component products."""
        component_products = self.env['product.product']
        for product in products:
            bom = self._get_product_bom(product)
            if bom:
                component_products |= bom.bom_line_ids.mapped('product_id')
        return component_products

    def _merge_ads_data(self, sales_data, production_data, resupply_data, scrap_data):
        """Merge sales, production, resupply and scrap ADS by product."""
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
        """Return free, outgoing and incoming qty across warehouses."""
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
        """Return open incoming stock move IDs for product."""
        stock_location_ids = warehouses.mapped('lot_stock_id').ids
        return self.env['stock.move'].search([
            ('product_id', '=', product.id),
            ('state', 'not in', ['draft', 'cancel', 'done']),
            ('location_dest_id', 'in', stock_location_ids),
        ]).ids

    def _rounding_demand_quantity(self, quantity):
        """Round demand qty by company rounding rules."""
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
        """Prepare stock fields for one demand line."""
        wh_summary = self._get_warehouse_qty_summary(product, warehouses)
        moves = self.get_stock_move(product, warehouses)
        return {
            'product_id': product.id,
            'available_stock': wh_summary['available'],
            'incoming_qty': wh_summary['incoming'],
            'stock_move_ids': [(6, 0, moves)],
        }

    def prepare_reorder_line_vals(self, warehouses, demand_data, is_mto_route=False):
        """Build or update demand lines from ADS and lead days."""
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
        """Generate demand lines for all company warehouses, then MRP component tabs."""
        self.ensure_one()
        self.demand_line_ids.unlink()
        self.to_be_produced_line_ids.unlink()
        self.component_demand_line_ids.unlink()
        self.by_product_line_ids.unlink()
        self.summary_ids.unlink()
        vals = []
        warehouses = self._get_company_warehouses()
        product_ids = self.product_id

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
        self.invalidate_recordset(['demand_line_ids'])
        if self.demand_line_ids:
            self._collect_mrp_tab_requirements()
            self._round_mrp_demand_quantities()
        return True

    def _round_mrp_demand_quantities(self):
        """Round demand quantities in MRP demand lines."""
        self._round_demand_qty(self.to_be_produced_line_ids)
        self._round_demand_qty(self.component_demand_line_ids)

    def _round_demand_qty(self, lines):
        """Round demand quantity for the given recordset."""
        for line in lines:
            line.demand_adjustment_qty = round(self._rounding_demand_quantity(line.net_demand))

    def _collect_mrp_tab_requirements(self):
        """Generate To Be Produced, Component Demand, and By-Product lines by exploding BOMs."""
        self.ensure_one()
        produced_data = defaultdict(float)
        component_data = defaultdict(
            lambda: {
                'qty': 0.0,
                'source_line_ids': [],
            }
        )
        by_product_data = []
        warehouses = self._get_company_warehouses()

        for line in self.demand_line_ids:
            product = line.product_id
            qty = line.demand_adjustment_qty

            if qty <= 0 or product.is_kit_product:
                continue

            classification = product.reorder_product_classification
            if classification not in ('finished_good', 'semi_finished_good'):
                continue

            bom = self._get_product_bom(product)
            if not bom:
                _logger.warning(
                    "Reorder BOM not found for product '%s' (ID: %s). Skipping demand generation.",
                    product.display_name,
                    product.id,
                )
                continue

            self._explode_bom_into_tabs(
                product,
                qty,
                component_data,
                produced_data,
                warehouses,
                by_product_data=by_product_data,
                parent_product=product,
                bom=bom,
            )

        self._generate_component_demand_lines(warehouses, dict(component_data))
        self._generate_by_product_lines(by_product_data)

    def _explode_bom_into_tabs(
            self, product, quantity, component_data, produced_data, warehouses,
            bom=None, by_product_data=None, parent_product=None,
    ):
        """Recursively explode a product BOM into Component / To Be Produced / By-Product tabs."""
        if quantity <= 0:
            return

        bom = bom or self._get_product_bom(product)
        if not bom:
            _logger.warning(
                "No BOM found for product %s (ID: %s).",
                product.display_name,
                product.id,
            )
            return

        bom_parent = parent_product or product
        self._collect_bom_by_products(product, quantity, by_product_data, bom=bom)

        bom_qty = bom.product_qty or 1.0
        for bom_line in bom.bom_line_ids:
            component = bom_line.product_id
            if not component:
                continue
            required_qty = quantity * (bom_line.product_qty / bom_qty)
            self._process_product_by_classification(
                component, required_qty, component_data, produced_data, warehouses, bom,
                by_product_data=by_product_data,
                source_product=bom_parent, source_qty=quantity,
            )

    def _process_product_by_classification(
            self, product, qty, component_data, produced_data, warehouses, bom,
            by_product_data=None, source_product=None, source_qty=0,
    ):
        """Route each BOM component to Component Demand or To Be Produced based on classification."""
        if not product or qty <= 0:
            return

        classification = product.reorder_product_classification
        if classification == 'raw_material':
            self._add_to_component_tab(component_data, product, qty, bom, source_product, source_qty)
        elif classification == 'semi_finished_good':
            line, net_qty = self._create_or_update_to_be_produced_line(
                product, qty, bom, source_product, source_qty, warehouses, produced_data,
            )
            self._explode_bom_into_tabs(
                product, net_qty, component_data, produced_data, warehouses,
                bom=line.bom_id,
                by_product_data=by_product_data,
                parent_product=product,
            )

    def _collect_bom_by_products(self, product, parent_mo_qty, by_product_data, bom=None):
        """Collect by-product quantities generated from a BOM based on parent production qty."""
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
        """Add a by-product entry to the by-product demand collection."""
        if product and qty > 0:
            by_product_data.append({
                'product_id': product.id,
                'source_product_id': source_product.id if source_product else False,
                'source_product_demand': source_product_demand,
                'quantity': qty,
            })

    def _add_to_component_tab(self, component_data, product, qty, bom, source_product, source_qty):
        """Accumulate a component requirement and its source details."""
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

    def _prepare_to_be_produced_line_vals(self, product, required_qty, bom, source_product, source_qty, warehouses):
        """Prepare values for creating a To Be Produced demand line."""
        warehouse_qty = self._get_warehouse_qty_summary(product, warehouses)
        scrap_data = self.get_scrap_data(warehouses, product)
        product_bom = self._get_product_bom(product)
        return {
            'product_wise_reorder_id': self.id,
            'product_id': product.id,
            'bom_id': product_bom.id if product_bom else False,
            'available_qty': warehouse_qty['available'],
            'required_qty': required_qty,
            'incoming_qty': warehouse_qty['incoming'],
            'scrap_qty': scrap_data[0].get('scrap_qty', 0) if scrap_data else 0,
            'net_demand': max(0.0, required_qty - warehouse_qty['available']),
            'source_line_ids': [
                (0, 0, {
                    'source_product_id': source_product.id,
                    'bom_id': bom.id,
                    'source_qty': source_qty,
                    'required_qty': required_qty,
                })
            ],
        }

    def _create_or_update_to_be_produced_line(
            self, product, qty, bom, source_product, source_qty, warehouses, produced_data,
    ):
        """Create or update a To Be Produced line when an SFG is found in the BOM."""
        ProducedLine = self.env['advance.reorder.productwise.produced.demand.line']
        if not product or qty <= 0:
            return ProducedLine, 0.0

        produced_data[product.id] += qty
        match_line = self.to_be_produced_line_ids.filtered(
            lambda line: line.product_id.id == product.id
        )[:1]
        if match_line:
            required_qty = qty
            if match_line.net_demand <= 0:
                required_qty = abs(min(0, match_line.available_qty - match_line.required_qty - qty))

            match_line.write({
                'required_qty': match_line.required_qty + qty,
                'net_demand': max(0.0, (match_line.required_qty + qty) - match_line.available_qty),
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

        vals = self._prepare_to_be_produced_line_vals(
            product, qty, bom, source_product, source_qty, warehouses,
        )
        produced_line = ProducedLine.create(vals)
        return produced_line, produced_line.net_demand

    def _generate_component_demand_lines(self, warehouses, component_data=None):
        """Create component demand lines from accumulated BOM component requirements."""
        if not component_data:
            return

        ComponentLine = self.env['advance.reorder.productwise.component.demand.line']
        for product_id, bom_required_qty in component_data.items():
            product = self.env['product.product'].browse(product_id)
            warehouse_qty = self._get_warehouse_qty_summary(product, warehouses)
            qty = bom_required_qty.get('qty')
            scrap_data = self.get_scrap_data(warehouses, product)
            ComponentLine.create({
                'product_wise_reorder_id': self.id,
                'product_id': product_id,
                'available_qty': warehouse_qty['available'],
                'required_qty': qty,
                'incoming_qty': warehouse_qty['incoming'],
                'scrap_qty': scrap_data[0].get('scrap_qty', 0) if scrap_data else 0,
                'net_demand': max(0.0, qty - warehouse_qty['available']),
                'source_line_ids': bom_required_qty.get('source_line_ids'),
            })

    def _generate_by_product_lines(self, by_product_data=None):
        """Create by-product demand lines from collected by-product data."""
        if not by_product_data:
            return

        ByProductLine = self.env['advance.reorder.productwise.by.product.line']
        for entry in by_product_data:
            quantity = entry.get('quantity', 0.0)
            if quantity <= 0:
                continue
            ByProductLine.create({
                'product_wise_reorder_id': self.id,
                'product_id': entry['product_id'],
                'source_product_id': entry.get('source_product_id'),
                'source_product_demand': entry.get('source_product_demand', 0.0),
                'quantity': quantity,
            })

    def action_recalculate_demand(self):
        """Recalculate demand lines after validation."""
        for record in self:
            record.action_reorder_confirm()
        return True

    def action_validate(self):
        """Validate inputs and generate demand lines."""
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
        """Cancel the product-wise demand process."""
        for record in self:
            if record.state not in ('done', 'cancel', 'verified'):
                record.write({'state': 'cancel'})
        return True

    def action_reorder_reset_to_draft(self):
        """Reset to draft and clear generated lines."""
        for record in self:
            record.demand_line_ids.unlink()
            record.to_be_produced_line_ids.unlink()
            record.component_demand_line_ids.unlink()
            record.by_product_line_ids.unlink()
            record.summary_ids.unlink()
            record.component_line_ids.unlink()
            record.write({
                'state': 'draft',
                'reorder_amount': 0.0,
            })
        return True

    def _filter_supplier_info_by_moq(self, ps_info, total_demand):
        """Pick supplier pricelist matching demand and MOQ."""
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
        """Resolve supplier pricelist for product and demand."""
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
        """Convert order qty to purchase UoM, applying vendor MOQ."""
        purchase_qty = round(
            product.uom_id._compute_quantity(qty=order_qty, to_unit=product.uom_po_id)
        )
        if vendor_moq and demanded_qty < vendor_moq:
            purchase_qty = vendor_moq
        return purchase_qty

    def _get_purchase_details(self, product, company_id, demanded_qty, order_qty):
        """Return vendor MOQ, purchase UoM qty and unit price."""
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
        """Check if product uses MTO with Buy or Manufacture."""
        route_names = set(product.route_ids.mapped('name'))
        return (
                {'Buy', 'Replenish on Order (MTO)'} <= route_names
                or {'Manufacture', 'Replenish on Order (MTO)'} <= route_names
        )

    def _get_order_action(self, product):
        """Decide summary action from BOM type, routes and classification.

        Non-storable products get none; subcontract BOM → subcontracting;
        otherwise purchase or production.
        """
        if not product or not product.is_storable:
            return 'none'
        if self._get_subcontract_bom_for_product(product):
            return 'subcontracting'
        route_names = set(product.route_ids.mapped('name'))
        if {'Manufacture', 'Replenish on Order (MTO)'} <= route_names:
            return 'production'
        if {'Buy', 'Replenish on Order (MTO)'} <= route_names:
            return 'purchase'
        if product.reorder_product_classification in ('finished_good', 'semi_finished_good'):
            return 'production'
        return 'purchase'


    def _get_summary_vals_by_product(self, summary_vals):
        """Index pending summary vals by product id."""
        return {
            command[2]['product_id']: command[2]
            for command in summary_vals
            if command[0] == 0 and command[2].get('product_id')
        }

    def _prepare_net_demand_summary_line_vals(
            self, product, order_qty, demanded_qty, order_action, company_id=None
    ):
        """Prepare one summary line with MOQ and purchase UoM qty."""
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

    def _append_net_demand_summary_from_tab_lines(
            self,
            summary_vals,
            reorder_total_amount,
            tab_lines,
            order_action,
    ):
        """Add products from MRP tab lines to the reorder summary."""
        summary_by_product = self._get_summary_vals_by_product(summary_vals)

        for tab_line in tab_lines:
            product = tab_line.product_id
            if not product or product.id in summary_by_product:
                continue

            order_qty = round(tab_line.demand_adjustment_qty)
            if (
                    product.reorder_product_classification == 'semi_finished_good'
                    and self._is_mto_buy_or_manufacture_product(product)
            ):
                warehouses = self._get_company_warehouses()
                sales_data = self.get_sales_data(warehouses, product)
                order_qty = self.prepare_reorder_line_vals(
                    warehouses, sales_data, is_mto_route=True,
                ) if sales_data else 0.0

            if order_qty <= 0:
                continue

            resolved_action = self._get_order_action(product)
            line_vals = self._prepare_net_demand_summary_line_vals(
                product=product,
                order_qty=order_qty,
                demanded_qty=order_qty,
                order_action=resolved_action,
                company_id=self.company_id,
            )
            if resolved_action == 'purchase':
                _vendor_moq, _purchase_qty, price = self._get_purchase_details(
                    product, self.company_id, order_qty, order_qty,
                )
                reorder_total_amount += round(order_qty) * (price or 0.0)
            else:
                reorder_total_amount += round(order_qty) * (product.standard_price or 0.0)

            summary_vals.append((0, 0, line_vals))
            summary_by_product[product.id] = line_vals

        return summary_vals, reorder_total_amount

    def prepare_reorder_summary_vals(self):
        """Build summary lines from demand, To Be Produced, and Component Demand tabs."""
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

        summary_vals, reorder_total_amount = self._append_net_demand_summary_from_tab_lines(
            summary_vals=summary_vals,
            reorder_total_amount=reorder_total_amount,
            tab_lines=self.to_be_produced_line_ids,
            order_action='production',
        )
        return self._append_net_demand_summary_from_tab_lines(
            summary_vals=summary_vals,
            reorder_total_amount=reorder_total_amount,
            tab_lines=self.component_demand_line_ids,
            order_action='purchase',
        )

    def action_verify(self):
        """Create summary lines and move process to verified."""
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
        """Compute planned receipt date from vendor and company lead."""
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
        """Prepare purchase order line values from summaries."""
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
        """Create or update draft purchase order for vendor."""
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

    def get_vendor_product_mapping_dict(self, purchase_summaries, order_action='purchase'):
        """Map vendors to products for purchase or subcontracting summaries."""
        if order_action == 'subcontracting':
            return self.get_subcontracting_vendor_product_mapping_dict(purchase_summaries)

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
        """Open wizard to create purchase orders."""
        self.ensure_one()
        if self.is_purchase_action_done:
            raise UserError(_(
                'Purchase orders have already been created for this product-wise demand.'
            ))
        purchase_summaries = self.summary_ids.filtered(
            lambda summary: summary.order_action == 'purchase' and not summary.is_action_done
        )
        if not purchase_summaries:
            raise UserError(_('No summary lines are set to Generate Purchase Orders.'))

        wizard = self.env['advance.reorder.po.vendor.wizard'].create({
            'product_wise_reorder_id': self.id,
            'company_id': self.company_id.id,
            'is_subcontracting': False,
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

    def create_purchase_orders_for_warehouse(self, warehouse, order_action='purchase'):
        """Create purchase/subcontract orders for warehouse using vendor mapping."""
        self.ensure_one()
        is_subcontracting = order_action == 'subcontracting'
        if not warehouse:
            raise UserError(_(
                'Please select a warehouse to create %s.'
            ) % (_('subcontracting orders') if is_subcontracting else _('purchase orders')))
        if self.state != 'verified':
            raise UserError(_(
                '%s can only be created from a verified product-wise demand.'
            ) % (_('Subcontracting orders') if is_subcontracting else _('Purchase orders')))

        if is_subcontracting:
            if self.is_subcontracting_created:
                raise UserError(_(
                    'Subcontracting orders have already been created for this product-wise demand.'
                ))
            empty_msg = _('No summary lines are set to Subcontracting.')
            no_created_msg = _(
                'No subcontracting orders were created. Check subcontract BOM subcontractors '
                'for subcontracting summary products.'
            )
        else:
            if self.is_purchase_action_done:
                raise UserError(_(
                    'Purchase orders have already been created for this product-wise demand.'
                ))
            empty_msg = _('No summary lines are set to Generate Purchase Orders.')
            no_created_msg = _(
                'No purchase orders were created. Check that products have demand and that '
                'vendors have supplier pricelist lines on those products.'
            )

        summaries = self.summary_ids.filtered(
            lambda summary: summary.order_action == order_action and not summary.is_action_done
        )
        if not summaries:
            raise UserError(empty_msg)

        vendor_product_dict = self.get_vendor_product_mapping_dict(
            summaries, order_action=order_action
        )
        processed_summaries = self.env['advance.reorder.product.wise.order.summary']
        for vendor_id, product_list in vendor_product_dict.items():
            partner = self.env['res.partner'].browse(vendor_id)
            summary_lines = summaries.filtered(
                lambda summary, products=product_list: summary.product_id.id in products
            )
            if (
                order_action == 'purchase'
                and self.vendor_selection_strategy == 'specific_vendor'
                and partner.vendor_rule in ['both', 'minimum_order_value']
                and self.reorder_amount < self.minimum_reorder_amount
            ):
                raise UserError(_(
                    "Can not create purchase order because reorder doesn't fulfil "
                    "vendor's minimum order amount's rule."
                ))
            if summary_lines:
                self.create_purchase_order(
                    warehouse,
                    partner=partner,
                    summary_lines=summary_lines,
                )
                processed_summaries |= summary_lines

        if not processed_summaries:
            raise UserError(no_created_msg)
        self._mark_summary_lines_done(processed_summaries)
        self._update_state_after_order_creation()
        return True

    def action_create_reorder_manufacturing_orders(self):
        """Open wizard to create manufacturing orders."""
        self.ensure_one()
        if self.production_ids:
            raise UserError(_(
                'Manufacturing orders have already been created for this product-wise demand.'
            ))
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
        """Create manufacturing orders from production summaries."""
        self.ensure_one()
        if self.state != 'verified':
            raise UserError(_(
                'Manufacturing orders can only be created from a verified product-wise demand.'
            ))
        production_summaries = self.summary_ids.filtered(
            lambda summary: (
                summary.order_action == 'production'
                and summary.order_qty > 0
                and not summary.is_action_done
            )
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
        self._mark_summary_lines_done(production_summaries)
        self._update_state_after_order_creation()
        return True

    def action_create_reorder_subcontracting(self):
        """Open warehouse wizard to create subcontract purchase orders."""
        self.ensure_one()
        if self.is_subcontracting_created:
            raise UserError(_(
                'Subcontracting orders have already been created for this product-wise demand.'
            ))
        subcontract_summaries = self.summary_ids.filtered(
            lambda summary: summary.order_action == 'subcontracting' and not summary.is_action_done
        )
        if not subcontract_summaries:
            raise UserError(_('No summary lines are set to Subcontracting.'))

        wizard = self.env['advance.reorder.po.vendor.wizard'].with_context(
            default_is_subcontracting=True,
        ).create({
            'product_wise_reorder_id': self.id,
            'company_id': self.company_id.id,
            'is_subcontracting': True,
        })
        return {
            'name': _('Select Warehouse To Create Subcontract Order'),
            'type': 'ir.actions.act_window',
            'res_model': 'advance.reorder.po.vendor.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
            'context': dict(self.env.context, default_is_subcontracting=True),
        }

    def _prepare_manufacturing_order_vals_from_summary(self, production_summaries, warehouse):
        """Prepare manufacturing order values from summaries."""
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
        """Open linked purchase orders."""
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
        """Open linked manufacturing orders."""
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

    def action_replenishment_count(self):
        """Open linked warehouse replenishment records."""
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id(
            'setu_advance_reordering.actions_advance_procurement_process'
        )
        replenishment = self.mapped('replenishment_ids')
        if len(replenishment) > 1:
            action['domain'] = [('id', 'in', replenishment.ids)]
        elif replenishment:
            form_view = [(
                self.env.ref('setu_advance_reordering.form_advance_procurement_process').id,
                'form',
            )]
            if 'views' in action:
                action['views'] = form_view + [
                    (state, view) for state, view in action['views'] if view != 'form'
                ]
            else:
                action['views'] = form_view
            action['res_id'] = replenishment.id
        return action

    def _get_replenishment_destination_warehouse(self, warehouses):
        """Resolve destination warehouse for product-wise replenishment."""
        self.ensure_one()
        if self.purchase_ids:
            destination = self.purchase_ids[0].picking_type_id.warehouse_id
            if destination:
                return destination
        return warehouses[:1]

    def create_warehouse_replenishment(self):
        """Create replenishment with products that have Generate Purchase Orders in summary."""
        self.ensure_one()
        if self.replenishment_ids:
            raise UserError(_(
                'Warehouse replenishment has already been created for this product-wise demand.'
            ))
        purchase_summaries = self.summary_ids.filtered(
            lambda summary: summary.order_action == 'purchase'
        )
        product_ids = purchase_summaries.mapped('product_id').ids
        if not product_ids:
            raise UserError(_(
                'No summary lines with Generate Purchase Orders action found '
                'to create warehouse replenishment.'
            ))

        warehouses = self._get_company_warehouses()
        destination = self._get_replenishment_destination_warehouse(warehouses)
        if not destination:
            raise UserError(_(
                'No warehouse found to create warehouse replenishment.'
            ))

        replenishment = self.env['advance.procurement.process'].create({
            'warehouse_id': destination.id,
            'procurement_date': datetime.today(),
            'user_id': self.user_id.id,
            'buffer_stock_days': self.buffer_security_days,
            'generate_demand_with': 'history_sales',
            'history_sale_start_date': self.sales_start_date,
            'history_sale_end_date': self.sales_end_date,
            'procurement_demand_growth': self.reorder_demand_growth,
            'config_ids': [(0, 0, {'warehouse_id': warehouse.id}) for warehouse in warehouses],
            'product_ids': [(6, 0, product_ids)],
            'product_wise_reorder_id': self.id,
            'company_id': self.company_id.id,
        })
        for config in replenishment.config_ids:
            config.onchange_warehouse_id()
            config.onchange_transit_days()
            config.onchange_shipment_arrival_date()
        replenishment.onchange_buffer_security_days()
        return True
