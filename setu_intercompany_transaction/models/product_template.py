from odoo import fields, models, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def _price_compute(self, price_type, uom=None, currency=None, company=None, date=False):
        company_obj = self.env['res.company']
        company = company or self.env.company
        date = date or fields.Date.context_today(self)

        context = self.env.context
        if context.get('params', {}) and context.get('params').get('is_price_list_from_ict', False):
            company = company_obj.browse(context.get('params').get('company_id'))

        self = self.with_company(company)
        if price_type == 'standard_price':
            # standard_price field can only be seen by users in base.group_user
            # Thus, in order to compute the sale price from the cost for users not in this group
            # We fetch the standard price as the superuser
            self = self.sudo()

        prices = dict.fromkeys(self.ids, 0.0)
        for template in self:
            price = template[price_type] or 0.0
            price_currency = template.currency_id
            if price_type == 'standard_price':
                if not price and template.product_variant_ids:
                    price = template.product_variant_ids[0].standard_price
                price_currency = template.cost_currency_id
            elif price_type == 'list_price':
                price += template._get_attributes_extra_price()

            if uom:
                price = template.uom_id._compute_price(price, uom)

            # Convert from current user company currency to asked one
            # This is right cause a field cannot be in more than one currency
            if currency:
                price = price_currency._convert(price, currency, company, date)

            prices[template.id] = price
        return prices
