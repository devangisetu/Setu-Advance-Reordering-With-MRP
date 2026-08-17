# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProductWiseRealDemandPoVendorWizard(models.TransientModel):
    _name = 'advance.reorder.product.real.demand.po.vendor.wizard'
    _description = 'Assign vendors before creating purchase orders (Product-Wise Real Demand)'

    real_demand_id = fields.Many2one(
        'advance.reorder.product.real.demand',
        string='Product-Wise Real Demand',
        required=True,
        ondelete='cascade',
    )
    bulk_vendor_id = fields.Many2one(
        'res.partner',
        string='Vendor for multiple products',
        help='Select a vendor and apply it to selected lines.',
    )
    line_ids = fields.One2many(
        'advance.reorder.product.real.demand.po.vendor.wizard.line',
        'wizard_id',
        string='Products and vendors',
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if not rec.real_demand_id:
                continue
            purchase_summaries = rec.real_demand_id.summary_ids.filtered(
                lambda summary: summary.order_action == 'purchase'
            )
            if not purchase_summaries:
                raise UserError(_('No summary lines are set to Generate Purchase Orders.'))
            if not rec.line_ids:
                rec.line_ids = [
                    (0, 0, {'summary_line_id': summary.id}) for summary in purchase_summaries
                ]
        return records

    def action_confirm(self):
        self.ensure_one()
        real_demand = self.real_demand_id
        if not real_demand.summary_ids:
            raise UserError(_('There are no summary lines to purchase.'))
        for line in self.line_ids:
            if not line.vendor_id:
                raise UserError(
                    _('Please select a vendor for product %s.') % (line.product_id.display_name,)
                )

        po_before = len(real_demand.purchase_ids)
        for warehouse_group, default_warehouse in real_demand._get_order_warehouse_pairs():
            vendor_to_summary_ids = defaultdict(list)
            for wline in self.line_ids:
                summary = wline.summary_line_id
                product = summary.product_id
                demand_line = real_demand.demand_line_ids.filtered(
                    lambda demand, prod=product, wg=warehouse_group: (
                        demand.product_id == prod
                        and demand.warehouse_group_id == wg
                        and demand.demand_adjustment_qty > 0.0
                    )
                )
                if not demand_line and summary.warehouse_group_id != warehouse_group:
                    continue
                vendor_to_summary_ids[wline.vendor_id].append(summary.id)
            for vendor, sum_ids in vendor_to_summary_ids.items():
                summaries = self.env['advance.reorder.product.real.demand.summary'].browse(sum_ids)
                if summaries:
                    real_demand.create_purchase_order(
                        default_warehouse,
                        warehouse_group,
                        partner=vendor,
                        summary_lines=summaries,
                    )

        if len(real_demand.purchase_ids) == po_before:
            raise UserError(_(
                'No purchase orders were created. Check that products have demand for the '
                'configured warehouse groups and that the selected vendors have supplier '
                'pricelist lines on those products.'
            ))
        real_demand.write({'state': 'done'})
        return {'type': 'ir.actions.act_window_close'}

    def action_apply_bulk_vendor(self):
        self.ensure_one()
        if not self.bulk_vendor_id:
            raise UserError(_('Please select a vendor to apply.'))
        target_lines = self.line_ids.filtered(lambda line: line.is_selected)
        if not target_lines:
            raise UserError(_('Please select at least one product line.'))
        target_lines.write({
            'vendor_id': self.bulk_vendor_id.id,
            'is_selected': False,
        })
        self.bulk_vendor_id = False
        return {
            'name': _('Select vendors for purchase'),
            'type': 'ir.actions.act_window',
            'res_model': 'advance.reorder.product.real.demand.po.vendor.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': dict(self.env.context),
        }


class ProductWiseRealDemandPoVendorWizardLine(models.TransientModel):
    _name = 'advance.reorder.product.real.demand.po.vendor.wizard.line'
    _description = 'Product-Wise Real Demand PO vendor wizard line'

    wizard_id = fields.Many2one(
        'advance.reorder.product.real.demand.po.vendor.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )
    summary_line_id = fields.Many2one(
        'advance.reorder.product.real.demand.summary',
        string='Summary line',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one(
        related='summary_line_id.product_id',
        string='Product',
        readonly=True,
    )
    demanded_qty = fields.Integer(
        related='summary_line_id.demanded_qty',
        string='Demand',
        readonly=True,
    )
    order_qty = fields.Integer(
        string='To be ordered',
        compute='_compute_vendor_related_fields',
        readonly=True,
    )
    vendor_moq = fields.Integer(
        string='Vendor MOQ',
        compute='_compute_vendor_related_fields',
        readonly=True,
    )
    vendor_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        help='Supplier for this product on the purchase order.',
    )
    is_selected = fields.Boolean(
        string='Select',
        help='Tick this line to apply the bulk vendor.',
    )

    def _get_supplier_info_for_vendor(self, product, vendor, demand_qty):
        self.ensure_one()
        if not product or not vendor:
            return self.env['product.supplierinfo']

        real_demand = self.wizard_id.real_demand_id
        company_id = real_demand.company_id or self.env.company
        supplier_lines = product.seller_ids.filtered(
            lambda seller: seller.partner_id in (vendor, vendor.parent_id)
            and (not seller.company_id or seller.company_id == company_id)
        )
        if not supplier_lines:
            return self.env['product.supplierinfo']
        return real_demand._filter_supplier_info_by_moq(supplier_lines, demand_qty)

    @api.depends('vendor_id', 'summary_line_id', 'summary_line_id.order_qty', 'summary_line_id.vendor_moq')
    def _compute_vendor_related_fields(self):
        for line in self:
            summary = line.summary_line_id
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

    def _sync_summary_vendor_moq(self):
        for line in self:
            if not line.summary_line_id:
                continue
            line.summary_line_id.write({'vendor_moq': line.vendor_moq})

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
