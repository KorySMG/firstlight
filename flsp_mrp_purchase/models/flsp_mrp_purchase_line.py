# -*- coding: utf-8 -*-

import datetime
from odoo import models, fields, api
from datetime import timedelta
from datetime import datetime
from odoo.exceptions import UserError

class FlspMrppurchaseLine(models.Model):
    _name = 'flsp.mrp.purchase.line'
    _description = 'FLSP MRP purchase Line'

    description = fields.Char(string='Description', readonly=True)
    default_code = fields.Char(string='Part #', readonly=True)
    product_tmpl_id = fields.Many2one('product.template', string='Product', readonly=True)
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    stock_picking = fields.Many2one('stock.picking', string='Stock Picking', readonly=False)
    production_id = fields.Many2one('mrp.production', string='Manufacturing Order', readonly=False)
    product_min_qty = fields.Float('Min. Qty', readonly=True)
    product_max_qty = fields.Float('Max. Qty', readonly=True)
    qty_multiple = fields.Float('Qty Multiple', readonly=True)
    product_qty = fields.Float(string='Qty on Hand', readonly=True)
    qty_mo = fields.Float(string='Qty of Draft MO', readonly=True)
    curr_outs = fields.Float(String="Demand", readonly=True, help="Includes all confirmed sales orders and manufacturing orders")
    curr_ins = fields.Float(String="Replenishment", readonly=True, help="Includes all confirmed purchase orders and manufacturing orders")
    average_use = fields.Float(String="Avg Use", readonly=True, help="Average usage of the past 3 months.")
    month1_use = fields.Float(String="2020-06 Usage", readonly=True, help="Total usage of last month.")
    month2_use = fields.Float(String="2020-05 Usage", readonly=True, help="Total usage of 2 months ago.")
    month3_use = fields.Float(String="2020-04 Usage", readonly=True, help="Total usage of 3 months ago.")
    suggested_qty = fields.Float(String="Suggested Qty", readonly=True, help="Quantity suggested to buy or produce.")
    adjusted_qty = fields.Float(String="Adjusted Qty", help="Adjust the quantity to be executed.")
    qty_rfq = fields.Float(String="RFQ Qty", readonly=True, help="Total Quantity of Requests for Quotation.")
    level_bom = fields.Integer(String="BOM Level", readonly=True, help="Position of the product inside of a BOM.")
    route_buy = fields.Selection([('buy', 'To Buy'),('na' , 'Non Applicable'),], string='To Buy', readonly=True)
    route_mfg = fields.Selection([('mfg', 'To Manufacture'),('na' , 'Non Applicable'),], string='To Produce', readonly=True)
    state = fields.Selection([
        ('buy', 'To Buy'),
        ('ok' , 'No Action'),
        ('po' , 'Confirm PO'),
        ('mo' , 'Confirm MO'),
        ('mfg', 'To Manufacture'),
    ], string='State', readonly=True)
    type = fields.Char(string='Type', readonly=True)
    start_date = fields.Date(String="Start Date", readonly=True)
    deadline_date = fields.Date(String="Deadline", readonly=True)
    rationale = fields.Html(string='Rationale')
    source = fields.Char(string='Source')
    source_description = fields.Char(string='Source Description')
    calculated = fields.Boolean('Calculated Flag')

    stock_qty    = fields.Float(string='Stock Qty', readonly=True)
    wip_qty      = fields.Float(string='WIP Qty', readonly=True)
    vendor_id    = fields.Many2one('res.partner', string='Supplier')
    vendor_qty   = fields.Float(string='Quantity', readonly=True)
    vendor_price = fields.Float(string='Price', readonly=True)
    delay = fields.Integer(string="Delivery Lead Time")
    required_by = fields.Date(String="Required by", readonly=True)

    qty_month1 = fields.Float(string='January')
    qty_month2 = fields.Float(string='February')
    qty_month3 = fields.Float(string='March')
    qty_month4 = fields.Float(string='April')
    qty_month5 = fields.Float(string='May')
    qty_month6 = fields.Float(string='June')
    qty_month7 = fields.Float(string='July')
    qty_month8 = fields.Float(string='August')
    qty_month9 = fields.Float(string='September')
    qty_month10 = fields.Float(string='October')
    qty_month11 = fields.Float(string='November')
    qty_month12 = fields.Float(string='December')

    consumption_month1 = fields.Float(string='Consumption January')
    consumption_month2 = fields.Float(string='Consumption February')
    consumption_month3 = fields.Float(string='Consumption March')
    consumption_month4 = fields.Float(string='Consumption April')
    consumption_month5 = fields.Float(string='Consumption May')
    consumption_month6 = fields.Float(string='Consumption June')
    consumption_month7 = fields.Float(string='Consumption July')
    consumption_month8 = fields.Float(string='Consumption August')
    consumption_month9 = fields.Float(string='Consumption September')
    consumption_month10 = fields.Float(string='Consumption October')
    consumption_month11 = fields.Float(string='Consumption November')
    consumption_month12 = fields.Float(string='Consumption December')

    def _flsp_calc_purchase(self, standard_lead_time=1, standard_queue_time=1, indirect_lead_time=1, consider_drafts=True, consider_wip=True, consider_forecast=True):
        current_date = datetime.now()
        required_by = current_date
        route_mfg = self.env.ref('mrp.route_warehouse0_manufacture').id
        route_buy = self.env.ref('purchase_stock.route_warehouse0_buy').id

        delivery_stock_type = self.env['stock.picking.type'].search([('name', '=', 'Delivery Orders')]).ids
        receipt_stock_type = self.env['stock.picking.type'].search([('name', '=', 'Receipts')]).ids

        pa_location = self.env['stock.location'].search([('complete_name', '=', 'WH/PA')]).parent_path
        if not pa_location:
            raise UserError('WIP Stock Location is missing')
        pa_wip_locations = self.env['stock.location'].search([('parent_path', 'like', pa_location+'%')]).ids
        if not pa_wip_locations:
            raise UserError('WIP Stock Location is missing')

        mrp_purchase_product = self.env['flsp.mrp.purchase.line'].search([])
        for purchase in mrp_purchase_product:  ##delete not used
            purchase.unlink()

        # components within BOM
        # bom_components = self._get_flattened_totals(self.bom_id, self.product_qty)
        open_moves = []
        # index  type, source,     doc,          product_id,   qty,  uom   date                  level  lead time
        #         IN   Purchase    WH/IN/P0001       32          5   each  2020-01-01 00:00:00     1        1
        #         IN   Manufacture WH/MO/M0001       32          5   each  2020-01-01 00:00:00     1        1
        #        OUT   Sales       WH/OUT/P0001      33          8   each  2020-01-01 00:00:00     1        1
        #        OUT   Manufacture WH/MO/M0001       32          5   each  2020-01-01 00:00:00     1        1

        # *******************************************************************************
        # ***************************** Purchase Orders *********************************
        # *******************************************************************************
        open_receipts = self.env['stock.picking'].search(['&', ('state', 'not in', ['done', 'cancel', 'draft']),('picking_type_id', 'in', receipt_stock_type)])
        for receipt in open_receipts:
            stock_move_product = self.env['stock.move'].search([('picking_id', '=', receipt.id)])
            for move in stock_move_product:
                open_moves.append([len(open_moves) + 1, 'In   ', 'Purchase',
                                   receipt.origin,
                                   move.product_id,
                                   move.product_uom_qty, move.product_uom,
                                   receipt.scheduled_date, 0, 0])
        # *******************************************************************************
        # ***************************** Sales Orders ************************************
        # *******************************************************************************
        open_deliveries = self.env['stock.picking'].search(['&', ('state', 'not in', ['done', 'cancel', 'draft']), ('picking_type_id', 'in', delivery_stock_type)])
        for delivery in open_deliveries:
            stock_move_product = self.env['stock.move'].search([('picking_id', '=', delivery.id)])
            for move in stock_move_product:
                move_bom = self.env['mrp.bom'].search([('product_tmpl_id', '=', move.product_id.product_tmpl_id.id)], limit=1)
                if not move_bom:
                    open_moves.append([len(open_moves) + 1, 'Out  ', 'Sales   ',
                                       receipt.origin,
                                       move.product_id,
                                       move.product_uom_qty, move.product_uom,
                                       receipt.scheduled_date, 0, standard_lead_time ])
                else:
                    move_components = self._get_flattened_totals(move_bom, move.product_uom_qty)
                    for prod in move_components:
                        if prod.type in ['service', 'consu']:
                            continue
                        if move_components[prod]['total'] <= 0:
                            continue
                        open_moves.append([len(open_moves) + 1, 'Out  ', 'Sales   ',
                                           delivery.origin,
                                           prod,
                                           move_components[prod]['total'], prod.uom_id.id,
                                           delivery.scheduled_date, move_components[prod]['level'], standard_lead_time+(indirect_lead_time*move_components[prod]['level'])])
        # *******************************************************************************
        # ************************ Manufacturing Orders *********************************
        # *******************************************************************************
        if consider_drafts:
            production_orders = self.env['mrp.production'].search([('state', 'not in', ['done', 'cancel'])])
        else:
            production_orders = self.env['mrp.production'].search([('state', 'not in', ['done', 'cancel', 'draft'])])
        for production in production_orders:
            move_components = self._get_flattened_totals(production.bom_id, production.product_qty)
            for prod in move_components:
                if move_components[prod]['level'] == 1:
                    open_moves.append([len(open_moves) + 1, 'In   ', 'MO      ',
                                       production.name,
                                       prod,
                                       move_components[prod]['total'], prod.uom_id.id,
                                       production.date_planned_start, move_components[prod]['level'], standard_lead_time+(move_components[prod]['level']*indirect_lead_time)])
                    continue
                if prod.type in ['service', 'consu']:
                    continue
                if move_components[prod]['total'] <= 0:
                    continue
                open_moves.append([len(open_moves) + 1, 'Out  ', 'MO      ',
                                   production.name,
                                   prod,
                                   move_components[prod]['total'], prod.uom_id.id,
                                   production.date_planned_start, move_components[prod]['level'], standard_lead_time+(indirect_lead_time*move_components[prod]['level'])])
        #print(open_moves)

        #for move in open_moves:
            #print(move[4].default_code+' - '+str(move[7])) ## Product + Date
            #print(move[4])  ## Product

        #open_moves.sort(key=lambda x: x[4].id) # Sort by product
        #open_moves.sort(key=lambda x: x[7])  # Sort by date
        open_moves.sort(key=lambda x: (x[4].id, x[7]))  # Sort by product and then date
        open_moves.append(False) ## append the last item to print when the for ends.
        consumption = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        #print('---> After sorting')
        #for move in open_moves:
            #print(move[4].default_code+' - '+str(move[7])) ## Product + Date
            #print(move[7]) ## Date
            #print(move[4])  ## Product

        # First Item
        for item in open_moves:
            if item:
                if route_buy not in item[4].route_ids.ids:
                    continue
            rationale = "<pre>--------------------------------------------------------------------------------------------"
            rationale += "<br/>                                        | Movement     "
            rationale += "<br/>DATE        | QTY         |Balance      |Type |Source  |BOM Level|Mfg Lead time| Doc"
            rationale += "<br/>------------|-------------|-------------|-----|--------|---------|-------------|-----------"
            product = open_moves[1][4]
            order_point = self.env['stock.warehouse.orderpoint'].search([('product_id', '=', product.id)], limit=1)
            if order_point:
                min_qty = order_point.product_min_qty
                max_qty = order_point.product_max_qty
                multiple = order_point.qty_multiple
            else:
                min_qty = 0.0
                max_qty = 0.0
                multiple = 1
            current_balance = product.qty_available
            pa_wip_qty = 0
            stock_quant = self.env['stock.quant'].search(
                ['&', ('location_id', 'in', pa_wip_locations), ('product_id', '=', product.id)])
            for stock_lin in stock_quant:
                pa_wip_qty += stock_lin.quantity

            if consider_wip:
                current_balance = product.qty_available
            else:
                current_balance = product.qty_available - pa_wip_qty
            rationale += '<br/>            |             | '+'{0: <12}|'.format(current_balance)+'     |        |         |             |Initial Balance'
            bom_level = item[8]
            required_by = False
            break

        for item in open_moves:
            new_prod = True
            if item:
                if route_buy not in item[4].route_ids.ids:
                    continue
                new_prod = (item[4] != product)
            if new_prod:
                rationale += "</pre>"
                purchase_line = self._include_prod(product, rationale, current_balance, required_by, consider_wip, consumption)
                purchase_line.level_bom = bom_level
                bom_level = 0
                consumption = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

                if not item:
                    break
                product = item[4]
                rationale = "<pre>--------------------------------------------------------------------------------------------"
                rationale += "<br/>                                        | Movement     "
                rationale += "<br/>DATE        | QTY         |Balance      |Type |Source  |BOM Level|Mfg Lead time| Doc"
                rationale += "<br/>------------|-------------|-------------|-----|--------|---------|-------------|-----------"
                required_by = False
                pa_wip_qty = 0
                stock_quant = self.env['stock.quant'].search(
                    ['&', ('location_id', 'in', pa_wip_locations), ('product_id', '=', product.id)])
                for stock_lin in stock_quant:
                    pa_wip_qty += stock_lin.quantity

                if consider_wip:
                    current_balance = product.qty_available
                else:
                    current_balance = product.qty_available - pa_wip_qty
                rationale += '<br/>            |             | ' + '{0: <12}|'.format(current_balance) + '     |        |         |             |Initial Balance'
            if item:
                if item[1] == 'Out  ':
                    current_balance -= item[5]
                    # Do not account the past
                    if current_date < item[7]:
                        consumption[item[7].month] += item[5]
                else:
                    current_balance += item[5]
                if not required_by:
                    if current_balance < 0:
                        required_by = item[7]
                rationale += '<br/>'+item[7].strftime("%Y-%m-%d")+'  | '+'{0: <12}|'.format(item[5])+' ' + '{0: <12}|'.format(current_balance) + item[1]+'|'+item[2]+'|'+'{0: <9}|'.format(item[8])+'{0: <13}|'.format(item[9])+item[3]
                product = item[4]
                if bom_level < item[8]:
                    bom_level = item[8]


        # ########################################
        # ### Other products without movements ###
        # ########################################
        products = self.env['product.product'].search(['&', ('type', '=', 'product'), ('route_ids', 'in', [route_buy])])
        required_by = current_date
        for product in products:
            purchase_planning = self.env['flsp.mrp.purchase.line'].search([('product_id', '=', product.id)])
            if not purchase_planning:
                current_balance = False
                rationale = 'No open movements - Product Selected based on Min qty.'
                purchase_line = self._include_prod(product, rationale, current_balance, required_by, consider_wip, consumption)

        # ########################################
        # ######## FORECAST   ####################
        # ########################################
        if consider_forecast:
            sales_forecast = self.env['flsp.sales.forecast'].search([])
            for forecast in sales_forecast:
                forecast_bom = self.env['mrp.bom'].search([('product_tmpl_id', '=', forecast.product_id.product_tmpl_id.id)], limit=1)
                if forecast_bom:
                    forecast_components = self._get_flattened_totals(forecast_bom, 1)
                    for component in forecast_components:
                        purchase_planning = self.env['flsp.mrp.purchase.line'].search([('product_id', '=', component.id)])
                        if not purchase_planning:
                            product = component
                            rationale = 'No open movements - Product Selected based on Forecast.'
                            purchase_line = self._include_prod(product, rationale, False, current_date, consider_wip, False, forecast)
                        else:
                            purchase_planning.qty_month1 += forecast.qty_month1
                            purchase_planning.qty_month2 += forecast.qty_month2
                            purchase_planning.qty_month3 += forecast.qty_month3
                            purchase_planning.qty_month4 += forecast.qty_month4
                            purchase_planning.qty_month5 += forecast.qty_month5
                            purchase_planning.qty_month6 += forecast.qty_month6
                            purchase_planning.qty_month7 += forecast.qty_month7
                            purchase_planning.qty_month8 += forecast.qty_month8
                            purchase_planning.qty_month9 += forecast.qty_month9
                            purchase_planning.qty_month10 += forecast.qty_month10
                            purchase_planning.qty_month11 += forecast.qty_month11
                            purchase_planning.qty_month12 += forecast.qty_month12
                else:
                    if forecast.product_id.type == 'product' and route_buy in forecast.product_id.route_ids.ids:
                        purchase_planning = self.env['flsp.mrp.purchase.line'].search([('product_id', '=', forecast.product_id.id)])
                        if not purchase_planning:
                            product = forecast.product_id
                            current_balance = False
                            rationale = 'No movement. Product Selected based on Forecast.'
                            purchase_line = self._include_prod(product, rationale, current_balance, current_date, consider_wip)
                        else:
                            purchase_planning.qty_month1 += forecast.qty_month1
                            purchase_planning.qty_month2 += forecast.qty_month2
                            purchase_planning.qty_month3 += forecast.qty_month3
                            purchase_planning.qty_month4 += forecast.qty_month4
                            purchase_planning.qty_month5 += forecast.qty_month5
                            purchase_planning.qty_month6 += forecast.qty_month6
                            purchase_planning.qty_month7 += forecast.qty_month7
                            purchase_planning.qty_month8 += forecast.qty_month8
                            purchase_planning.qty_month9 += forecast.qty_month9
                            purchase_planning.qty_month10 += forecast.qty_month10
                            purchase_planning.qty_month11 += forecast.qty_month11
                            purchase_planning.qty_month12 += forecast.qty_month12

            print('starting forecast')
            purchase_planning = self.env['flsp.mrp.purchase.line'].search([])
            months = ['', 'January  ', 'February ', 'March    ', 'April    ', 'May      ', 'June     ', 'July     ',
                      'August   ', 'October  ', 'September', 'November ', 'December ']
            next_6_months = []
            key = current_date.month
            count = 1
            for month in months:
                if count >= 7:
                    break
                if key > 12:
                    key = 1
                next_6_months.append(months[key])
                key += 1
                count += 1
            for planning in purchase_planning:
                print(planning)
                rationale = "<pre>----------------------------- Forecast ---------------------------------<br/>"
                rationale += '           |'
                for month in next_6_months:
                    rationale += month + "|"
                rationale += "<br/>"
                key = current_date.month
                rationale += 'Forecast   |'
                for month in next_6_months:
                    field_name = 'qty_month'+str(key)
                    rationale += '{0: <9}|'.format(getattr(planning, field_name))
                    key += 1
                    if key > 12:
                        key = 1
                rationale += '<br/>Actual     |'
                key = current_date.month
                for month in next_6_months:
                    field_name = 'consumption_month'+str(key)
                    rationale += '{0: <9}|'.format(getattr(planning, field_name))
                    key += 1
                    if key > 12:
                        key = 1
                rationale += '<br/>Diff       |'
                key = current_date.month
                for month in next_6_months:
                    field_name = 'qty_month'+str(key)
                    diff = getattr(planning, field_name)
                    field_name = 'consumption_month'+str(key)
                    diff -= getattr(planning, field_name)
                    rationale += '{0: <9}|'.format(diff)
                    key += 1
                    if key > 12:
                        key = 1
                rationale += "<br/>------------------------------------------------------------------------</pre>"
                planning.rationale += rationale
            # if not purchase_planning:
            #    print(forecast.product_id.name)
            # else:
            #    print('product already in there.......')

        return


        products_templates = self.env['product.template'].search(['&', ('type', '=', 'product'), ('route_ids', 'in', [route_buy, route_mfg])])
        for product_template in products_templates:
            lead_time = product_template.produce_delay
            product = self.env['product.product'].search([('product_tmpl_id', '=', product_template.id)])
            order_point = self.env['stock.warehouse.orderpoint'].search([('product_id', '=', product.id)], limit=1)
            if order_point:
                min_qty = order_point.product_min_qty
                max_qty = order_point.product_max_qty
                multiple = order_point.qty_multiple
            else:
                min_qty = 0.0
                max_qty = 0.0
                multiple = 1

            current_balance = product.qty_available
            pa_wip_qty = 0
            stock_quant = self.env['stock.quant'].search(
                ['&', ('location_id', 'in', pa_wip_locations), ('product_id', '=', product.id)])
            for stock_lin in stock_quant:
                pa_wip_qty += stock_lin.quantity

            if consider_wip:
                current_balance = product.qty_available
            else:
                current_balance = product.qty_available - pa_wip_qty

        return

        # calculating purchase
        products_templates = self.env['product.template'].search(['&', ('type', '=', 'product'), ('route_ids', 'in', [route_buy, route_mfg])])
        for product_template in products_templates:


            open_moves = []
            # index  type, source,    doc,          picking_id, production_id, qty, date
            #         IN   Purchase   WH/IN/P0001       32          0           5    2020-01-01 00:00:00
            #        OUT   Sales      WH/OUT/P0001      33          0           8    2020-01-01 00:00:00
            # ******************* quantity coming up***************************
            # Purchase Orders
            if route_buy in product_template.route_ids.ids:
                open_receipts = self.env['stock.picking'].search(['&', '&', ('product_id', '=', product.id), ('state', 'not in', ['done', 'cancel', 'draft']),('picking_type_id', 'in', receipt_stock_type)])
                for receipt in open_receipts:
                    stock_move_product = self.env['stock.move'].search(['&', ('picking_id', '=', receipt.id), ('product_id', '=', product.id)])
                    total_moved = 0
                    for move in stock_move_product:
                        total_moved += move.product_uom_qty
                    open_moves.append([len(open_moves)+1,'In ', 'Purchase  ', receipt.origin, receipt.id, 0, total_moved, receipt.scheduled_date])
            # Manufacturing Orders
            if route_mfg in product_template.route_ids.ids:
                if consider_drafts:
                    production_orders = self.env['mrp.production'].search(['&', ('state', 'not in', ['done', 'cancel']), ('product_id', '=', product.id)])
                else:
                    production_orders = self.env['mrp.production'].search(['&', ('state', 'not in', ['done', 'cancel', 'draft']), ('product_id', '=', product.id)])
                for production in production_orders:
                    open_moves.append([len(open_moves)+1, 'In ', 'Production', production.name, 0, production.id, production.product_qty, production.date_planned_finished])

            # ******************* quantity going out ***************************
            #Sales Orders
            open_deliveries = self.env['stock.picking'].search(['&', '&', ('product_id', '=', product.id), ('state', 'not in', ['done', 'cancel', 'draft']), ('picking_type_id', 'in', delivery_stock_type)])
            for delivery in open_deliveries:
                stock_move_product = self.env['stock.move'].search(['&', ('picking_id', '=', delivery.id), ('product_id', '=', product.id)])
                total_moved = 0
                for move in stock_move_product:
                    total_moved += move.product_uom_qty
                open_moves.append([len(open_moves)+1, 'Out', 'Sale      ', delivery.origin, delivery.id, 0, total_moved, delivery.scheduled_date])

            #Manufacturing Orders
            ## comment to consider only top level products
            if consider_drafts:
                production_orders = self.env['mrp.production'].search(['&', ('state', 'not in', ['done', 'cancel']), ('move_raw_ids.product_id', '=', product.id)])
            else:
                production_orders = self.env['mrp.production'].search(['&', ('state', 'not in', ['done', 'cancel', 'draft']), ('move_raw_ids.product_id', '=', product.id)])
            for production in production_orders:
                if production.origin:
                    open_moves.append([len(open_moves)+1, 'Out', 'Production', production.origin +"-"+ production.name, 0, production.id, production.product_qty, production.date_planned_finished])
                else:
                    open_moves.append([len(open_moves)+1, 'Out', 'Production', production.name, 0, production.id, production.product_qty, production.date_planned_finished])

            if len(open_moves) > 0:
                open_moves.sort(key=lambda l: l[7])
                open_moves_sorted = []
                for x in open_moves:
                    tmp = [len(open_moves_sorted)+1]
                    for y in x:
                        tmp.append(y)
                    open_moves_sorted.append(tmp)
                current_day = open_moves_sorted[0][8].date()
                last_day_moves = []
                suggested_qty = 0
                rationale = 'Initial Balance: ' + str(current_balance) + " on " + str(current_day)  + '<br/>'
                for x in open_moves_sorted:
                    rationale += "Movement: " + x[2] + " | Source: " + x[3] + " | Doc: " + x[4] + " | Qty: " + str(
                        x[7]) + " | Date: " + str(x[8].date()) + '<br/>'
                    if current_day != x[8].date():
                        #rationale = "Movement: " + x[1] + "source" + x[2] + str(x[8].date()) + "=" + str(x[7]) + '<br/>'
                        if current_balance-min_qty < 0.0:
                            suggested_qty = min_qty - current_balance
                            if (max_qty > 0.0) & ((suggested_qty+current_balance) < max_qty):
                                suggested_qty = max_qty
                            source = ''
                            desc_source = ''
                            picking_id = False
                            production_id = False
                            for y in last_day_moves:
                                if y[2] == 'Out':
                                    if source != '':
                                        source += ', '
                                    if desc_source != '':
                                        desc_source = 'Multiple orders'
                                    else:
                                        desc_source = y[3]
                                        picking_id = y[5]
                                        production_id = y[6]
                                    source += y[4]

                            #Checking multiple quantities
                            if multiple > 1:
                                if multiple > suggested_qty:
                                    suggested_qty += multiple-suggested_qty
                                else:
                                    if (suggested_qty % multiple) > 0:
                                        suggested_qty += multiple-(suggested_qty % multiple)

                            rationale += 'Balance on ' + str(current_day) + ' will be: ' + str(current_balance) + '<br/>'
                            rationale += 'Min qty =' + str(min_qty) + '<br/>'
                            rationale += 'Max qty =' + str(max_qty) + '<br/>'
                            rationale += 'Multiple qty =' + str(multiple) + '<br/>'
                            rationale += 'Lead time on product =' + str(lead_time) + ' days <br/>'
                            if lead_time == 0:
                                if not production_id:
                                    lead_time = standard_lead_time
                                    rationale += '-->Using direct demand lead time =' + str(lead_time) + ' days <br/>'
                                else:
                                    lead_time = indirect_lead_time
                                    rationale += '-->Using indirect demand lead time =' + str(lead_time) + ' days <br/>'

                            rationale += '* purchase for qty required =' + str(suggested_qty) + '<br/>'

                            self.create({'product_tmpl_id': product_template.id,
                                         'product_id': product.id,
                                         'description': product_template.name,
                                         'default_code': product_template.default_code,
                                         'suggested_qty': suggested_qty,
                                         'start_date': current_day + timedelta(days=-1 * lead_time),
                                         'deadline_date': current_day,
                                         'calculated': True,
                                         'stock_picking': picking_id,
                                         'production_id': production_id,
                                         'source_description': desc_source,
                                         'rationale': rationale,
                                         'source': source, })
                        current_balance += suggested_qty
                        current_day = x[8].date()
                        last_day_moves = []
                    if x[2] == 'Out':
                        current_balance -= x[7]
                        last_day_moves.append(x)
                    else:
                        current_balance += x[7]
                        last_day_moves.append(x)

                if len(last_day_moves) > 0:
                    current_day = x[8].date()
                    if current_balance - min_qty < 0:
                        suggested_qty = min_qty - current_balance
                        if (max_qty > 0.0) & ((suggested_qty+current_balance) < max_qty):
                            suggested_qty = max_qty
                        source = ''
                        desc_source = ''
                        picking_id = False
                        production_id = False
                        for y in last_day_moves:
                            if y[2] == 'Out':
                                if source != '':
                                    source += ', '
                                if desc_source != '':
                                    desc_source = 'Multiple orders'
                                else:
                                    desc_source = y[3]
                                    picking_id = y[5]
                                    production_id = y[6]
                                source += y[4]

                        #checking multiple quantities
                        if multiple > 1:
                            if multiple > suggested_qty:
                                suggested_qty += multiple - suggested_qty
                            else:
                                if (suggested_qty % multiple) > 0:
                                    suggested_qty += multiple - (suggested_qty % multiple)

                        rationale += 'Balance on ' + str(current_day) + ' will be: ' + str(current_balance) + '<br/>'
                        rationale += 'Min qty =' + str(min_qty) + '<br/>'
                        rationale += 'Max qty =' + str(max_qty) + '<br/>'
                        rationale += 'Multiple qty =' + str(multiple) + '<br/>'
                        rationale += 'Lead time on product =' + str(lead_time) + ' days <br/>'
                        if lead_time == 0:
                            if not production_id:
                                lead_time = standard_lead_time
                                rationale += '-->Using direct demand lead time =' + str(lead_time) + ' days <br/>'
                            else:
                                lead_time = indirect_lead_time
                                rationale += '-->Using indirect demand lead time =' + str(lead_time) + ' days <br/>'

                        rationale += '* purchase for Qty required =' + str(suggested_qty) + '<br/>'

                        self.create({'product_tmpl_id': product_template.id,
                                     'product_id': product.id,
                                     'description': product_template.name,
                                     'default_code': product_template.default_code,
                                     'suggested_qty': suggested_qty,
                                     'start_date': current_day + timedelta(days=-1 * lead_time),
                                     'deadline_date': current_day,
                                     'calculated': True,
                                     'stock_picking': picking_id,
                                     'production_id': production_id,
                                     'source_description': desc_source,
                                     'rationale' : rationale,
                                     'source': source, })

        return

    def execute_suggestion(self):
        return
        wip_location = self.env['stock.location'].search([('complete_name', '=', 'WH/PA')])
        stock_location = self.env['stock.location'].search([('complete_name', '=', 'WH/Stock')])
        if not wip_location:
            raise UserError('WIP Stock Location is missing')
        if not stock_location:
            raise UserError('Stock Location is missing')

        for item in self:
            bom_id = self.env['mrp.bom'].search([('product_tmpl_id', '=', item.product_tmpl_id.id)], limit=1)
            if not bom_id:
                item.rationale += "<br/> |"
                item.rationale += "<br/> |"
                item.rationale += "<br/>A T T E N T I O N: "
                item.rationale += "<br/> **** The attempt to create MO has failed *** "
                item.rationale += "<br/> Product has no Bill of Materials."
                item.rationale += "<br/> User: " + self.env['res.users'].search([('id', '=', self._uid)]).name
                continue

            mo = self.env['mrp.production'].create({
                'product_id': item.product_id.id,
                'bom_id': bom_id.id,
                'product_uom_id': item.product_id.uom_id.id,
                'product_qty': item.suggested_qty,
                'date_planned_start': datetime.combine(item.start_date, datetime.now().time()),
                'date_planned_finished': datetime.combine(item.deadline_date, datetime.now().time()),
                'date_deadline': datetime.combine(item.deadline_date, datetime.now().time()),
                'origin': item.source,
                'location_src_id': wip_location.id,
                'location_dest_id': stock_location.id,
            })


            list_move_raw = [(4, move.id) for move in mo.move_raw_ids.filtered(lambda m: not m.bom_line_id)]
            moves_raw_values = mo._get_moves_raw_values()
            move_raw_dict = {move.bom_line_id.id: move for move in mo.move_raw_ids.filtered(lambda m: m.bom_line_id)}
            for move_raw_values in moves_raw_values:
                if move_raw_values['bom_line_id'] in move_raw_dict:
                    # update existing entries
                    list_move_raw += [(1, move_raw_dict[move_raw_values['bom_line_id']].id, move_raw_values)]
                else:
                    # add new entries
                    list_move_raw += [(0, 0, move_raw_values)]
            mo.move_raw_ids = list_move_raw
            item.unlink()

        action = self.env.ref('mrp.mrp_production_action').read()[0]
        action.update({'target': 'main', 'ignore_session': 'read', 'clear_breadcrumb': True})
        return action

    def _get_flattened_totals(self, bom, factor=1, totals=None, level=None):
        """Calculate the **unitary** product requirements of flattened BOM.
        *Unit* means that the requirements are computed for one unit of the
        default UoM of the product.
        :returns: dict: keys are components and values are aggregated quantity
        in the product default UoM.
        """
        if level is None:
            level = 0
        if totals is None:
            totals = {}
        factor /= bom.product_uom_id._compute_quantity(
            bom.product_qty, bom.product_tmpl_id.uom_id, round=False
        )
        for line in bom.bom_line_ids:
            sub_bom = bom._bom_find(product=line.product_id)
            if sub_bom:
                if not line.product_id.product_tmpl_id.flsp_backflush:
                    if totals.get(line.product_id):
                        totals[line.product_id]['total'] += (
                            factor
                            * line.product_uom_id._compute_quantity(
                                line.product_qty, line.product_id.uom_id, round=False
                            )
                        )
                    else:
                        totals[line.product_id] = {'total':(
                            factor
                            * line.product_uom_id._compute_quantity(
                                line.product_qty, line.product_id.uom_id, round=False
                            )
                        ), 'level': level, 'bom': sub_bom.code}
                    continue
                else:
                    new_factor = factor * line.product_uom_id._compute_quantity(
                        line.product_qty, line.product_id.uom_id, round=False
                    )

                level += 1
                self._get_flattened_totals(sub_bom, new_factor, totals, level)
                level -= 1
            else:
                if totals.get(line.product_id):
                    totals[line.product_id]['total'] += (
                        factor
                        * line.product_uom_id._compute_quantity(
                            line.product_qty, line.product_id.uom_id, round=False
                        )
                    )
                else:
                    totals[line.product_id] = {'total':(
                        factor
                        * line.product_uom_id._compute_quantity(
                            line.product_qty, line.product_id.uom_id, round=False
                        )
                    ), 'level': level, 'bom': ''}
        return totals

    def _include_prod(self, product, rationale, balance, required_by, consider_wip, consumption=False, fc_obj=False):

        pa_location = self.env['stock.location'].search([('complete_name', '=', 'WH/PA')]).parent_path
        if not pa_location:
            raise UserError('WIP Stock Location is missing')
        pa_wip_locations = self.env['stock.location'].search([('parent_path', 'like', pa_location+'%')]).ids
        if not pa_wip_locations:
            raise UserError('WIP Stock Location is missing')

        pa_wip_qty = 0
        stock_quant = self.env['stock.quant'].search(
            ['&', ('location_id', 'in', pa_wip_locations), ('product_id', '=', product.id)])
        for stock_lin in stock_quant:
            pa_wip_qty += stock_lin.quantity

        if not balance:
            if consider_wip:
                current_balance = product.qty_available
            else:
                current_balance = product.qty_available - pa_wip_qty
        else:
            current_balance = balance

        prod_vendor = self.env['product.supplierinfo'].search([('product_tmpl_id', '=', product.product_tmpl_id.id)],limit=1)
        order_point = self.env['stock.warehouse.orderpoint'].search([('product_id', '=', product.id)], limit=1)
        if order_point:
            min_qty = order_point.product_min_qty
            max_qty = order_point.product_max_qty
            multiple = order_point.qty_multiple
        else:
            min_qty = 0.0
            max_qty = 0.0
            multiple = 1

        if current_balance < 0:
            suggested_qty = min_qty - current_balance
        else:
            if current_balance < min_qty:
                suggested_qty = min_qty - current_balance
            else:
                suggested_qty = 0
        # Checking supplier quantity:
        if prod_vendor:
            if suggested_qty > 0 and prod_vendor.min_qty > 0:
                if suggested_qty < prod_vendor.min_qty:
                    suggested_qty = prod_vendor.min_qty
        # checking multiple quantities
        if multiple > 1:
            if multiple > suggested_qty:
                suggested_qty += multiple - suggested_qty
            else:
                if (suggested_qty % multiple) > 0:
                    suggested_qty += multiple - (suggested_qty % multiple)
        # Checking Vendor lead time:
        if prod_vendor:
            if prod_vendor.delay and prod_vendor.delay > 0:
                if not required_by:
                    required_by = datetime.now()
                required_by = required_by - timedelta(days=prod_vendor.delay)
        if not consumption:
            consumption = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        forecast = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        if fc_obj:
            forecast[1] = fc_obj.qty_month1
            forecast[2] = fc_obj.qty_month2
            forecast[3] = fc_obj.qty_month3
            forecast[4] = fc_obj.qty_month4
            forecast[5] = fc_obj.qty_month5
            forecast[6] = fc_obj.qty_month6
            forecast[7] = fc_obj.qty_month7
            forecast[8] = fc_obj.qty_month8
            forecast[9] = fc_obj.qty_month9
            forecast[10] = fc_obj.qty_month10
            forecast[11] = fc_obj.qty_month11
            forecast[12] = fc_obj.qty_month12

        ret = self.create({'product_tmpl_id': product.product_tmpl_id.id,
                     'product_id': product.id,
                     'description': product.product_tmpl_id.name,
                     'default_code': product.product_tmpl_id.default_code,
                     'suggested_qty': suggested_qty,
                     'adjusted_qty': suggested_qty,
                     'calculated': True,
                     'product_qty': product.qty_available,
                     'product_min_qty': min_qty,
                     'product_max_qty': max_qty,
                     'qty_multiple': multiple,
                     'vendor_id': prod_vendor.name.id,
                     'vendor_qty': prod_vendor.min_qty,
                     'delay': prod_vendor.delay,
                     'stock_qty': product.qty_available - pa_wip_qty,
                     'wip_qty': pa_wip_qty,
                     'rationale': rationale,
                     'required_by': required_by,
                     'consumption_month1': consumption[1],
                     'consumption_month2': consumption[2],
                     'consumption_month3': consumption[3],
                     'consumption_month4': consumption[4],
                     'consumption_month5': consumption[5],
                     'consumption_month6': consumption[6],
                     'consumption_month7': consumption[7],
                     'consumption_month8': consumption[8],
                     'consumption_month9': consumption[9],
                     'consumption_month10': consumption[10],
                     'consumption_month11': consumption[11],
                     'consumption_month12': consumption[12],
                     'qty_month1': forecast[1],
                     'qty_month2': forecast[2],
                     'qty_month3': forecast[3],
                     'qty_month4': forecast[4],
                     'qty_month5': forecast[5],
                     'qty_month6': forecast[6],
                     'qty_month7': forecast[7],
                     'qty_month8': forecast[8],
                     'qty_month9': forecast[9],
                     'qty_month10': forecast[10],
                     'qty_month11': forecast[11],
                     'qty_month12': forecast[12],
                     'source': 'source', })
        return ret
