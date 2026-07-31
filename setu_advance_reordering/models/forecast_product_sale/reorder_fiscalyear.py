from odoo import fields, models, api, _
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError, UserError


class ReorderFiscalyear(models.Model):
    _name = 'reorder.fiscalyear'
    _description = "Reorder fiscalyear is used to manage fiscal year for the reordering process"
    _order = "fystartdate desc"

    fystartdate = fields.Date("Start Date")
    fyenddate = fields.Date("End Date")
    code = fields.Char("Code")
    name = fields.Char("Name")
    fp_ids = fields.One2many("reorder.fiscalperiod", "fy_id", "Fiscal Period")

    @api.constrains('fystartdate', 'fyenddate')
    def _check_fiscalyear(self):
        for year in self:
            if year.fyenddate < year.fystartdate:
                raise ValidationError(
                    _('Incorrect fiscal year end date: date must be greater than start date!')
                )
            domain = [('id', '!=', year.id),
                      ('fystartdate', "<", year.fyenddate.strftime("%Y-%m-%d")),
                      ('fyenddate', ">", year.fystartdate.strftime("%Y-%m-%d"))]
            rec = self.search(domain)
            if len(rec) >= 1:
                raise ValidationError(
                    _('Incorrect fiscal year start date or end date: date must not be overlapped')
                )

    def create_monthly_period(self, interval=1):
        period_obj = self.env['reorder.fiscalperiod']
        ds = datetime.strptime(self.fystartdate.strftime('%Y-%m-%d'), '%Y-%m-%d')

        while ds.date() < self.fyenddate:
            de = ds + relativedelta(months=interval, days=-1)

            if de.date() > self.fyenddate:
                de = datetime.strptime(str(self.fyenddate), '%Y-%m-%d')

            period_obj.create({
                'code': ds.strftime('%m/%Y'),
                'fpstartdate': ds.strftime('%Y-%m-%d'),
                'fpenddate': de.strftime('%Y-%m-%d'),
                'fy_id': self.id,
            })
            ds = ds + relativedelta(months=interval)
        return True

    def calculate_actual_sales_for_year(self):
        """
        This method will calculate actual sales year wise.
        """
        for record in self:
            periods = record.fp_ids
            calculative_periods = periods.filtered(lambda x: x.sales_forecast_available)
            if not calculative_periods:
                raise UserError(_('No sales forecast record found for this year to update Actual Sales.'))
            calculative_periods.calculate_actual_sales_for_period()
