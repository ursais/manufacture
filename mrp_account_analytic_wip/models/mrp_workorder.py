# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo import api, fields, models


class MRPWorkOrder(models.Model):
    _inherit = "mrp.workorder"

    # TODO: probbaly not needed anymore...
    analytic_tracking_item_id = fields.Many2one(
        "account.analytic.tracking.item", string="Tracking Item", copy=False
    )
    # Make MO lock status available for views
    is_locked = fields.Boolean(related="production_id.is_locked")
    duration_planned = fields.Float(string="Planned Duration")

    @api.model_create_multi
    def create(self, vals_list):
        new_workorders = super().create(vals_list)
        new_workorders.production_id.populate_ref_bom_tracking_items()
        return new_workorders

    # FIXME: manual time entry on Wokr Order does not generate analytic items!


class MrpWorkcenterProductivity(models.Model):
    _inherit = "mrp.workcenter.productivity"

    def _prepare_mrp_workorder_analytic_item(self):
        values = super()._prepare_mrp_workorder_analytic_item()
        # Ensure the related Tracking Item is populated
        workorder = self.workorder_id
        if not workorder.analytic_tracking_item_id:
            item_vals = {
                "product_id": workorder.workcenter_id.analytic_product_id.id,
                "production_id": workorder.production_id.id,
                "workcenter_id": workorder.workcenter_id.id,
            }
            item = workorder.production_id._get_matching_tracking_item(item_vals)
            self.workorder_id.analytic_tracking_item_id = item
        values["analytic_tracking_item_id"] = workorder.analytic_tracking_item_id.id
        values["product_id"] = workorder.workcenter_id.analytic_product_id.id
        return values
