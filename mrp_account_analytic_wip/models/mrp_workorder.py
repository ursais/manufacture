# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo import api, fields, models


class MRPWorkOrder(models.Model):
    _inherit = "mrp.workorder"

    analytic_tracking_item_id = fields.Many2one(
        "account.analytic.tracking.item", string="Tracking Item", copy=False
    )

    def _prepare_tracking_item_values(self):
        analytic = self.production_id.analytic_account_id
        return analytic and {
            "analytic_id": analytic.id,
            "product_id": self.workcenter_id.analytic_product_id.id,
            "workorder_id": self.id,
            "planned_qty": self.duration_expected / 60,
        }

    def _get_tracking_item(self):
        self.ensure_one()
        all_tracking = self.production_id.analytic_tracking_item_ids
        tracking = all_tracking.filtered(lambda x: x.workorder_id == self)
        return tracking

    def _get_set_tracking_item(self):
        """
        Given an Analytic Item,
        locate the corresponding Tracking Item
        and set it on the record.
        If the (parent level) Tracking Item does not exist, it is created.
        """
        tracking = self._get_tracking_item()
        if tracking:
            self.analytic_tracking_item_id = tracking
        else:
            vals = self._prepare_tracking_item_values()
            if vals:
                tracking = self.env["account.analytic.tracking.item"].create(vals)
                self.analytic_tracking_item_id = tracking
        return tracking

    def populate_tracking_items(self):
        """
        When creating an Analytic Item,
        link it to a Tracking Item, the may have to be created if it doesn't exist.
        """
        to_populate = self.filtered(
            lambda x: not x.analytic_tracking_item_id
            and x.production_id.analytic_account_id
            and x.production_id.state not in ("draft", "done", "cancel")
        )
        for item in to_populate:
            item._get_set_tracking_item()

    @api.model
    def create(self, vals):
        new_workorders = super().create(vals)
        new_workorders.populate_tracking_items()
        return new_workorders


class MrpWorkcenterProductivity(models.Model):
    _inherit = "mrp.workcenter.productivity"

    def _prepare_mrp_workorder_analytic_item(self):
        values = super()._prepare_mrp_workorder_analytic_item()
        new_values = {
            "product_id": self.workcenter_id.analytic_product_id.id,
        }
        values.update(new_values)
        return values
