# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo import fields, models


class MRPWorkOrder(models.Model):
    _inherit = "mrp.workorder"

    analytic_tracking_item_id = fields.Many2one(
        "account.analytic.tracking.item", string="Tracking Item"
    )

    def _prepare_tracking_item_values(self):
        analytic = self.production_id.analytic_account_id
        return analytic and {
            "analytic_id": analytic.id,
            "product_id": self.workcenter_id.analytic_product_id.id,
            "workorder_id": self.id,
            "planned_qty": self.duration_expected / 60,
        }

    def populate_tracking_items(self):
        TrackingItem = self.env["account.analytic.tracking.item"]
        for operation in self:
            vals = operation._prepare_tracking_item_values()
            if vals:
                operation.analytic_tracking_item_id = TrackingItem.create(vals)


class MrpWorkcenterProductivity(models.Model):
    _inherit = "mrp.workcenter.productivity"

    def _prepare_mrp_workorder_analytic_item(self):
        values = super()._prepare_mrp_workorder_analytic_item()
        new_values = {
            "analytic_tracking_item_id": self.workorder_id.analytic_tracking_item_id.id,
            "product_id": self.workcenter_id.analytic_product_id.id,
        }
        values.update(new_values)
        return values
