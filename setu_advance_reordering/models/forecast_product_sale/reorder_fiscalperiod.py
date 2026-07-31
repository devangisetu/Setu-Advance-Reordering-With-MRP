from odoo import fields, models, api, _


class ReorderFiscalPeriod(models.Model):
    _name = 'reorder.fiscalperiod'
    _description = "Reorder period is used to manage monthly timeframe for reordering"
    _order = "fpstartdate"
    _rec_name = 'code'

    _sql_constraints = [
        (
            'unique_period_by_fiscalyear', 'UNIQUE(fy_id, fpstartdate)',
            'Only one period allowed for specific time frame')
    ]

    code = fields.Char("Code")
    fy_id = fields.Many2one("reorder.fiscalyear", "Fiscal Year", ondelete="cascade")
    fpstartdate = fields.Date("Start Date")
    fpenddate = fields.Date("End Date")
    sales_forecast_available = fields.Boolean(compute="check_sales_forecast_available")

    def find(self, date):
        period = self.search([('fpstartdate', '<=', date), ('fpenddate', '>=', date)], limit=1)
        return period or False

    def check_sales_forecast_available(self):
        """
        This is a compute method which will check whether sales forecast is available or not for a particular period.
        """
        sales_forecast_obj = self.env['forecast.product.sale']
        for record in self:
            sales_forecast = sales_forecast_obj.search([]).filtered(
                lambda x: x.product_id and x.product_id.active and x.period_id == record)
            if sales_forecast:
                record.sales_forecast_available = True
            else:
                record.sales_forecast_available = False

    def calculate_actual_sales_for_period(self):
        """
        This method will calculate actual sales of product period wise.
        :return: It will return a Boolean.
        """
        sales_forecast_obj = self.env['forecast.product.sale']
        for record in self:
            products = {}
            sales_forecasts = sales_forecast_obj.search([]).filtered(
                lambda x: x.product_id and x.product_id.active and x.period_id == record)
            warehouses = sales_forecasts and set(sales_forecasts.mapped('warehouse_id.id')) or {}
            periods = {record.id}
            if warehouses:
                sales_forecast_obj.update_actual_sales_period_wise(products, warehouses, periods)
        return True
