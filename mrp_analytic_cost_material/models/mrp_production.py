# Copyright (C) 2020 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    def _prepare_material_analytic_line(self, move):
        self.ensure_one()
        return {
            "name": "{} / {}".format(self.name, move.product_id.display_name),
            "ref": self.name,
            "account_id": self.analytic_account_id.id or False,
            "manufacturing_order_id": self.id,
            "company_id": self.company_id.id,
            "stock_move_id": move.id,
            "product_id": move.product_id.id or False,
            "unit_amount": move.forecast_availability,
        }

    def generate_analytic_line(self):
        """Generate Analytic Lines Manually."""
        # FIXME: this is a placeholder for final logic
        # TODO: when should Analytic Items generation be triggered?
        AnalyticLine = self.env["account.analytic.line"].sudo()
        order_raw_moves = self.mapped("move_raw_ids")
        existing_items = AnalyticLine.search(
            [("stock_move_id", "in", order_raw_moves.ids)]
        )
        for order in self.filtered("analytic_account_id"):
            for move in order.move_raw_ids:
                line_vals = order._prepare_material_analytic_line(move)
                if move in existing_items.mapped("stock_move_id"):
                    analytic_line = existing_items.filtered(
                        lambda x: x.stock_move_id == move
                    )
                    analytic_line.write(line_vals)
                    analytic_line.on_change_unit_amount()
                elif move.forecast_availability:
                    analytic_line = AnalyticLine.create(line_vals)
                    analytic_line.on_change_unit_amount()
