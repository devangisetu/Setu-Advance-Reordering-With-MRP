# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AdvanceReorderPoVendorWizard(models.TransientModel):
    _inherit = 'advance.reorder.po.vendor.wizard'

    reorder_process_id = fields.Many2one(
        'advance.reorder.orderprocess',
        string='Reorder',
        required=False,
        ondelete='cascade',
    )
    product_wise_reorder_id = fields.Many2one(
        'advance.reorder.product.wise.process',
        string='Product-Wise Reorder',
        ondelete='cascade',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
    )
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Warehouse',
        domain="[('company_id', '=', company_id)]",
    )
    show_vendor_selection = fields.Boolean(
        compute='_compute_show_vendor_selection',
    )

    @api.depends(
        'product_wise_reorder_id',
        'product_wise_reorder_id.vendor_selection_strategy',
        'reorder_process_id',
    )
    def _compute_show_vendor_selection(self):
        for rec in self:
            if rec.product_wise_reorder_id:
                rec.show_vendor_selection = rec.product_wise_reorder_id.vendor_selection_strategy in (
                    'on_po_creation',
                    'without_vendor',
                )
            else:
                rec.show_vendor_selection = True

    @api.model_create_multi
    def create(self, vals_list):
        """Preloads purchase demand lines for purchase order generation."""
        records = super().create(vals_list)
        for rec in records:
            if rec.product_wise_reorder_id:
                rec.company_id = rec.product_wise_reorder_id.company_id
                purchase_summaries = rec.product_wise_reorder_id.summary_ids.filtered(
                    lambda summary: summary.order_action == 'purchase'
                )
                if not purchase_summaries:
                    raise UserError(_('No summary lines are set to Generate Purchase Orders.'))
                if not rec.line_ids:
                    rec.line_ids = [
                        (0, 0, {'product_wise_summary_line_id': summary.id})
                        for summary in purchase_summaries
                    ]
                continue
            if not rec.reorder_process_id:
                continue
            purchase_summaries = rec.reorder_process_id.summary_ids.filtered(
                lambda summary: summary.order_action == 'purchase'
            )
            if not purchase_summaries:
                raise UserError(_('No summary lines are set to Generate Purchase Orders.'))
            rec.line_ids.filtered(
                lambda line: line.summary_line_id not in purchase_summaries
            ).unlink()
            if not rec.line_ids and purchase_summaries:
                rec.line_ids = [
                    (0, 0, {'summary_line_id': summary.id}) for summary in purchase_summaries
                ]
        return records

    def action_confirm(self):
        self.ensure_one()
        if self.product_wise_reorder_id:
            return self._action_confirm_product_wise()
        return super().action_confirm()

    def _action_confirm_product_wise(self):
        self.ensure_one()
        if not self.warehouse_id:
            raise UserError(_('Please select a warehouse to create purchase orders.'))

        real_demand = self.product_wise_reorder_id
        if real_demand.state != 'verified':
            raise UserError(_(
                'Purchase orders can only be created from a verified product-wise demand.'
            ))
        if not real_demand.summary_ids.filtered(lambda summary: summary.order_action == 'purchase'):
            raise UserError(_('No summary lines are set to Generate Purchase Orders.'))

        if self.show_vendor_selection:
            for line in self.line_ids:
                if not line.vendor_id:
                    raise UserError(
                        _('Please select a vendor for product %s.') % (line.product_id.display_name,)
                    )
            po_before = len(real_demand.purchase_ids)
            vendor_to_summary_ids = defaultdict(list)
            for wizard_line in self.line_ids:
                if wizard_line.product_wise_summary_line_id:
                    vendor_to_summary_ids[wizard_line.vendor_id].append(
                        wizard_line.product_wise_summary_line_id.id
                    )
            for vendor, summary_ids in vendor_to_summary_ids.items():
                summaries = self.env['advance.reorder.product.wise.order.summary'].browse(summary_ids)
                if summaries:
                    real_demand.create_purchase_order(
                        self.warehouse_id,
                        partner=vendor,
                        summary_lines=summaries,
                    )
            if len(real_demand.purchase_ids) == po_before:
                raise UserError(_(
                    'No purchase orders were created. Check that products have demand and that '
                    'the selected vendors have supplier pricelist lines on those products.'
                ))
            real_demand.write({'state': 'done'})
            return {'type': 'ir.actions.act_window_close'}

        real_demand.create_purchase_orders_for_warehouse(self.warehouse_id)
        return {'type': 'ir.actions.act_window_close'}


