# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo import _, api, fields, models


class MRPProduction(models.Model):
    _inherit = "mrp.production"

    analytic_tracking_item_ids = fields.Many2many(
        "account.analytic.tracking.item",
        string="Tracking Items",
        compute="_compute_analytic_tracking_item",
    )
    analytic_tracking_item_count = fields.Integer(
        "WIP Item Count", compute="_compute_analytic_tracking_item"
    )
    analytic_tracking_item_amount = fields.Float(
        "WIP Actual Amount", compute="_compute_analytic_tracking_item"
    )
    currency_id = fields.Many2one("res.currency", related="company_id.currency_id")

    def _get_tracking_items(self):
        """
        Returns a recordset with the related Ttacking Items
        """
        return (
            self.mapped("move_raw_ids.analytic_tracking_item_id")
            | self.mapped("workorder_ids.analytic_tracking_item_id")
            | self.mapped("workorder_ids.analytic_tracking_item_id.child_ids")
        )

    @api.depends(
        "move_raw_ids.analytic_tracking_item_id",
        "workorder_ids.analytic_tracking_item_id",
    )
    def _compute_analytic_tracking_item(self):
        for mo in self:
            mo.analytic_tracking_item_ids = mo._get_tracking_items()
            mo.analytic_tracking_item_count = len(mo.analytic_tracking_item_ids)
            mo.analytic_tracking_item_amount = sum(
                mo.analytic_tracking_item_ids.mapped("actual_amount")
            )

    def _get_accounting_data_for_valuation(self):
        """
        Extension hook to set the accounts to use
        """
        # TODO: Deprecate property_wip_journal + wip_account + variance_account
        return self.product_id.product_tmpl_id.get_product_accounts()

    def _post_inventory(self, cancel_backorder=False):
        """
        Does MO closing.
        Ensure all done raw material moves are set
        on the consumed lines field, for correct traceability.
        """
        # _post_inventory will post missing raw material WIP and the final product
        super()._post_inventory(cancel_backorder=cancel_backorder)

        for order in self:
            # Correct consume_line_ids, that otherwise will miss
            # the early consumed raw materials
            moves_done = order.move_raw_ids.filtered(lambda x: x.state == "done")
            consume_move_lines = moves_done.mapped("move_line_ids")
            order.move_finished_ids.move_line_ids.consume_line_ids = [
                (6, 0, consume_move_lines.ids)
            ]
            # Clear the WIP Balance
            order.analytic_tracking_item_ids.clear_wip_journal_entries()

        return True

    def action_post_inventory_wip(self, cancel_backorder=False):
        """
        A variation of _post_inventory that allows consuming
        raw materials during MO execution, rather than only at
        MO completion.
        Triggered by button click, not automatic on raw material consumption.
        """
        for order in self:
            # Raw Material Consumption, closely following _post_inventory()
            moves_not_to_do = order.move_raw_ids.filtered(lambda x: x.state == "done")
            moves_to_do = order.move_raw_ids.filtered(
                lambda x: x.state not in ("done", "cancel")
            )
            for move in moves_to_do.filtered(
                lambda m: m.product_qty == 0.0 and m.quantity_done > 0
            ):
                move.product_uom_qty = move.quantity_done
            # MRP do not merge move, catch the result of _action_done in order
            # to get extra moves.
            moves_to_do = moves_to_do._action_done()
            moves_to_do = (
                order.move_raw_ids.filtered(lambda x: x.state == "done")
                - moves_not_to_do
            )
            order._cal_price(moves_to_do)
            order.action_assign()
            consume_move_lines = moves_to_do.mapped("move_line_ids")
            order.move_finished_ids.move_line_ids.consume_line_ids |= consume_move_lines

            # update posted and to post columns on Tracking Items!
            for tracking in moves_to_do.mapped("analytic_tracking_item_id"):
                tracking.accounted_amount = tracking.actual_amount

            # Post Work Order WIP
            workorders_tracking = order.workorder_ids.mapped(
                "analytic_tracking_item_id"
            )
            workorders_tracking |= workorders_tracking.child_ids
            tracking_todo = workorders_tracking.filtered("pending_amount")
            tracking_todo.process_wip_and_variance()

        return True

    def action_view_analytic_tracking_items(self):
        self.ensure_one()
        return {
            "res_model": "account.analytic.tracking.item",
            "type": "ir.actions.act_window",
            "name": _("%s Tracking Items") % self.name,
            "domain": [("id", "in", self._get_tracking_items().ids)],
            "view_mode": "tree,form",
        }

    def action_confirm(self):
        """
        On MO Confirm, save the planned amount on the tracking item.
        Note that in some cases, the Analytic Account might be set
        just after MO confirmation.
        """
        res = super().action_confirm()
        self.mapped("move_raw_ids").populate_tracking_items()
        self.mapped("workorder_ids").populate_tracking_items()
        return res

    def button_mark_done(self):
        res = super().button_mark_done()
        mfg_done = self.filtered(lambda x: x.state == "done")
        mfg_done._get_tracking_items().process_wip_and_variance(close=True)
        return res

    def action_cancel(self):
        res = super().action_cancel()
        self._get_tracking_items().action_cancel()
        return res

    @api.model
    def create(self, vals):
        new = super().create(vals)
        # Do not copy Tracking Items wjen duplicating an MO
        to_fix = new.move_raw_ids.filtered("analytic_tracking_item_id")
        to_fix.write({"analytic_tracking_item_id": None})
        return new

    def write(self, vals):
        """
        When setting the Analytic account,
        generate tracking items.

        On MTO, the Analytic Account might be set after the action_confirm(),
        so the planned amount needs to be set here.

        TODO: in what cases the planned amounts update should be prevented?
        """
        super().write(vals)
        if "analytic_account_id" in vals:
            confirmed_mos = self.filtered(lambda x: x.state == "confirmed")
            confirmed_mos.move_raw_ids.populate_tracking_items()
            confirmed_mos.workorder_ids.populate_tracking_items()
        return True
