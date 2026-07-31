# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare


class SetuInterCompanyTransferLine(models.Model):
    _name = 'setu.intercompany.transfer.line'
    _description = """this is to define how many products will be going to transfer to another warehouse with which price."""

    quantity = fields.Float(string="Quantity", compute='_compute_product_uom_qty', digits='Product Unit of Measure',
                            default=1.0, store=True, readonly=False, required=True, precompute=True)
    unit_price = fields.Float("Price")
    product_packaging_qty = fields.Float(string="Packaging Quantity",
                                         compute='_compute_product_packaging_qty', store=True, readonly=False,
                                         precompute=True)

    product_id = fields.Many2one('product.product', "Product")
    intercompany_transfer_id = fields.Many2one("setu.intercompany.transfer", "Inter Company Transfer", index=True)
    product_uom_category_id = fields.Many2one(related='product_id.uom_id.category_id', depends=['product_id'])
    product_uom_id = fields.Many2one(comodel_name='uom.uom', string="Unit of Measure",
                                     compute='_compute_product_uom', store=True, readonly=False, precompute=True,
                                     ondelete='restrict')
    product_packaging_id = fields.Many2one(comodel_name='product.packaging',
                                           string="Packaging", compute='_compute_product_packaging_id',
                                           store=True, readonly=False, precompute=True,
                                           domain="[('sales', '=', True), ('product_id','=',product_id)]")

    @api.depends('product_id', 'product_packaging_qty')
    def _compute_product_uom_qty(self):
        for line in self:
            if not line.product_packaging_id:
                continue
            packaging_uom = line.product_packaging_id.product_uom_id
            qty_per_packaging = line.product_packaging_id.qty
            product_uom_qty = packaging_uom._compute_quantity(
                line.product_packaging_qty * qty_per_packaging, line.product_uom_id)
            if float_compare(product_uom_qty, line.quantity, precision_rounding=line.product_uom_id.rounding) != 0:
                line.quantity = product_uom_qty

    @api.constrains('quantity')
    def _check_quantity(self):
        for rec in self:
            if rec.quantity <= 0:
                raise ValidationError(_("Quantity should be greater than 0 to do a transfer."))

    @api.onchange('product_id')
    def product_id_change(self):
        for record in self:
            if not record.product_id:
                return
            if record.intercompany_transfer_id and record.intercompany_transfer_id.pricelist_id and record.intercompany_transfer_id.fulfiller_partner_id:
                record.unit_price = record.get_price()

    def get_price(self):
        product_context = dict(self.env.context, partner_id=self.intercompany_transfer_id.fulfiller_partner_id.id,
                               date=self.intercompany_transfer_id.ict_date,
                               default_company_id=self.intercompany_transfer_id.fulfiller_company_id.id)
        params = dict(product_context.get('params', {}))
        params.update(
            {'is_price_list_from_ict': True, 'company_id': self.intercompany_transfer_id.fulfiller_company_id.id})
        product_context['params'] = params
        final_price, rule_id = self.intercompany_transfer_id.pricelist_id.with_context(
            product_context).with_company(
            self.intercompany_transfer_id.fulfiller_company_id)._get_product_price_rule(self.product_id,
                                                                                        self.quantity or 1.0)

        return final_price

    @api.depends('product_id')
    def _compute_product_uom(self):
        for line in self:
            if not line.product_uom_id or (line.product_id.uom_id.id != line.product_uom_id.id):
                line.product_uom_id = line.product_id.uom_id

    @api.depends('product_id', 'quantity', 'product_uom_id')
    def _compute_product_packaging_id(self):
        for line in self:
            if line.product_packaging_id.product_id != line.product_id:
                line.product_packaging_id = False
            if line.product_id and line.quantity and line.product_uom_id:
                suggested_packaging = line.product_id.packaging_ids \
                    .filtered(lambda p: p.sales and (p.product_id.company_id <= p.company_id <= self.env.company)) \
                    ._find_suitable_product_packaging(line.quantity, line.product_uom_id)
                line.product_packaging_id = suggested_packaging or line.product_packaging_id

    @api.depends('product_packaging_id', 'product_uom_id', 'quantity')
    def _compute_product_packaging_qty(self):
        self.product_packaging_qty = 0
        for line in self:
            if not line.product_packaging_id:
                continue
            line.product_packaging_qty = line.product_packaging_id._compute_qty(line.quantity, line.product_uom_id)

    @api.onchange('product_packaging_id')
    def _onchange_product_packaging_id(self):
        if self.product_packaging_id and self.quantity:
            newqty = self.product_packaging_id._check_qty(self.quantity, self.product_uom_id, "UP")
            if float_compare(newqty, self.quantity, precision_rounding=self.product_uom_id.rounding) != 0:
                return {
                    'warning': {
                        'title': _('Warning'),
                        'message': _(
                            "This product is packaged by %(pack_size).2f %(pack_name)s. You should transfer %(quantity).2f %(unit)s.",
                            pack_size=self.product_packaging_id.qty,
                            pack_name=self.product_id.uom_id.name,
                            quantity=newqty,
                            unit=self.product_uom_id.name
                        ),
                    },
                }