class AdvanceReorderPoVendorWizardLine(models.TransientModel):
    _inherit = 'advance.reorder.po.vendor.wizard.line'

    summary_line_id = fields.Many2one(
        'advance.reorder.orderprocess.summary',
        string='Summary line',
        required=False,
        ondelete='cascade',
    )
    product_wise_summary_line_id = fields.Many2one(
        'advance.reorder.product.wise.order.summary',
        string='Product-Wise Summary line',
        ondelete='cascade',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        compute='_compute_line_summary_fields',
        related=False,
        store=True,
        readonly=True,
    )
    demanded_qty = fields.Integer(
        string='Demand',
        compute='_compute_line_summary_fields',
        related=False,
        store=True,
        readonly=True,
    )

    @api.depends(
        'summary_line_id',
        'summary_line_id.product_id',
        'summary_line_id.demanded_qty',
        'product_wise_summary_line_id',
        'product_wise_summary_line_id.product_id',
        'product_wise_summary_line_id.demanded_qty',
    )
    def _compute_line_summary_fields(self):
        for line in self:
            summary = line.product_wise_summary_line_id or line.summary_line_id
            line.product_id = summary.product_id if summary else False
            line.demanded_qty = summary.demanded_qty if summary else 0

    def _get_supplier_info_for_vendor(self, product, vendor, demand_qty):
        self.ensure_one()
        if self.wizard_id.product_wise_reorder_id:
            if not product or not vendor:
                return self.env['product.supplierinfo']
            real_demand = self.wizard_id.product_wise_reorder_id
            company_id = real_demand.company_id or self.env.company
            supplier_lines = product.seller_ids.filtered(
                lambda seller: seller.partner_id in (vendor, vendor.parent_id)
                and (not seller.company_id or seller.company_id == company_id)
            )
            if not supplier_lines:
                return self.env['product.supplierinfo']
            return real_demand._filter_supplier_info_by_moq(supplier_lines, demand_qty)
        return super()._get_supplier_info_for_vendor(product, vendor, demand_qty)

    @api.depends(
        'vendor_id',
        'product_id',
        'summary_line_id',
        'summary_line_id.order_qty',
        'summary_line_id.vendor_moq',
        'summary_line_id.demanded_qty',
        'product_wise_summary_line_id',
        'product_wise_summary_line_id.order_qty',
        'product_wise_summary_line_id.vendor_moq',
        'product_wise_summary_line_id.demanded_qty',
    )
    def _compute_vendor_related_fields(self):
        product_wise_lines = self.filtered('product_wise_summary_line_id')
        for line in product_wise_lines:
            summary = line.product_wise_summary_line_id
            demand_qty = summary.demanded_qty or 0.0
            vendor_moq = summary.vendor_moq or 0.0
            order_qty = summary.order_qty or demand_qty
            supplier_info = line._get_supplier_info_for_vendor(
                line.product_id, line.vendor_id, demand_qty
            )
            if supplier_info:
                vendor_moq = supplier_info.reorder_minimum_quantity or 0.0
                order_qty = max(demand_qty, vendor_moq)
            line.vendor_moq = round(vendor_moq)
            line.order_qty = round(order_qty)
        remaining = self - product_wise_lines
        if remaining:
            super(AdvanceReorderPoVendorWizardLine, remaining)._compute_vendor_related_fields()

    def _sync_summary_vendor_moq(self):
        for line in self:
            if line.product_wise_summary_line_id:
                line.product_wise_summary_line_id.write({'vendor_moq': line.vendor_moq})
        super()._sync_summary_vendor_moq()
