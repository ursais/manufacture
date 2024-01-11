# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo import api, fields, models


class MRPWorkOrder(models.Model):
    _inherit = "mrp.workorder"

    # TODO: probbaly not needed anymore...
    analytic_tracking_item_id = fields.Many2one(
        "account.analytic.tracking.item", string="Tracking Item", copy=False
    )
    # Operations added after MO confirmation have expected qty zero
    duration_expected = fields.Float(default=0.0)
    # Make MO lock status available for views
    is_locked = fields.Boolean(related="production_id.is_locked")
    duration_planned = fields.Float(string="Planned Duration")

    # From BOAK Code
    # @api.model_create_multi
    #def create(self, vals_list):
    #    new_workorders = super().create(vals_list)
    #    new_workorders.production_id.populate_ref_bom_tracking_items()
    #    return new_workorders

    # FIXME: manual time entry on Wokr Order does not generate analytic items!

    def _prepare_tracking_item_values(self):
        analytic = self.production_id.analytic_account_id
        planned_qty = self.duration_planned / 60
        return analytic and {
            "analytic_id": analytic.id,
            "product_id": self.workcenter_id.analytic_product_id.id,
            "workorder_id": self.id,
            "planned_qty": planned_qty,
            "production_id" : self.production_id.id
        }

    def populate_tracking_items(self, set_planned=False):
        """
        When creating a Work Order link it to a Tracking Item.
        It may be an existing Tracking Item,
        or a new one my be created if it doesn't exist yet.
        """
        TrackingItem = self.env["account.analytic.tracking.item"]
        to_populate = self.filtered(
            lambda x: x.production_id.analytic_account_id
            and x.production_id.state not in ("draft", "done", "cancel")
        )
        all_tracking = to_populate.production_id.analytic_tracking_item_ids
        for item in to_populate:
            tracking = all_tracking.filtered(lambda x: x.workorder_id == self)[:1]
            vals = item._prepare_tracking_item_values()
            not set_planned and vals.pop("planned_qty")
            if tracking:
                tracking.write(vals)
            else:
                tracking = TrackingItem.create(vals)
            item.analytic_tracking_item_id = tracking
            
    @api.model_create_multi
    def create(self, vals):
        new_workorder = super().create(vals)
        new_workorder.populate_tracking_items()
        return new_workorder
        

    # def write(self, vals):
    #     res = super().write(vals)
    #     for timelog in self.time_ids:
    #         timelog.generate_mrp_work_analytic_line()
    #     return res

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

    def generate_mrp_work_analytic_line(self):
        res = super().generate_mrp_work_analytic_line()
        # When recording actuals, consider posting WIp immedately
        mos_to_post = self.production_id.filtered("is_post_wip_automatic")
        mos_to_post.action_post_inventory_wip()
        return res
      
# class MrpWorkcenterProductivityLoss(models.Model):
#     _inherit = "mrp.workcenter.productivity.loss"
#
#     def _convert_to_duration(self, date_start, date_stop, workcenter=False):
#         """ Convert a date range into a duration in minutes.
#         If the productivity type is not from an employee (extra hours are allow)
#         and the workcenter has a calendar, convert the dates into a duration based on
#         working hours.
#         """
#         duration = super()._convert_to_duration(date_start, date_stop, workcenter)
#         for productivity_loss in self:
#             if workcenter and workcenter.resource_calendar_id:
#                 r = workcenter._get_work_days_data_batch(date_start, date_stop)[workcenter.id]['hours']
#                 duration = r * 60
#         return duration
