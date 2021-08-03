# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _prepare_mrp_raw_material_analytic_line(self):
        values = super()._prepare_mrp_raw_material_analytic_line()
        values["analytic_tracking_item_id"] = self.analytic_tracking_item_id.id
        return values

    def _prepare_tracking_item_values(self):
        vals = {}
        analytic = self.raw_material_production_id.analytic_account_id
        if analytic:
            vals = {
                "analytic_id": analytic.id,
                "product_id": self.product_id.id,
                "stock_move_id": self.id,
                "planned_qty": self.product_uom_qty,
            }
        return vals

    def populate_tracking_items(self):
        TrackingItem = self.env["account.analytic.tracking.item"]
        for move in self:
            vals = move._prepare_tracking_item_values()
            vals and TrackingItem.create(vals)
