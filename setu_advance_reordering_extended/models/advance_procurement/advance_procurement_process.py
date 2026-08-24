# -*- coding: utf-8 -*-
from odoo import fields, models


class AdvanceProcurementProcess(models.Model):
    _inherit = 'advance.procurement.process'

    show_subcontracting_qty = fields.Boolean(
        string="Show Resupply Qty",
        related='company_id.use_subcontracting_for_demand',
        store=True,
    )
    show_scrap_qty = fields.Boolean(
        string="Show Scrap Qty",
        related='company_id.use_scrap_for_demand',
        store=True,
    )

    def get_history_sales(self, products, warehouses, start_date, end_date):
        """Get sales history data grouped by product, same as real demand."""
        start_date = start_date.strftime("%Y-%m-%d")
        end_date = end_date and end_date.strftime("%Y-%m-%d")
        query = """Select product_id,product_name,sum(sales) as sales,sum(sales_return) as sales_return,
                sum(total_sales) as total_sales,sum(ads) as ads from
                get_products_sales_warehouse_group_wise('%s','%s','%s','%s','%s','%s')
                group by product_id,product_name
        """ % ('{}', products, '{}', warehouses, start_date, end_date)
        self._cr.execute(query)
        return self._cr.dictfetchall()

    def get_sales_data(self, config, line_product_ids=None, is_sfg=False):
        """Retrieves sales or forecast demand data for eligible products based on the configured demand source"""
        if line_product_ids is None:
            line_product_ids = self.product_ids
        sales_driven_products = line_product_ids
        if not is_sfg:
            sales_driven_products = line_product_ids.filtered(
                lambda pr: pr.is_kit_component or pr.demand_planning_type in ('sales_driven', 'combined'))
        products = sales_driven_products and set(sales_driven_products.ids) or {}
        if not products:
            return []
        warehouses = config.warehouse_id and set(config.warehouse_id.ids) or {}
        if self.generate_demand_with == 'history_sales':
            return self.get_history_sales(
                products, warehouses, self.history_sale_start_date, self.history_sale_end_date
            )
        return self.get_forecast_sales(products, warehouses, config)

    def get_production_data(self, config, line_product_ids):
        """Retrieves production consumption history and ADS for production-driven products."""
        if not self.history_sale_start_date or not self.history_sale_end_date or not line_product_ids:
            return []

        production_driven_products = line_product_ids.filtered(
            lambda pr: pr.demand_planning_type != 'sales_driven')
        products = set(production_driven_products.ids) if production_driven_products else set()
        if not products:
            return []

        warehouses = config.warehouse_id and set(config.warehouse_id.ids) or {}
        start_date = self.history_sale_start_date.strftime('%Y-%m-%d')
        end_date = self.history_sale_end_date.strftime('%Y-%m-%d')

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
        """Retrieves subcontracting resupply history and ADS for production-driven products."""
        if not self.history_sale_start_date or not self.history_sale_end_date or not line_product_ids:
            return []

        if not self.company_id.use_subcontracting_for_demand:
            return []

        production_driven_products = line_product_ids.filtered(
            lambda pr: pr.is_kit_component or pr.demand_planning_type != 'sales_driven')
        products = set(production_driven_products.ids) if production_driven_products else set()
        if not products:
            return []

        warehouses = config.warehouse_id and set(config.warehouse_id.ids) or {}
        start_date = self.history_sale_start_date.strftime('%Y-%m-%d')
        end_date = self.history_sale_end_date.strftime('%Y-%m-%d')

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
        """Retrieves scrap history and ADS for the selected products."""
        if not self.history_sale_start_date or not self.history_sale_end_date or not line_product_ids:
            return []

        if not self.company_id.use_scrap_for_demand:
            return []

        products = set(line_product_ids.ids)
        if not products:
            return []

        warehouses = config.warehouse_id and set(config.warehouse_id.ids) or {}
        start_date = self.history_sale_start_date.strftime('%Y-%m-%d')
        end_date = self.history_sale_end_date.strftime('%Y-%m-%d')

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
        """
        Merges sales, production, resupply, and scrap data into a single product-wise demand summary with calculated ADS.
        """
        if not any((sales_data, production_data, resupply_data, scrap_data)):
            return []

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
            ads_values = []

            if sales:
                ads_values.append(sales.get('ads', 0.0))
            if production:
                ads_values.append(production.get('ads', 0.0))
            if resupply:
                ads_values.append(resupply.get('ads', 0.0))
            if scrap:
                ads_values.append(scrap.get('ads', 0.0))

            avg_ads = sum(ads_values) if ads_values else 0.0

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
                'ads': avg_ads,
                # Preserve forecast-sales fields used by prepare_reorder_line_vals
                'lead_days_demand_stock': sales.get('lead_days_demand_stock', 0.0),
                'expected_sales_stock': sales.get('expected_sales_stock', 0.0),
            })
        return merged

    def prepare_reorder_line_vals(self, config, sales_data, generate_demand_with):
        """Prepare replenishment line vals and store real-demand quantity breakdown."""
        vals = super().prepare_reorder_line_vals(config, sales_data, generate_demand_with)
        qty_by_product = {
            data.get('product_id'): {
                'sales_qty': data.get('sales_qty', 0),
                'sales_return_qty': data.get('sales_return', 0),
                'consumed_qty': data.get('consumed_qty', 0),
                'resupply_qty': data.get('resupply_qty', 0),
                'resupply_return_qty': data.get('resupply_return_qty', 0),
                'scrap_qty': data.get('scrap_qty', 0),
            }
            for data in sales_data
        }
        for command in vals:
            if command[0] == 0 and command[2]:
                extra = qty_by_product.get(command[2].get('product_id'))
                if extra:
                    command[2].update(extra)
        for line in self.line_ids.filtered(lambda l: l.warehouse_id == config.warehouse_id):
            extra = qty_by_product.get(line.product_id.id)
            if extra:
                line.write(extra)
        return vals

    def action_procurement_confirm(self):
        """
        Override to merge sales and production consumption ADS per product planning type.
        Same approach as advance reorder with real demand.

        For each config:
          1. Fetch sales data (via get_sales_data).
          2. Fetch production consumption data (via get_production_data).
          3. Fetch Scrap data (via get_scrap_data).
          4. Fetch Resupply data (via get_resupply_data).
          5. Merge all datasets per product demand_planning_type:
               - sales_driven     → sales data only
               - production_driven → production consumption(production + resupply) ADS replaces sales ADS
               - combined         → combined ADS = sales_ads + production_ads + scrap_ads
          6. Pass merged data to prepare_reorder_line_vals as usual.
        """
        self.check_configuration_product()
        vals = []
        procurement_vals = {}
        for config in self.config_ids:
            line_product_ids = self.product_ids
            sales_data = self.get_sales_data(config, line_product_ids)
            if self.generate_demand_with == 'history_sales' and line_product_ids:
                production_data = self.get_production_data(config, line_product_ids)
                scrap_data = self.get_scrap_data(config, line_product_ids)
                resupply_data = self.get_resupply_data(config, line_product_ids)
                demand_data = self._merge_ads_data(
                    sales_data, production_data, resupply_data, scrap_data
                )
            else:
                demand_data = sales_data
            vals.extend(self.prepare_reorder_line_vals(config, demand_data, self.generate_demand_with))
        if not self.state == 'inprogress':
            procurement_vals = {'state': 'unable_to_replenish'}
        vals and procurement_vals.update({'line_ids': vals, 'state': 'inprogress'})
        self.write(procurement_vals)
        return True
