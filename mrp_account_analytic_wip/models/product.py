# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ProductProduct(models.Model):
    _name = 'product.product'
    _inherit = 'product.product'

    cost_reference_bom_id = fields.Many2one("mrp.bom", "Cost Reference BoM", compute="_compute_cost_reference_bom")

    def _compute_cost_reference_bom(self):
        # bom calculation inspired on mrp_account\..\product.py _set_price_from_bom method
        self.ensure_one()
        bom = (self.env['mrp.bom']._bom_find(self)[self]
               or self.env['mrp.bom'].search([
                ('byproduct_ids.product_id', '=', self.id)],
                order='sequence, product_id, id', limit=1)
               )
        self.cost_reference_bom_id = bom.id
