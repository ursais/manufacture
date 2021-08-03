# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo import models


class MRPWorkOrder(models.Model):
    _inherit = "mrp.workorder"

    def _prepare_mrp_workorder_analytic_item(self):
        values = super()._prepare_mrp_workorder_analytic_item()
        values["analytic_tracking_item_id"] = self.analytic_tracking_item_id.id
        return values

    def _prepare_tracking_item_values(self):
        vals = super()._prepare_tracking_item_values()
        analytic = self.production_id.analytic_account_id
        if analytic:
            vals = {
                "analytic_id": analytic.id,
                "product_id": self.workcenter_id.analytic_product_id.id,
                "workorder_id": self.id,
                "planned_qty": self.duration_expected / 60,
            }
        return vals

    def populate_tracking_items(self):
        TrackingItem = self.env["account.analytic.tracking.item"]
        for operation in self:
            vals = operation._prepare_tracking_item_values()
            vals and TrackingItem.create(vals)
