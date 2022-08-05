# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    @api.depends(
        "raw_material_production_id.qty_producing", "product_uom_qty", "product_uom"
    )
    def _compute_should_consume_qty(self):
        super()._compute_should_consume_qty()
        # Components added after MO confirmation have expected qty zero
        for move in self:
            mo = move.raw_material_production_id
            if mo.state != "draft":
                move.should_consume_qty = 0

    # Copy Tracking item, so that when a move is split,
    # it still related to the same Tracking Item
    analytic_tracking_item_id = fields.Many2one(
        "account.analytic.tracking.item", string="Tracking Item", copy=True
    )

    def _prepare_mrp_raw_material_analytic_line(self):
        values = super()._prepare_mrp_raw_material_analytic_line()
        values["analytic_tracking_item_id"] = self.analytic_tracking_item_id.id
        return values

    def _prepare_tracking_item_values(self):
        analytic = self.raw_material_production_id.analytic_account_id
        planned_qty = self.product_uom_qty
        return {
            "analytic_id": analytic.id,
            "product_id": self.product_id.id,
            "stock_move_id": self.id,
            "planned_qty": planned_qty,
        }

    def populate_tracking_items(self, set_planned=False):
        """
        When creating an Analytic Item,
        link it to a Tracking Item, the may have to be created if it doesn't exist.
        """
        TrackingItem = self.env["account.analytic.tracking.item"]
        to_populate = self.filtered(
            lambda x: x.raw_material_production_id.analytic_account_id
            and x.raw_material_production_id.state not in ("draft", "done", "cancel")
        )
        all_tracking = to_populate.raw_material_production_id.analytic_tracking_item_ids
        for item in to_populate:
            tracking = all_tracking.filtered(
                lambda x: x.stock_move_id and x.product_id == item.product_id
            )
            vals = item._prepare_tracking_item_values()
            not set_planned and vals.pop("planned_qty")
            if tracking:
                tracking.write(vals)
            else:
                tracking = TrackingItem.create(vals)
            item.analytic_tracking_item_id = tracking

    @api.model
    def create(self, vals):
        new_moves = super().create(vals)
        new_moves.populate_tracking_items()
        return new_moves

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("flag_write_tracking"):
            moves = self.filtered(
                lambda x: x.raw_material_production_id.analytic_account_id
                and not x.analytic_tracking_item_id
            )
            moves and moves.with_context(
                flag_write_tracking=True
            ).populate_tracking_items()
        return res
