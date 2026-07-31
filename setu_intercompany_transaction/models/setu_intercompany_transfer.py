# -*- coding: utf-8 -*-
from datetime import datetime

from dateutil import relativedelta
from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools import float_compare

STATE = [('draft', 'New'),
         ('in_progress', 'In Progress'),
         ('done', 'Done'),
         ('cancel', 'Cancel')]


class SetuIntercompanyTransfer(models.Model):
    _name = 'setu.intercompany.transfer'
    _order = 'ict_date desc, id desc'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = """Intercompany Transfer
        ==========================================================
        This app is used to keep track of all the transactions between two warehouses, source warehouse
        and destination warehouse can be of same company and can be of different company.
        
        This app will perform following operations.
        -> Inter company transaction (transaction between warehouses of two different companies)
        -> Inter warehouse transaction (transaction between warehouses of same company)
        -> Reverse transactions (Inter company or Inter warehouse)
        
        Advance features
        -> Define inter company rules which will create inter Company transactions record automatically"""

    transfer_with_single_picking = fields.Boolean(string="Direct transfer to destination without transit location?",
                                                  help="""This option is useful to transfer stock between two warehouses directly without moving stock to transit location.
          By default stock will be transferred in two step
              1. Source Location to Transit Location
              2. Transit Location to Destination Location """)

    name = fields.Char(string="Name")

    ict_date = fields.Date(string="Date", copy=False, default=datetime.today())

    transfer_type = fields.Selection([('inter_company', "Inter Company"),
                                      ('inter_warehouse', 'Inter Warehouse'),
                                      ('reverse_transfer', 'Reverse Transfer')], string="Transfer Type")
    state = fields.Selection(STATE, string='State', readonly=True,
                             copy=False, index=True, default='draft', compute='_compute_state', store=True)

    delivery_count = fields.Integer(string='Total Pickings', compute='_compute_picking_ids')
    purchase_count = fields.Integer(string='Total Purchase', compute='_compute_purchase_ids')
    sale_count = fields.Integer(string='Total Sale', compute='_compute_sale_ids')
    invoice_count = fields.Integer(string='Total Invoice', compute='_compute_invoice_ids')

    requestor_warehouse_id = fields.Many2one("stock.warehouse", string="Requestor Warehouse")
    fulfiller_warehouse_id = fields.Many2one("stock.warehouse", string="Fulfiller Warehouse")
    requestor_partner_id = fields.Many2one("res.partner", string="Requestor Partner", change_default=True)
    fulfiller_partner_id = fields.Many2one("res.partner", string="Fulfiller Partner", change_default=True)
    requestor_company_id = fields.Many2one("res.company", string="Requestor Company", change_default=True)
    fulfiller_company_id = fields.Many2one("res.company", string="Fulfiller Company", change_default=True)
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist')
    sales_team_id = fields.Many2one("crm.team", string="Sales Team")
    ict_user_id = fields.Many2one("res.users", string="Inter Company User")
    origin_order_id = fields.Many2one("sale.order", string="Origin Sale Order", copy=False, index=True)
    origin_ict_id = fields.Many2one("setu.intercompany.transfer", string="Origin ICT", copy=False)
    intercompany_channel_id = fields.Many2one("setu.intercompany.channel", string="Intercompany Channel", copy=False)
    interwarehouse_channel_id = fields.Many2one("setu.interwarehouse.channel", string="Interwarehouse Channel",
                                                copy=False)
    auto_workflow_id = fields.Many2one("setu.ict.auto.workflow", string="Auto workflow")
    location_id = fields.Many2one("stock.location", string="Destination location",
                                  help="IWT will be created for this location from the fulfiller warehouse.")

    intercompany_transfer_line_ids = fields.One2many("setu.intercompany.transfer.line", "intercompany_transfer_id",
                                                     "Intercompany Transfer Lines")
    picking_ids = fields.One2many('stock.picking', 'ict_internal_transfer_id', string='Pickings')
    purchase_ids = fields.One2many('purchase.order', 'intercompany_transfer_id', string='Purchases')
    sale_ids = fields.One2many('sale.order', 'intercompany_transfer_id', string='Sales')
    invoice_ids = fields.One2many('account.move', 'intercompany_transfer_id', string='Invoices')

    locations_ids = fields.Many2many('stock.location', string='Locations', compute='_compute_locations_id', store=True)

    @api.depends('picking_ids.state', 'sale_ids.picking_ids.state', 'purchase_ids.picking_ids.state')
    def _compute_state(self):
        for rec in self:
            picking_ids = False
            if all(sale.state == 'sale' for sale in rec.sale_ids) and all(
                    purchase.state == 'purchase' for purchase in rec.purchase_ids):
                picking_ids = rec.sale_ids.picking_ids + rec.purchase_ids.picking_ids
            if rec.picking_ids and all(picking.state == 'done' for picking in rec.picking_ids):
                rec.state = 'done'
            elif picking_ids and all(picking.state == 'done' for picking in picking_ids):
                rec.state = 'done'

    @api.depends('picking_ids')
    def _compute_picking_ids(self):
        for internal_transfer in self:
            internal_transfer.delivery_count = len(internal_transfer.picking_ids)

    @api.depends('invoice_ids')
    def _compute_invoice_ids(self):
        for ict in self:
            ict.invoice_count = len(ict.invoice_ids)

    @api.depends('sale_ids')
    def _compute_sale_ids(self):
        for ict in self:
            ict.sale_count = len(ict.sale_ids)

    @api.depends('purchase_ids')
    def _compute_purchase_ids(self):
        for ict in self:
            ict.purchase_count = len(ict.purchase_ids)

    @api.depends('requestor_warehouse_id.view_location_id')
    def _compute_locations_id(self):
        for record in self:
            if record.requestor_warehouse_id:
                view_location_id = record.requestor_warehouse_id.view_location_id
                if view_location_id:
                    locations = record.env['stock.location'].sudo().search(
                        [('parent_path', 'ilike', '%%/%d/%%' % view_location_id.id),
                         ('usage', '=', 'internal')])
                    if locations:
                        record.locations_ids = locations if locations else False

    @api.onchange('requestor_warehouse_id')
    def onchange_requestor_warehouse_id(self):
        if self.requestor_warehouse_id:
            self.requestor_company_id = self.requestor_warehouse_id.company_id
            self.requestor_partner_id = self.requestor_warehouse_id.company_id.partner_id

    @api.onchange('fulfiller_warehouse_id')
    def onchange_fulfiller_warehouse_id(self):
        if self.fulfiller_warehouse_id:
            self.fulfiller_company_id = self.fulfiller_warehouse_id.company_id
            self.fulfiller_partner_id = self.fulfiller_warehouse_id.company_id.partner_id
            self.pricelist_id = self.fulfiller_partner_id.sudo().with_company(
                self.fulfiller_company_id).property_product_pricelist or False

    @api.onchange('origin_ict_id')
    def onchange_origin_ict_id(self):
        if self.origin_ict_id:
            self.requestor_warehouse_id = self.origin_ict_id.requestor_warehouse_id.id
            self.fulfiller_warehouse_id = self.origin_ict_id.fulfiller_warehouse_id.id
            self.pricelist_id = self.origin_ict_id.pricelist_id.id
            self.transfer_with_single_picking = self.origin_ict_id.transfer_with_single_picking
            self.ict_user_id = self.origin_ict_id.ict_user_id.id
            line_ids = [line.copy(default={'intercompany_transfer_id': self.id}).id for line in
                        self.origin_ict_id.intercompany_transfer_line_ids]
            self.intercompany_transfer_line_ids = [(6, 0, line_ids)]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            transfer_type = vals['transfer_type']
            name = False
            if transfer_type == "inter_company":
                name = self.env['ir.sequence'].next_by_code('setu.intercompany.transfer') or _('New')
            elif transfer_type == "inter_warehouse":
                name = self.env['ir.sequence'].next_by_code('setu.interwarehouse.transfer') or _('New')
            elif transfer_type == "reverse_transfer":
                name = self.env['ir.sequence'].next_by_code('setu.reverse.intercompany.transfer') or _('New')

            vals['name'] = name
            result = super(SetuIntercompanyTransfer, self).create(vals)
        return result

    def unlink(self):
        for record in self:
            document = 'Inter Company Transfer' if record.transfer_type != "inter_warehouse" else "Inter Warehouse " \
                                                                                                  "Transfer"
            if record.state == 'done':
                raise ValidationError("Done %s can not be deleted." % document)
        return super(SetuIntercompanyTransfer, self).unlink()

    def action_validate_internal_transfer(self):
        if self.transfer_with_single_picking:
            self.create_direct_picking()
        else:
            transit_location = self.env['stock.location'].search(
                [('usage', '=', 'transit'), ('company_id', '=', self.requestor_company_id.id)], limit=1)
            if not transit_location:
                raise ValidationError(
                    _("To Create Inter Warehouse Transfer With Transit Location, First Please Create Transit Location."))
            self.create_two_step_pickings()
        self.state = "in_progress"
        return True

    def action_reverse_internal_transfer(self):
        vals = {'origin_ict_id': self.id, 'transfer_type': 'reverse_transfer'}

        rict = self.env['setu.intercompany.transfer'].create(vals)
        rict.onchange_origin_ict_id()
        rict.onchange_requestor_warehouse_id()
        rict.onchange_fulfiller_warehouse_id()

        report_display_views = []
        form_view_id = self.env.ref('setu_intercompany_transaction.setu_reverse_transfer_form').id
        tree_view_id = self.env.ref('setu_intercompany_transaction.setu_reverse_transfer_tree').id
        report_display_views.append((tree_view_id, 'list'))
        report_display_views.append((form_view_id, 'form'))

        return {'name': _('Reverse Transactions'),
                'domain': [('id', 'in', [rict.id])],
                'res_model': 'setu.intercompany.transfer',
                'view_mode': "list,form",
                'type': 'ir.actions.act_window',
                'views': report_display_views,
                }

    def action_validate_reverse_transfer(self):
        if not self.origin_ict_id and self.requestor_warehouse_id.company_id.id == self.fulfiller_warehouse_id.company_id.id:
            if self.transfer_with_single_picking:
                self.create_direct_reverse_picking()
            else:
                self.create_two_step_reverse_pickings()
            self.state = "in_progress"
            return True

        if self.origin_ict_id.transfer_type == "inter_company":
            if self.origin_ict_id.sale_ids.mapped("picking_ids").filtered(lambda x: x.state != "done"):
                raise UserError("You can't create return for undelivered sales")

            if self.origin_ict_id.purchase_ids.mapped("picking_ids").filtered(lambda x: x.state != "done"):
                raise UserError("You can't create return for purchase orders which is not received yet")

            warehouse = self.origin_ict_id.fulfiller_warehouse_id
            picking_type_id = self.origin_ict_id.fulfiller_warehouse_id.in_type_id.id
            partner_id = self.origin_ict_id.with_company(self.fulfiller_company_id).requestor_partner_id.id
            src_location_id = self.with_company(self.fulfiller_company_id).get_customer_location()
            dest_location_id = warehouse.with_company(self.fulfiller_company_id).lot_stock_id.id

            self.with_user(self.ict_user_id).with_company(self.fulfiller_company_id).create_direct_reverse_picking(
                src_location_id=src_location_id, dest_location_id=dest_location_id,
                warehouse=warehouse, partner_id=partner_id, picking_type_id=picking_type_id)

            warehouse = self.origin_ict_id.requestor_warehouse_id
            picking_type_id = self.origin_ict_id.requestor_warehouse_id.out_type_id.id
            partner_id = self.origin_ict_id.with_company(self.requestor_company_id).fulfiller_partner_id.id
            src_location_id = warehouse.with_company(self.requestor_company_id).lot_stock_id.id
            dest_location_id = self.with_company(self.requestor_company_id).get_vendor_location()

            self.with_user(self.ict_user_id).with_company(self.requestor_company_id).create_direct_reverse_picking(
                src_location_id=src_location_id, dest_location_id=dest_location_id,
                warehouse=warehouse, partner_id=partner_id, picking_type_id=picking_type_id)

            self.state = "in_progress"
            return True
        elif self.requestor_warehouse_id.company_id.id != self.fulfiller_warehouse_id.company_id.id:
            warehouse = self.fulfiller_warehouse_id
            picking_type_id = self.fulfiller_warehouse_id.in_type_id.id
            partner_id = self.with_company(self.fulfiller_company_id).requestor_partner_id.id
            src_location_id = self.with_company(self.fulfiller_company_id).get_customer_location()
            dest_location_id = warehouse.with_company(self.fulfiller_company_id).lot_stock_id.id

            self.with_user(self.ict_user_id).with_company(self.fulfiller_company_id).create_direct_reverse_picking(
                src_location_id=src_location_id, dest_location_id=dest_location_id,
                warehouse=warehouse, partner_id=partner_id, picking_type_id=picking_type_id)

            warehouse = self.requestor_warehouse_id
            picking_type_id = self.requestor_warehouse_id.out_type_id.id
            partner_id = self.with_company(self.requestor_company_id).fulfiller_partner_id.id
            src_location_id = warehouse.with_company(self.requestor_company_id).lot_stock_id.id
            dest_location_id = self.with_company(self.requestor_company_id).get_vendor_location()

            self.with_user(self.ict_user_id).with_company(self.requestor_company_id).create_direct_reverse_picking(
                src_location_id=src_location_id, dest_location_id=dest_location_id,
                warehouse=warehouse, partner_id=partner_id, picking_type_id=picking_type_id)

            self.state = "in_progress"
            return True
        elif self.origin_ict_id.transfer_type == "inter_warehouse":
            if self.origin_ict_id.transfer_with_single_picking:
                self.create_direct_reverse_picking()
            else:
                self.create_two_step_reverse_pickings()
            self.state = "in_progress"
            return True
        return True

    def prepare_picking_vals(self, src_location_id=False, dest_location_id=False, warehouse=False, partner_id=False,
                             picking_type_id=False):
        picking_vals = {
            'ict_internal_transfer_id': self.id,
            'partner_id': partner_id or self.requestor_warehouse_id.partner_id.id,
            'origin': self.name,
            'company_id': warehouse and warehouse.company_id.id or self.requestor_company_id.id,
            'picking_type_id': picking_type_id or (
                    warehouse and warehouse.int_type_id.id or self.requestor_warehouse_id.int_type_id.id),
            'location_id': src_location_id or self.fulfiller_warehouse_id.lot_stock_id.id,
            'location_dest_id': dest_location_id or self.requestor_warehouse_id.lot_stock_id.id,
            'state': 'draft',
            'user_id': self.ict_user_id and self.ict_user_id.id or self.env.user.id,
            'scheduled_date': self.origin_order_id and self.origin_order_id.picking_ids and
                              self.origin_order_id.picking_ids[0].scheduled_date or fields.Datetime.now()
        }
        return picking_vals

    def get_transit_location(self):
        return self.env['stock.location'].search(
            [('usage', '=', 'transit'), ('company_id', '=', self.requestor_company_id.id)], limit=1).id

    def get_customer_location(self):
        return self.env['stock.location'].search([('usage', '=', 'customer')], limit=1).id

    def get_vendor_location(self):
        return self.env['stock.location'].search([('usage', '=', 'supplier')], limit=1).id

    def get_location_route(self):
        if self.transfer_with_single_picking:
            return False
        route = self.env['stock.location.route'].search([('supplied_wh_id', '=', self.requestor_warehouse_id.id),
                                                         ('supplier_wh_id', '=', self.fulfiller_warehouse_id.id)])
        return route

    def get_location_rule(self, src_location_id, dest_location_id):
        if self.transfer_with_single_picking:
            return False
        route = self.get_location_route()
        domain = [('route_id', '=', route.id), ('location_src_id', '=', src_location_id.id),
                  ('location_dest_id', '=', dest_location_id.id)]
        return self.env['stock.rule'].search(domain)

    def prepare_move_vals(self, src_location_id=False, dest_location_id=False, warehouse=False, partner_id=False,
                          picking_type_id=False):
        move_vals = []
        group_vals = {'name': self.name,
                      'move_type': 'direct',
                      'partner_id': partner_id or self.requestor_warehouse_id.partner_id.id}
        group = self.env['procurement.group'].create(group_vals)

        for line in self.intercompany_transfer_line_ids:
            if not line.product_id:
                continue
            product_lang = line.product_id.with_prefetch().with_context(
                lang=self.fulfiller_warehouse_id.partner_id.lang,
                partner_id=self.fulfiller_warehouse_id.partner_id.id,
            )
            name = product_lang.display_name or line.product_id.default_code
            move_vals.append((0, 0, {
                'name': name,
                'origin': self.name,
                'company_id': warehouse and warehouse.company_id.id or self.requestor_company_id.id,
                'picking_type_id': picking_type_id or (
                        warehouse and warehouse.int_type_id.id or self.requestor_warehouse_id.int_type_id.id),
                'location_id': src_location_id or self.fulfiller_warehouse_id.lot_stock_id.id,
                'location_dest_id': dest_location_id or self.requestor_warehouse_id.lot_stock_id.id,
                'state': 'draft',
                'product_id': line.product_id.id,
                'product_uom_qty': round(
                    line.product_uom_id._compute_quantity(qty=line.quantity, to_unit=line.product_id.uom_id)),
                'product_uom': line.product_id.uom_id.id,
                'product_packaging_id': line.product_packaging_id.id,
                'group_id': group and group.id or False,
                'date_deadline': self.origin_order_id and self.origin_order_id.picking_ids and
                                 self.origin_order_id.picking_ids[0].scheduled_date or fields.Datetime.now(),

            }))
        return move_vals

    def create_direct_reverse_picking(self, src_location_id=False, dest_location_id=False, warehouse=False,
                                      partner_id=False, picking_type_id=False):
        src_location_id = src_location_id or self.requestor_warehouse_id.lot_stock_id.id
        dest_location_id = dest_location_id or self.fulfiller_warehouse_id.lot_stock_id.id
        warehouse = warehouse or self.requestor_warehouse_id
        partner_id = partner_id or self.fulfiller_warehouse_id.partner_id.id
        picking_vals = self.prepare_picking_vals(src_location_id=src_location_id, dest_location_id=dest_location_id,
                                                 warehouse=warehouse, partner_id=partner_id,
                                                 picking_type_id=picking_type_id)
        picking_vals.update({'move_ids_without_package': self.prepare_move_vals(src_location_id=src_location_id,
                                                                                dest_location_id=dest_location_id,
                                                                                warehouse=warehouse,
                                                                                partner_id=partner_id,
                                                                                picking_type_id=picking_type_id)})

        picking = self.env['stock.picking'].with_company(warehouse.company_id).create(picking_vals)
        picking.with_company(warehouse.company_id).action_confirm()
        picking.with_company(warehouse.company_id).action_assign()
        return picking

    def find_source_dest_location(self):
        dest_location = self.location_id
        requestor_warehouse = self.requestor_warehouse_id
        if not dest_location and requestor_warehouse:
            if requestor_warehouse.reception_steps == 'one_step':
                dest_location = requestor_warehouse.lot_stock_id
            else:
                dest_location = requestor_warehouse.wh_input_stock_loc_id
        return dest_location

    def create_direct_picking(self):
        destination = self.find_source_dest_location()  # source,
        picking_vals = self.prepare_picking_vals(dest_location_id=destination and destination.id or False
                                                 )  # src_location_id=source and source.id or False
        picking_vals.update({'move_ids_without_package': self.prepare_move_vals()})
        picking = self.env['stock.picking'].create(picking_vals)
        picking.with_company(self.fulfiller_company_id).action_confirm()
        picking.with_company(self.fulfiller_company_id).action_assign()
        return picking

    def create_two_step_pickings(self):
        transit_location = self.get_transit_location()
        dest_location_id = self.find_source_dest_location()  # src_location_id,
        src_location_id = self.fulfiller_warehouse_id.lot_stock_id.id
        dest_location_id = dest_location_id.id  # self.location_id and self.location_id.id or self.requestor_warehouse_id.lot_stock_id.id
        picking_type_id = self.fulfiller_warehouse_id.int_type_id.id
        partner_id = self.requestor_warehouse_id.partner_id.id

        # Create first piking from Source Location to Transit Location
        picking_vals = self.prepare_picking_vals(src_location_id=src_location_id, dest_location_id=transit_location,
                                                 warehouse=self.fulfiller_warehouse_id)
        picking_vals.update({'move_ids_without_package': self.prepare_move_vals(src_location_id=src_location_id,
                                                                                dest_location_id=transit_location,
                                                                                warehouse=self.fulfiller_warehouse_id,
                                                                                partner_id=partner_id,
                                                                                picking_type_id=picking_type_id)})
        first_picking = self.env['stock.picking'].create(picking_vals)
        first_picking.with_company(self.fulfiller_company_id).action_confirm()
        first_picking.with_company(self.fulfiller_company_id).action_assign()

        # Create second picking from Transit Location to Destination Location
        picking_type_id = self.requestor_warehouse_id.int_type_id.id
        partner_id = self.requestor_warehouse_id.partner_id.id
        picking_vals = self.prepare_picking_vals(src_location_id=transit_location, dest_location_id=dest_location_id,
                                                 warehouse=self.requestor_warehouse_id, partner_id=partner_id,
                                                 picking_type_id=picking_type_id)
        second_picking = self.env['stock.picking'].create(picking_vals)
        for move in first_picking.move_ids_without_package:
            new_move = move.copy({
                'name': move.name,
                'location_id': transit_location,
                'location_dest_id': dest_location_id,
                'picking_type_id': picking_type_id,
                'move_orig_ids': [(6, 0, [move.id])],
                'picking_id': second_picking.id,
                'state': 'waiting',
            })
        return True

    def create_two_step_reverse_pickings(self):
        transit_location = self.get_transit_location()
        dest_location_id = self.fulfiller_warehouse_id.lot_stock_id.id
        src_location_id = self.requestor_warehouse_id.lot_stock_id.id
        picking_type_id = self.requestor_warehouse_id.int_type_id.id
        partner_id = self.fulfiller_warehouse_id.partner_id.id
        # Create first piking from Source Location to Transit Location
        picking_vals = self.prepare_picking_vals(src_location_id=src_location_id, dest_location_id=transit_location,
                                                 warehouse=self.requestor_warehouse_id, partner_id=partner_id,
                                                 picking_type_id=picking_type_id)
        picking_vals.update({'move_ids_without_package': self.prepare_move_vals(src_location_id=src_location_id,
                                                                                dest_location_id=transit_location,
                                                                                warehouse=self.requestor_warehouse_id,
                                                                                partner_id=partner_id)})
        first_picking = self.env['stock.picking'].create(picking_vals)
        first_picking.with_company(self.fulfiller_company_id).action_confirm()
        first_picking.with_company(self.fulfiller_company_id).action_assign()

        # Create second picking from Transit Location to Destination Location
        picking_type_id = self.fulfiller_warehouse_id.int_type_id.id
        partner_id = self.fulfiller_warehouse_id.partner_id.id
        picking_vals = self.prepare_picking_vals(src_location_id=transit_location, dest_location_id=dest_location_id,
                                                 warehouse=self.fulfiller_warehouse_id, partner_id=partner_id,
                                                 picking_type_id=picking_type_id)
        second_picking = self.env['stock.picking'].create(picking_vals)
        for move in first_picking.move_ids_without_package:
            new_move = move.copy({
                'name': move.name,
                'location_id': transit_location,
                'location_dest_id': dest_location_id,
                'picking_type_id': self.fulfiller_warehouse_id.int_type_id.id,
                'move_orig_ids': [(6, 0, [move.id])],
                'picking_id': second_picking.id,
                'state': 'waiting',
            })
        return True

    def action_validate_intercompany_transfer(self):
        if not self.intercompany_transfer_line_ids:
            raise ValidationError(_("Please add any product to do a transfer."))
        for ict in self:
            if ict.state != 'draft':
                return False
            fulfiller_partner_id = ict.fulfiller_partner_id
            if self.env['ir.module.module'].sudo().search([('name', '=', 'l10n_in'), ('state', '=', 'installed')],
                                                          limit=1) \
                    and fulfiller_partner_id and fulfiller_partner_id.country_id and fulfiller_partner_id.country_id.code == 'IN':
                ict.check_partner_gst_treatment()

            ict.create_sale_order()
            ict.create_purchase_order()
            ict.execute_workflow()
            ict.state = "in_progress"
        return True

    def check_partner_gst_treatment(self):
        self.ensure_one()
        fulfilment_partner = self.fulfiller_partner_id
        if fulfilment_partner and not fulfilment_partner.l10n_in_gst_treatment:
            raise ValidationError('It seems like GST Treatment is missing in the Vendor of this ICT Fulfiller, '
                                  'please fill it and then try to validate this ICT.')

    def create_sale_order(self):
        so_line_vals = self.prepare_sale_order_line_vals()
        fpos = self.intercompany_channel_id.requestor_fiscal_position_id and self.intercompany_channel_id.requestor_fiscal_position_id or False
        if not fpos:
            fpos = self.env['account.fiscal.position'].with_company(self.fulfiller_company_id)._get_fiscal_position(
                self.requestor_partner_id) or False

        team_id = (self.intercompany_channel_id.sales_team_id and self.intercompany_channel_id.sales_team_id)
        so_vals = {
            'company_id': self.fulfiller_company_id.id,
            'partner_id': self.requestor_partner_id.id,
            'user_id': self.env.user.id,
            'intercompany_transfer_id': self.id,
            'order_line': so_line_vals,
            'fiscal_position_id': fpos.id if fpos else False,
            'intercompany_channel_id': self.intercompany_channel_id.id,
            'team_id': team_id and team_id.id or False,
            'pricelist_id': self.pricelist_id.id
        }

        order = self.env['sale.order'].with_user(self.ict_user_id).with_company(self.fulfiller_company_id).create(
            so_vals)
        order._compute_warehouse_id()
        order.write({'payment_term_id': self.origin_order_id.payment_term_id.id,
                     'pricelist_id': self.pricelist_id.id,
                     'team_id': team_id.id})

        if self.intercompany_channel_id.direct_deliver_to_customer:
            shipping_partner_id = self.origin_order_id.partner_shipping_id.id
            order.partner_shipping_id = shipping_partner_id

        if not order.fiscal_position_id:
            order._compute_fiscal_position_id()
        order._compute_team_id()
        if not order.fiscal_position_id and self.intercompany_channel_id and self.intercompany_channel_id.requestor_fiscal_position_id:
            order.fiscal_position_id = self.intercompany_channel_id.requestor_fiscal_position_id.id

        order.warehouse_id = self.fulfiller_warehouse_id.id
        return order

    def prepare_sale_order_line_vals(self):
        so_line_vals = []
        partner = self.requestor_partner_id
        for ict_line in self.intercompany_transfer_line_ids:
            product_lang = ict_line.product_id.with_prefetch().with_context(
                lang=partner.lang,
                partner_id=partner.id,
            )
            name = product_lang.display_name
            if product_lang.description_sale:
                name += '\n' + product_lang.description_sale
            so_line_vals.append((0, 0, {
                'name': name,
                'product_id': ict_line.product_id.id,
                'product_uom_qty': ict_line.quantity,
                'product_uom': ict_line.product_uom_id.id,
                'product_packaging_qty': ict_line.product_packaging_qty,
                'product_packaging_id': ict_line.product_packaging_id.id,
                'price_unit': ict_line.unit_price
            }))
        return so_line_vals

    def _get_date_planned(self, partner_id, product_id, product_qty, start_date):
        days = self.requestor_company_id.po_lead or 0
        days += product_id._select_seller(
            partner_id=partner_id,
            quantity=product_qty,
            date=fields.Date.context_today(self, start_date),
            uom_id=product_id.uom_po_id).delay or 0.0
        date_planned = start_date + relativedelta.relativedelta(days=days)
        return date_planned.strftime(DEFAULT_SERVER_DATETIME_FORMAT)

    def create_purchase_order(self):
        """ Create a purchase order for Inter company
        """
        origins = self.name
        partner = self.fulfiller_partner_id
        purchase_date = datetime.today()
        fiscal_obj = self.env['account.fiscal.position'].sudo()
        fpos = fiscal_obj.with_company(self.requestor_company_id)._get_fiscal_position(partner) or False
        if not fpos:
            fpos = self.intercompany_channel_id and self.intercompany_channel_id.fulfiller_fiscal_position_id or False
        order_line_vals = self._prepare_purchase_order_line_vals(fpos)
        dates = [fields.Datetime.from_string(value[2]['date_planned']) for value in order_line_vals]
        procurement_date_planned = dates and max(dates) or False
        vals = {
            'partner_id': partner.id,
            'user_id': self.ict_user_id and self.ict_user_id.id or self.env.user.id,
            'picking_type_id': self.requestor_warehouse_id.in_type_id.id,
            'company_id': self.requestor_company_id.id,
            'currency_id': partner.with_company(
                self.fulfiller_company_id).property_purchase_currency_id.id or self.fulfiller_company_id.currency_id.id,
            'origin': origins,
            'payment_term_id': partner.with_company(self.requestor_company_id).property_supplier_payment_term_id.id,
            'date_order': purchase_date,
            'fiscal_position_id': fpos.id if fpos else False,
            'order_line': order_line_vals,
            'intercompany_transfer_id': self.id,
            'date_planned': procurement_date_planned,
        }
        return self.env['purchase.order'].with_user(self.ict_user_id).with_company(self.requestor_company_id).create(
            vals)

    def _prepare_purchase_order_line_vals(self, fpos):
        partner = self.fulfiller_partner_id
        po_line_vals = []

        for ict_line in self.intercompany_transfer_line_ids:
            date_planned = self._get_date_planned(partner, ict_line.product_id, ict_line.quantity, datetime.today())
            product_lang = ict_line.product_id.with_prefetch().with_context(
                lang=partner.lang,
                partner_id=partner.id,
            )
            name = product_lang.display_name
            if product_lang.description_purchase:
                name += '\n' + product_lang.description_purchase
            taxes = ict_line.product_id.supplier_taxes_id
            taxes_id = fpos.map_tax(taxes) if fpos else taxes
            if taxes_id:
                taxes_id = taxes_id.filtered(lambda x: x.company_id.id == self.requestor_company_id.id)

            po_line_vals.append((0, 0, {
                'name': name,
                'product_id': ict_line.product_id.id,
                'product_qty': ict_line.quantity,
                'price_unit': ict_line.unit_price,
                'product_uom': ict_line.product_uom_id.id,
                'product_packaging_qty': ict_line.product_packaging_qty,
                'product_packaging_id': ict_line.product_packaging_id.id,
                'date_planned': date_planned,
                'taxes_id': [(6, 0, taxes_id.ids)],
            }))
        return po_line_vals

    def action_validate_ict_so_po(self):
        po_context = {'default_company_id': self.requestor_company_id.id, }
        so_context = {'default_type': 'out_invoice',
                      'default_company_id': self.fulfiller_company_id.id,
                      }
        self.sale_ids.with_company(self.fulfiller_company_id).with_user(self.ict_user_id).with_context(
            so_context).filtered(lambda order: order.state in ('draft', 'sent')).action_confirm()
        self.purchase_ids.with_company(self.requestor_company_id).with_user(self.ict_user_id).with_context(
            po_context).filtered(lambda order: order.state in ('draft', 'sent')).button_confirm()
        return True

    def action_create_ict_invoices(self):
        so_context = {'default_move_type': 'out_invoice',
                      'default_company_id': self.fulfiller_company_id.id,
                      }
        channel_customer_invoice_journal = self.intercompany_channel_id and self.intercompany_channel_id.customer_invoice_journal_id and self.intercompany_channel_id.customer_invoice_journal_id.id or False
        if channel_customer_invoice_journal:
            so_context.update({'default_journal_id': channel_customer_invoice_journal})
        ci_process = False
        if len(self.sale_ids.mapped('order_line').filtered(lambda x: x.product_id.invoice_policy == 'delivery')) > 0:
            if len(self.sale_ids.picking_ids.filtered(lambda x: x.state != 'done')) == 0:
                ci_process = True
        else:
            ci_process = True

        if ci_process and len(self.sale_ids.filtered(lambda x: x.invoice_status == 'to invoice')) > 0:
            self.sale_ids.with_company(self.fulfiller_company_id).with_context(so_context)._create_invoices()
            self.invoice_ids.mapped('date') and self.invoice_ids.write(
                {'invoice_date': self.invoice_ids.mapped('date')[0]})

        vb_process = False
        if len(self.purchase_ids.mapped('order_line').filtered(
                lambda x: x.product_id.purchase_method == 'receive')) > 0:
            if len(self.purchase_ids.picking_ids.filtered(lambda x: x.state != 'done')) == 0:
                vb_process = True
        else:
            vb_process = True

        if vb_process and len(self.purchase_ids.filtered(lambda x: x.invoice_status == 'to invoice')) > 0:
            po_context = {'default_move_type': 'in_invoice',
                          'default_company_id': self.requestor_company_id.id,
                          'default_intercompany_transfer_id': self.id,
                          }
            channel_vendor_bill_journal = self.intercompany_channel_id and self.intercompany_channel_id.vendor_bill_journal_id \
                                          and self.intercompany_channel_id.vendor_bill_journal_id.id or False
            if channel_vendor_bill_journal:
                po_context.update({'default_journal_id': channel_vendor_bill_journal})
            self.purchase_ids.with_company(self.requestor_company_id).with_context(po_context).action_create_invoice()
            purchase_bill_ids = self.invoice_ids.filtered(lambda i: i.move_type == 'in_invoice')
            for purchase_bill_id in purchase_bill_ids:
                purchase_bill_id.write({'invoice_date': fields.Date.today()})

        return True

    def action_validate_ict_invoices(self):
        invoices = self.invoice_ids
        if invoices:
            in_invoices = invoices.filtered(lambda
                                                invoice: invoice.move_type == 'in_invoice' and invoice.amount_total >= 1 and invoice.state not in (
                'posted'))
            in_invoices and in_invoices.action_post()
            out_invoices = invoices.filtered(lambda
                                                 invoice: invoice.move_type == 'out_invoice' and invoice.amount_total >= 1 and invoice.state not in (
                'posted'))
            out_invoices and out_invoices.action_post()

    def action_cancel(self):
        for rec in self:
            msg = ""
            if rec.transfer_type == 'inter_company':
                sale = 'done' in rec.sale_ids.picking_ids.mapped('state')
                purchase = 'done' in rec.purchase_ids.picking_ids.mapped('state')
                if sale or purchase:
                    msg = "[%s] You can't cancel validated inter company transaction!!!" % (rec.name)
                else:
                    rec.sale_ids.filtered(lambda x: x.state != 'cancel')._action_cancel()
                    rec.purchase_ids.filtered(lambda x: x.state != 'cancel').button_cancel()
            elif rec.transfer_type == 'inter_warehouse':
                pickings = 'done' in rec.picking_ids.mapped('state')
                if pickings:
                    msg = "[%s] You can't cancel validated inter warehouse transaction!!!" % (rec.name)
                else:
                    rec.picking_ids.filtered(lambda x: x.state != 'cancel').action_cancel()
            else:
                if rec.state != 'draft':
                    msg = "[%s] You can't cancel validated inter company transaction!!!" % (rec.name)
            if msg:
                raise UserError(msg)
            rec.state = "cancel"
        return True

    def action_view_sale(self):
        action = self.env.ref('sale.action_quotations').sudo().read()[0]
        sales = self.mapped('sale_ids')
        if len(sales) > 1:
            action['domain'] = [('id', 'in', sales.ids)]
        elif sales:
            form_view = [(self.env.ref('sale.view_order_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = sales.id
        return action

    def action_view_purchase(self):
        action = self.env.ref('purchase.purchase_form_action').sudo().read()[0]
        purchases = self.mapped('purchase_ids')
        if len(purchases) > 1:
            action['domain'] = [('id', 'in', purchases.ids)]
        elif purchases:
            form_view = [(self.env.ref('purchase.purchase_order_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = purchases.id
        return action

    def action_view_delivery(self):
        '''
        This function returns an action that display existing delivery orders
        of given sales order ids. It can either be a in a list or in a form
        view, if there is only one delivery order to show.
        '''
        action = self.env.ref('stock.action_picking_tree_all').sudo().read()[0]

        pickings = self.mapped('picking_ids')
        if len(pickings) > 1:
            action['domain'] = [('id', 'in', pickings.ids)]
        elif pickings:
            form_view = [(self.env.ref('stock.view_picking_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = pickings.id

        return action

    def action_view_invoice(self):
        invoices = self.mapped('invoice_ids')
        action = self.env.ref('setu_intercompany_transaction.action_move_invoice').sudo().read()[0]
        if len(invoices) > 1:
            action['domain'] = [('id', 'in', invoices.ids)]
        elif len(invoices) == 1:
            form_view = [(self.env.ref('account.view_move_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = invoices.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def execute_workflow(self):
        if not self.auto_workflow_id:
            return

        if self.auto_workflow_id.validate_ict_so_po:
            self.action_validate_ict_so_po()
        if self.auto_workflow_id.create_ict_invoices:
            self.action_create_ict_invoices()
        if self.auto_workflow_id.validate_ict_invoices:
            self.action_validate_ict_invoices()
        return True

    def action_import_ict_lines(self):
        wizard = self.env['wizard.import.ict.product'].with_context({'transfer_type': self.transfer_type}).wizard_view()
        return wizard
