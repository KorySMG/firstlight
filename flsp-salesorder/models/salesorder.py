# -*- coding: utf-8 -*-

from odoo import fields, models, api


class flspsalesorder(models.Model):
    _inherit = 'sale.order'

    flsp_so_user_id = fields.Many2one('res.users', string="Salesperson 2")
    flsp_amount_deposit = fields.Monetary(string='Deposit Payment', store=True, copy=False, readonly=True)
    flsp_bpm_status = fields.Selection([
        ('quote', 'Quote'),
        ('wait', 'Waiting Approval'),
        ('approved', 'Disc.Approved'),
        ('sale', 'Sales Order'),
        ('confirmed', 'Delivery Confirmed'),
        ('packed', 'Packed'),
        ('shipped', 'Shipped'),
        ('partial', 'Partially Shipped'),
        ('tracking', 'Tracking Assigned'),
        ('delivered', 'Delivered'),
        ('cancel', 'Cancelled'),
        ('aa-quote', 'Quote'),
        ('bb-wait', 'Waiting Approval'),
        ('cc-approved', 'Disc.Approved'),
        ('dd-sale', 'Sales Order'),
        ('ee-confirmed', 'Shipping Confirmed'),
        ('ff-packed', 'Packed'),
        ('gg-partial', 'Partially Shipped'),
        ('hh-shipped', 'Shipped'),
        ('ii-tracking', 'Tracking Assigned'),
        ('jj-delivered', 'Delivered'),
        ('kk-cancel', 'Cancelled'),
        ], string='FL Status', copy=False, index=True, store=True, default='aa-quote')

    flsp_shipping_method = fields.Selection([
        ('1', 'FL account and Invoice the Customer'),
        ('2', 'FL account and do not Invoice Customer'),
        ('3', 'Customer carrier choice and account'),
        ], string='Shipping Method', copy=False, store=True)
    flsp_carrier_account = fields.Char(String="Carrier Account")

    @api.onchange('partner_id')
    def flsp_partner_onchange(self):
        self.flsp_so_user_id = self.partner_id.flsp_user_id.id
        return {
            'value': {
                'flsp_so_user_id': self.partner_id.flsp_user_id.id,
                'flsp_shipping_method': self.partner_id.flsp_shipping_method,
                'flsp_ship_via': self.partner_id.property_delivery_carrier_id.name,
                'flsp_carrier_account': self.partner_id.flsp_carrier_account
            },
        }

class flspsalesorderline(models.Model):
    _inherit = 'sale.order.line'

    @api.onchange('product_uom_qty')
    def flsp_product_uom_qty_onchange(self):
        ret_val = {}
        value_ret = self.product_uom_qty
        if self.product_uom_qty < self.product_template_id.flsp_min_qty:
            value_ret = self.product_template_id.flsp_min_qty
            self.product_uom_qty = value_ret
            ret_val = {'value': {'product_uom_qty': value_ret}}
        return ret_val

    @api.onchange('product_template_id')
    def flsp_product_template_id_onchange(self):
        ret_val = {}
        value_ret = self.product_uom_qty
        if self.product_uom_qty < self.product_template_id.flsp_min_qty:
            value_ret = self.product_template_id.flsp_min_qty
            self.product_uom_qty = value_ret
            ret_val = {'value': {'product_uom_qty': value_ret}}
        return ret_val
