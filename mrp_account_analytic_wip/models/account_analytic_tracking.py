# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class AnalyticTrackingItem(models.Model):
    _inherit = "account.analytic.tracking.item"

    stock_move_id = fields.Many2one(
        "stock.move", string="Stock Move", ondelete="cascade"
    )
    workorder_id = fields.Many2one(
        "mrp.workorder", string="Work Order", ondelete="cascade"
    )

    @api.depends("stock_move_id.product_id", "workorder_id.display_name")
    def _compute_name(self):
        super()._compute_name()
        for tracking in self.filtered("stock_move_id"):
            move = tracking.stock_move_id
            tracking.name = "{}{} / {}".format(
                "-> " if tracking.parent_id else "",
                move.raw_material_production_id.name,
                move.product_id.display_name,
            )
        for tracking in self.filtered("workorder_id"):
            workorder = tracking.workorder_id
            tracking.name = "{}{} / {} ({})".format(
                "-> " if tracking.parent_id else "",
                workorder.production_id.name,
                workorder.name,
                tracking.product_id.display_name or "",
            )

    def _get_accounting_data_for_valuation(self):
        """
        For raw material stock moves, consider the destination location (Production)
        input and output accounts.
        - "stock_input": is the WIP account where consumption is expected to have been
          posted
        - "stock_variance": is the Variance account
        """
        accounts = super()._get_accounting_data_for_valuation()
        dest_location = self.stock_move_id.location_dest_id
        # Only set for raw materials
        if dest_location.valuation_in_account_id:
            accounts["stock_input"] = dest_location.valuation_in_account_id
        if dest_location.valuation_out_account_id:
            accounts["stock_output"] = dest_location.valuation_out_account_id
        return accounts

    def _get_unit_cost(self):
        """
        If no cost Product is assigned to a work order,
        use the Work Center's Cost Hour.
        """
        unit_cost = super()._get_unit_cost()
        if not unit_cost and self.workorder_id:
            unit_cost = self.workorder_id.workcenter_id.costs_hour
        return unit_cost

    def _get_tracking_item(self):
        """
        Locate existing Tracking Item.
        - For Stock Moves, locate by Product, and multtiple lines
          can match the same Tracking Item.
        - For Work Order, locate by Work Order
        """
        tracking = super()._get_tracking_item()
        if self.stock_move_id:
            tracking = tracking.filtered(
                lambda x: x.stock_move_id == self.stock_move_id
            )
        if self.workorder_id:
            tracking = tracking.filtered(lambda x: x.workorder_id == self.workorder_id)
        return tracking
