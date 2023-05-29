# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ProductProduct(models.Model):

    _inherit = 'product.product'

    cost_reference_bom_id = fields.Many2one("mrp.bom", "Cost Reference BoM", compute="_compute_cost_reference_bom")

    def _compute_cost_reference_bom(self):
        # bom calculation inspired on mrp_account\..\product.py _set_price_from_bom method
        self.ensure_one()
        BoM = self.env['mrp.bom']
        bom = (
            BoM.with_context(active_test=False).search([
                ("active_ref_bom", "=", True),
                "|",
                ("active","=",True),("active","=",False),
                "|",
                ("product_id", "=", self.id),
                ("product_tmpl_id", "=", self.product_tmpl_id.id)
               ],
                    order='sequence, product_id, id', limit=1)
            or BoM.search([
                "|",
                ("product_id", "=", self.id),
                ("product_tmpl_id", "=", self.product_tmpl_id.id)
               ],
                    order='sequence, product_id, id', limit=1)
            or BoM.search([
                    ('byproduct_ids.product_id', '=', self.id)],
                    order='sequence, product_id, id', limit=1)
        )
        self.cost_reference_bom_id = bom.id
