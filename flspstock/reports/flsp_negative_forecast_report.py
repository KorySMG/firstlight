from odoo import fields, models, api, _
from psycopg2 import Error
import logging
_logger = logging.getLogger(__name__)

class FlspNegativeForecastStock(models.Model):
    _name = 'flsp.negative.forecast.stock'
    _description = "Negative Forecasted Stock"

    product_id = fields.Many2one('product.product', string='Product')
    product_name = fields.Char(related='product_id.display_name', string='Product Name')
    prod_purcahseable = fields.Boolean(compute='_compute_purcahseable', string='Purcahseable', store=True)
    prod_manufacturable = fields.Boolean(compute='_compute_manufacturable', string='Manufacturable', store=True)
    negative_forecast_qty = fields.Float(string='Negative Qty')
    negative_forecast_date = fields.Datetime(string='Negative Forecast Date')
    non_negative_forecast_qty = fields.Float(string='Non Negative Qty')
    non_negative_forecast_date = fields.Datetime(string='Non Negative Forecast Date')
    duration = fields.Float('Duration', compute='_compute_duration')

    @api.depends('negative_forecast_date', 'non_negative_forecast_date')
    def _compute_duration(self):
        for r in self:
            if r.negative_forecast_date and r.non_negative_forecast_date:
                elapsed_seconds = (r.non_negative_forecast_date - r.negative_forecast_date).total_seconds()
                seconds_in_day = 24 * 60 * 60
                r.duration = elapsed_seconds / seconds_in_day
            else:
                r.duration = False
    
    @api.depends('product_id')
    def _compute_purcahseable(self):
        route_buy = self.env.ref('purchase_stock.route_warehouse0_buy').id
        for r in self:
            if route_buy in r.product_id.route_ids.ids:
                r.product_id.flsp_route_buy = 'buy'
                r.prod_purcahseable = True
            else:
                r.product_id.flsp_route_buy = 'na'
                r.prod_purcahseable = False
    
    @api.depends('product_id')
    def _compute_manufacturable(self):
        route_mfg = self.env.ref('mrp.route_warehouse0_manufacture').id
        for r in self:
            if route_mfg in r.product_id.route_ids.ids:
                r.product_id.flsp_route_mfg = 'mfg'
                r.prod_manufacturable = True
            else:
                r.product_id.flsp_route_mfg = 'na'
                r.prod_manufacturable = False

    @api.model
    def _update_data(self):
        query_unlink = """ DELETE FROM flsp_negative_forecast_stock"""

        query_create = """WITH
                        neg AS (
                            SELECT product_id, min(date) as date
                            FROM report_stock_quantity
                            WHERE date >= current_date and company_id = %s and product_qty < 0 and state = 'forecast'
                            GROUP BY product_id
                        ),
                        negreport AS (
                            SELECT r.product_id, r.date, r.product_qty
                            FROM report_stock_quantity as r,neg
                            WHERE r.product_id = neg.product_id and r.date = neg.date and r.company_id = %s and r.state = 'forecast'
                        ),
                        nonneg AS (
                            SELECT r.product_id, min(r.date) as date
                            FROM report_stock_quantity as r,neg
                            WHERE r.product_id = neg.product_id and r.date > neg.date and r.company_id = %s and r.product_qty >= 0 and r.state = 'forecast'
                            GROUP BY r.product_id
                        ),
                        nonnegreport AS (
                            SELECT r.product_id, r.date, r.product_qty
                            FROM report_stock_quantity as r,nonneg
                            WHERE r.product_id = nonneg.product_id and r.date = nonneg.date and r.company_id = %s  and r.state = 'forecast'
                        )
                    INSERT INTO flsp_negative_forecast_stock (product_id, negative_forecast_date, negative_forecast_qty, non_negative_forecast_date, non_negative_forecast_qty)
                    SELECT negreport.product_id, negreport.date, negreport.product_qty, nonnegreport.date, nonnegreport.product_qty
                    FROM negreport
				    LEFT JOIN nonnegreport
                    ON negreport.product_id = nonnegreport.product_id
                """
        query_create_params = (self.env.company.id, self.env.company.id, self.env.company.id, self.env.company.id)

        try:
            with self.env.cr.savepoint():
                self.env.cr.execute(query_unlink)
                self.env.cr.execute(query_create, query_create_params)
        except Error as e:
            _logger.info("an error occured while updating database 'flsp_negative_forecast_stock': %s", e.pgerror)

    @api.model
    def action_view_negative_forecast(self):
        # update data in DB
        self._update_data()

        # set view for the page to show up
        action = {
            'name': _('Negative Forecasted Inventory'),
            'res_model': 'flsp.negative.forecast.stock',
            'view_mode': 'tree', 
            'type': 'ir.actions.act_window',
            'context': {},
            'help': """
                <p class="o_view_nocontent_empty_folder">No Negative Forecasted Inventory</p>
                """
        }
        
        return action