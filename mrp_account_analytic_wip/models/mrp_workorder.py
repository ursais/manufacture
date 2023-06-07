# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo import api, fields, models


class MRPWorkOrder(models.Model):
    _inherit = "mrp.workorder"

    analytic_tracking_item_id = fields.Many2one(
        "account.analytic.tracking.item", string="Tracking Item", copy=False
    )
    # Operations added after MO confirmation have expected qty zero
    duration_expected = fields.Float(default=0.0)
    # Make MO lock status available for views
    is_locked = fields.Boolean(related="production_id.is_locked")

    @api.model_create_multi
    def create(self, vals_list):
        new_workorder = super().create(vals_list)
        new_workorder.production_id.populate_tracking_items()
        return new_workorder

    def write(self, vals):
        res = super().write(vals)
        # Changing the Work Center should update the Tracking Items
        if "workcenter_id" in vals:
            self.production_id.populate_tracking_items()
        return res


class MrpWorkcenterProductivity(models.Model):
    _inherit = "mrp.workcenter.productivity"

    def _prepare_mrp_workorder_analytic_item(self):
        values = super()._prepare_mrp_workorder_analytic_item()
        values["product_id"] = self.workcenter_id.analytic_product_id.id
        return values

    def generate_mrp_work_analytic_line(self):
        res = super().generate_mrp_work_analytic_line()
        # When recording actuals, consider posting WIp immedately
        mos_to_post = self.production_id.filtered("is_post_wip_automatic")
        mos_to_post.action_post_inventory_wip()
        return res
