# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    qty_planned = fields.Float()

    # Improve the unconsume descrition on SVL and JE
    # (originally "Correction of False (modification of past move)")
    # and add link to the MO Tracking Items
    def _create_in_svl(self, forced_quantity=None):
        res = self.env["stock.valuation.layer"]
        for move in self:
            svl = super(StockMove, move)._create_in_svl(forced_quantity=forced_quantity)
            if move.raw_material_production_id:
                svl.description = "%s - %s (modification of past move)" % (
                    move.raw_material_production_id.name,
                    move.product_id.name,
                )
                tracking_item = move.analytic_tracking_item_id
                svl.account_move_id.analytic_tracking_item_id = tracking_item

            res |= svl
        return res

    def _create_out_svl(self, forced_quantity=None):
        res = self.env["stock.valuation.layer"]
        for move in self:
            svl = super(StockMove, move)._create_out_svl(
                forced_quantity=forced_quantity
            )
            if move.raw_material_production_id:
                svl.description = "%s - %s (modification of past move)" % (
                    move.raw_material_production_id.name,
                    move.product_id.name,
                )
                tracking_item = move.analytic_tracking_item_id
                svl.account_move_id.analytic_tracking_item_id = tracking_item
            res |= svl
        return res

    # Copy Tracking item, so that when a move is split,
    # it still related to the same Tracking Item
    analytic_tracking_item_id = fields.Many2one(
        "account.analytic.tracking.item", string="Tracking Item", copy=True
    )

    def _prepare_mrp_raw_material_analytic_line(self):
        # When creating consumption Analytic Items,
        # set the linked Tracking Item, so that it can compute Actuals
        values = super()._prepare_mrp_raw_material_analytic_line()
        values["analytic_tracking_item_id"] = self.analytic_tracking_item_id.id
        return values

    def generate_mrp_raw_analytic_line(self):
        res = super().generate_mrp_raw_analytic_line()
        # When recording actuals, consider posting WIP immediately
        mos_to_post = self.raw_material_production_id.filtered("is_post_wip_automatic")
        mos_to_post.action_post_inventory_wip()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        new_moves = super().create(vals_list)
        new_moves.raw_material_production_id.populate_tracking_items()
        return new_moves
