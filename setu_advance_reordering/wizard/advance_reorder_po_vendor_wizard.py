# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AdvanceReorderPoVendorWizard(models.TransientModel):
    _name = 'advance.reorder.po.vendor.wizard'
    _description = 'Assign vendors before creating purchase orders'

    reorder_process_id = fields.Many2one(
        'advance.reorder.orderprocess', string='Reorder', required=True, ondelete='cascade')
    bulk_vendor_id = fields.Many2one(
        'res.partner',
        string='Vendor for multiple products',
        help='Select a vendor and apply it to selected lines.')
    line_ids = fields.One2many(
        'advance.reorder.po.vendor.wizard.line', 'wizard_id', string='Products and vendors')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if not rec.line_ids and rec.reorder_process_id.summary_ids:
                rec.line_ids = [(0, 0, {'summary_line_id': s.id}) for s in rec.reorder_process_id.summary_ids]
        return records

    def action_confirm(self):
        self.ensure_one()
        reorder = self.reorder_process_id
        if not reorder.summary_ids:
            raise UserError(_('There are no summary lines to purchase.'))
        for line in self.line_ids:
            if not line.vendor_id:
                raise UserError(
                    _('Please select a vendor for product %s.') % (line.product_id.display_name,))
        po_before = len(reorder.purchase_ids)
        for config in reorder.config_ids:
            default_wh = config.default_warehouse_id
            wh_group = config.warehouse_group_id
            vendor_to_summary_ids = defaultdict(list)
            for wline in self.line_ids:
                summary = wline.summary_line_id
                product = summary.product_id
                reorder_line = reorder.line_ids.filtered(
                    lambda r, prod=product, wg=wh_group: r.product_id == prod
                    and r.warehouse_group_id == wg
                    and r.demand_adjustment_qty > 0.0)
                if not reorder_line:
                    continue
                vendor_to_summary_ids[wline.vendor_id].append(summary.id)
            for vendor, sum_ids in vendor_to_summary_ids.items():
                summaries = self.env['advance.reorder.orderprocess.summary'].browse(sum_ids)
                if summaries:
                    reorder.create_purchase_order(
                        default_wh, wh_group, partner=vendor, summary_lines=summaries)
        if len(reorder.purchase_ids) == po_before:
            raise UserError(_(
                'No purchase orders were created. Check that products have demand for the configured warehouse groups and that the selected vendors have supplier pricelist lines on those products.'))
        reorder.write({'state': 'done'})
        return {'type': 'ir.actions.act_window_close'}

    def action_apply_bulk_vendor(self):
        self.ensure_one()
        if not self.bulk_vendor_id:
            raise UserError(_('Please select a vendor to apply.'))
        bulk_vendor = self.bulk_vendor_id
        target_lines = self.line_ids.filtered(lambda line: line.is_selected)
        if not target_lines:
            raise UserError(_('Please select at least one product line.'))
        target_lines.write({
            'vendor_id': bulk_vendor.id,
            'is_selected': False,
        })
        self.bulk_vendor_id = False
        return {
            'name': _('Select vendors for purchase'),
            'type': 'ir.actions.act_window',
            'res_model': 'advance.reorder.po.vendor.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': dict(self.env.context),
        }


class AdvanceReorderPoVendorWizardLine(models.TransientModel):
    _name = 'advance.reorder.po.vendor.wizard.line'
    _description = 'Reorder PO vendor wizard line'

    wizard_id = fields.Many2one(
        'advance.reorder.po.vendor.wizard', string='Wizard', required=True, ondelete='cascade')
    summary_line_id = fields.Many2one(
        'advance.reorder.orderprocess.summary', string='Summary line', required=True, ondelete='cascade')
    product_id = fields.Many2one(
        related='summary_line_id.product_id', string='Product', readonly=True)
    demanded_qty = fields.Integer(related='summary_line_id.demanded_qty', string='Demand', readonly=True)
    order_qty = fields.Integer(
        string='To be ordered',
        compute='_compute_vendor_related_fields',
        readonly=True)
    vendor_moq = fields.Integer(
        string='Vendor MOQ',
        compute='_compute_vendor_related_fields',
        readonly=True)
    vendor_id = fields.Many2one(
        'res.partner', string='Vendor',
        help='Supplier for this product on the purchase order.')
    is_selected = fields.Boolean(
        string='Select',
        help='Tick this line to apply the bulk vendor.')

    def _get_supplier_info_for_vendor(self, product, vendor, demand_qty):
        self.ensure_one()
        if not product or not vendor:
            return self.env['product.supplierinfo']

        reorder = self.wizard_id.reorder_process_id
        company_id = self.env.company
        if reorder.config_ids and reorder.config_ids[0].default_warehouse_id:
            company_id = reorder.config_ids[0].default_warehouse_id.company_id

        supplier_lines = product.seller_ids.filtered(
            lambda seller: seller.partner_id in (vendor, vendor.parent_id)
            and (not seller.company_id or seller.company_id == company_id)
        )
        if not supplier_lines:
            return self.env['product.supplierinfo']
        return reorder._filter_supplier_info_by_moq(supplier_lines, demand_qty)

    @api.depends('vendor_id', 'summary_line_id', 'summary_line_id.order_qty', 'summary_line_id.vendor_moq')
    def _compute_vendor_related_fields(self):
        for line in self:
            summary = line.summary_line_id
            demand_qty = summary.demanded_qty or 0.0

            # Default to summary values until a vendor is selected.
            vendor_moq = summary.vendor_moq or 0.0
            order_qty = summary.order_qty or demand_qty

            supplier_info = line._get_supplier_info_for_vendor(line.product_id, line.vendor_id, demand_qty)
            if supplier_info:
                vendor_moq = supplier_info.reorder_minimum_quantity or 0.0
                order_qty = max(demand_qty, vendor_moq)

            line.vendor_moq = round(vendor_moq)
            line.order_qty = round(order_qty)

    def _sync_summary_vendor_moq(self):
        for line in self:
            if not line.summary_line_id:
                continue
            vals = {'vendor_moq': line.vendor_moq}
            if 'vendor_id' in line.summary_line_id._fields:
                vals['vendor_id'] = line.vendor_id.id if line.vendor_id else False
            line.summary_line_id.write(vals)

    @api.onchange('vendor_id')
    def _onchange_vendor_id_sync_summary(self):
        self._compute_vendor_related_fields()
        self._sync_summary_vendor_moq()

    def write(self, vals):
        result = super().write(vals)
        if 'vendor_id' in vals:
            self._compute_vendor_related_fields()
            self._sync_summary_vendor_moq()
        return result
