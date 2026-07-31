from odoo import fields, models


class ForecastBatchImportLine(models.Model):
    _name = 'forecast.batch.import.line'
    _description = "Import Forecast Batch Line"

    forecast_batch_import_id = fields.Many2one('forecast.product.sale.batch.import',
                                               string="Forecast Batch Import")
    sequence = fields.Integer('Sequence')
    sub_attachment_id = fields.Many2one('ir.attachment', string="File")
    state = fields.Selection([('draft', 'Draft'), ('in_progress', 'In progress'),
                              ('cancel', 'Cancel'), ('done', 'Done')],
                             string="State", default='draft')
    done_date = fields.Datetime('Done Date')