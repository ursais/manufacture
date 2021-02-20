# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo import models


class AnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    def _prepare_tracking_item_values(self):
        vals = super()._prepare_tracking_item_values()
        vals.update(
            {
                "stock_move_id": self.stock_move_id.id,
                "workorder_id": self.workorder_id.id,
            }
        )
        return vals

    def _get_tracking_item(self):
        tracking = super()._get_tracking_item()
        tracking = tracking.filtered(
            lambda x: (self.stock_move_id and self.stock_move_id == x.stock_move_id)
            or (self.workorder_id and self.workorder_id == x.workorder_id)
        )
        return tracking
