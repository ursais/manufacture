# Copyright (C) 2023 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo import models


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    def _prepare_raw_tracking_item_values(self):
        self.ensure_one()
        # Each distinct Product will be one Tracking Item
        # So multiple BOM lines for the same Product need to be aggregated
        lines = self.bom_line_ids
        return [
            {
                "product_id": product.id,
                "planned_qty": sum(
                    x.product_qty for x in lines if x.product_id == product
                ),
            }
            for product in lines.product_id
        ]

    def _prepare_ops_tracking_item_values(self):
        self.ensure_one()
        # Each distinct Work Center will be one Tracking Item
        # So multiple BOM lines for the same Work Center need to be aggregated
        lines = self.operation_ids
        return [
            {
                "product_id": workcenter.analytic_product_id.id,
                "workcenter_id": workcenter.id,
                "planned_qty": sum(
                    x.time_cycle for x in lines if x.workcenter_id == workcenter
                )
                / 60,
            }
            for workcenter in lines.workcenter_id
        ]
