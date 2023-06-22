# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import _, api, fields, models
from odoo.tools import float_is_zero, float_round
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


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

    @api.depends(
        "move_raw_ids.state",
        "move_raw_ids.quantity_done",
        "move_finished_ids.state",
        "workorder_ids",
        "workorder_ids.state",
        "product_qty",
        "qty_producing",
    )
    def _compute_state(self):
        """
        Now aving all raw material moves done is not enough to set the MO as done.
        Should only set as done if the finished moves are all done.
        """
        res = super()._compute_state()
        for production in self:
            all_finished_moves_done = all(
                move.state == "done" for move in production.move_finished_ids
            )
            all_workorders_done = not production.workorder_ids or all(
                wo.state in ("done", "cancel") for wo in production.workorder_ids
            )
            if production.state == "done" and not all_finished_moves_done:
                if all_workorders_done:
                    production.state = "to_close"
                else:
                    production.state = "progress"
        return res

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

    # def _cal_price(self, consumed_moves):
    #     """Set a price unit on the finished move according to `consumed_moves`.
    #     """
    #     super(MRPProduction, self)._cal_price(consumed_moves)
    #     work_center_cost = 0
    #     finished_move = self.move_finished_ids.filtered(
    #         lambda x: x.product_id == self.product_id and x.state not in ('done', 'cancel') and x.quantity_done > 0)
    #     if finished_move and not consumed_moves:
    #         finished_move.ensure_one()
    #         for work_order in self.workorder_ids:
    #             time_lines = work_order.time_ids.filtered(lambda t: t.date_end and not t.cost_already_recorded)
    #             work_center_cost += work_order._cal_cost(times=time_lines)
    #             time_lines.write({'cost_already_recorded': True})
    #         qty_done = finished_move.product_uom._compute_quantity(
    #             finished_move.quantity_done, finished_move.product_id.uom_id)
    #         extra_cost = self.extra_cost * qty_done
    #         total_cost = - sum(consumed_moves.sudo().stock_valuation_layer_ids.mapped('value')) + work_center_cost + extra_cost
    #         byproduct_moves = self.move_byproduct_ids.filtered(lambda m: m.state not in ('done', 'cancel') and m.quantity_done > 0)
    #         byproduct_cost_share = 0
    #         for byproduct in byproduct_moves:
    #             if byproduct.cost_share == 0:
    #                 continue
    #             byproduct_cost_share += byproduct.cost_share
    #             if byproduct.product_id.cost_method in ('fifo', 'average'):
    #                 byproduct.price_unit = total_cost * byproduct.cost_share / 100 / byproduct.product_uom._compute_quantity(byproduct.quantity_done, byproduct.product_id.uom_id)
    #         if finished_move.product_id.cost_method in ('fifo', 'average'):
    #             finished_move.price_unit = total_cost * float_round(1 - byproduct_cost_share / 100, precision_rounding=0.0001) / qty_done
    #     return True

    def _post_inventory(self, cancel_backorder=False):
        """
        Does MO closing.
        Ensure all done raw material moves are set
        on the consumed lines field, for correct traceability (and proper unbuild).

        The Odoo code will post all material to the "Input" (WIP) account.
        So the clear WIP method may need to convert some of this WIP into Variances.
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
        return True

    def action_post_inventory_wip(self, cancel_backorder=False):
        """
        A variation of _post_inventory that allows consuming raw materials
        during MO execution, rather than only at MO completion.
        Triggered by button click, not automatic on raw material consumption.
        TODO: have an action available on MO list view
        """
        for order in self:
            moves_all = order.move_raw_ids
            for move in moves_all.filtered(lambda m: m.quantity_done):
                move.product_uom_qty = move.quantity_done
            # Raw Material Consumption, closely following _post_inventory()
            moves_not_to_do = order.move_raw_ids.filtered(lambda x: x.state == "done")
            moves_to_do = order.move_raw_ids.filtered(
                lambda x: x.state not in ("done", "cancel")
            )
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
            for tracking in moves_all.mapped("analytic_tracking_item_id"):
                tracking.accounted_amount = tracking.actual_amount

            # Post Work Order WIP
            workorders_tracking = order.workorder_ids.mapped(
                "analytic_tracking_item_id"
            )
            workorders_tracking |= workorders_tracking.child_ids
            tracking_todo = workorders_tracking.filtered("pending_amount")
            tracking_todo.process_wip_and_variance()

        return True

    def _prepare_clear_wip_account_line(self, account, amount):
        # Note: do not set analytic_account_id,
        # as that triggers a (repeated) Analytic Item
        return {
            "ref": _("%s - Clear WIP") % (self.display_name),
            "product_id": self.product_id.id,
            "product_uom_id": self.product_id.uom_id.id,
            "account_id": account.id,
            "debit": amount if amount > 0.0 else 0.0,
            "credit": -amount if amount < 0.0 else 0.0,
#            "analytic_account_id": self.analytic_account_id.id,
        }

    def clear_wip_final(self):
        """
        Add final Clear WIP JE journal entry.
        Looks up the WIP account balance and clears it using the Variance account.

        - WIP Account is the Production Location Input Account.
        - Variance Account is the Production Location Variance account.
        """
        for prod in self:
            # Find WIP and Variance Accounts
            prod_location = prod.production_location_id
            # acc_wip_prod = prod_location.valuation_in_account_id
            acc_var = prod_location.valuation_variance_account_id
            acc_clear = prod_location.valuation_clear_account_id

            if not (acc_clear and acc_var):
                _logger.debug(
                    "No Clear or Variance account found for MO %s", prod.display_name
                )
                continue

            # Find the balance of the WIP account...
            # Issue: Finished product has no related account moves!
            stock_moves = prod.move_raw_ids | prod.move_finished_ids
            stock_account_moves = (
                stock_moves.account_move_ids
                | prod.analytic_tracking_item_ids.account_move_ids
            )
            wip_items = stock_account_moves.line_ids.filtered("is_wip")

            # ... clear each of the WIP accounts
            move_lines = []
            accounts_wip = wip_items.mapped("account_id")
            for acc_wip in accounts_wip:
                wip_acc_items = wip_items.filtered(lambda x: x.account_id == acc_wip)
                wip_acc_bal = sum(wip_acc_items.mapped("balance"))
                # Should we do separate Journal Entry for each WIP account?
                if wip_acc_bal:
                    move_lines.extend(
                        [
                            prod._prepare_clear_wip_account_line(acc_wip, -wip_acc_bal),
                            prod._prepare_clear_wip_account_line(
                                acc_clear, +wip_acc_bal
                            ),
                        ]
                    )

            # The final product valuation move is used as a template for the header
            # Alternative solution would be to add a prepare header method
            final_prod_move = prod.move_finished_ids.filtered(
                lambda x: x.product_id == prod.product_id
            )
            final_acc_move = final_prod_move.account_move_ids[:1]
            if move_lines and final_acc_move:
                wip_move = final_acc_move.copy(
                    {
                        "ref": _("%s Clear WIP") % (prod.name),
                        "line_ids": [(0, 0, x) for x in move_lines or [] if x],
                    }
                )
                wip_move._post()

    def _cron_process_wip_and_variance(self):
        items = self.env["mrp.variance"].search(
            [("state", "in", ["progress", "to_close"])]
        )
        items.action_post_inventory_wip()
        return super()._cron_process_wip_and_variance()

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
        self.mapped("move_raw_ids").populate_tracking_items(set_planned=True)
        self.mapped("workorder_ids").populate_tracking_items(set_planned=True)
        return res

    def button_mark_done(self):
        # Post all pending WIP and then generate MO close JEs
        self.action_post_inventory_wip()
        # Run finished product valuation (no raw materials to valuate now)
        res = super().button_mark_done()
        mfg_done = self.filtered(lambda x: x.state == "done")
        if mfg_done:
            tracking = mfg_done._get_tracking_items()
            # Ensure all pending WIP is posted
            tracking.process_wip_and_variance(close=True)
            # Operations - clear WIP
            if mfg_done.product_id.cost_method !='fifo':
                tracking.clear_wip_journal_entries()
            # Raw Material - clear final WIP and post Variances
            mfg_done.clear_wip_final()

        # Below code will fix the FIFO SN costing for Raw material, FG and By product
        if self.product_id.cost_method =='fifo':
            # recalculate all JE for last MO
            finished_move = self.move_finished_ids.filtered(
                lambda x: x.product_id == self.product_id and x.state == 'done' and x.quantity_done > 0)
            consumed_moves = self.move_raw_ids
            if finished_move:
                work_center_cost = 0
                finished_move.ensure_one()
                fg_svl_ids = finished_move.sudo().stock_valuation_layer_ids
                for work_order in self.workorder_ids:
                    time_lines = work_order.time_ids.filtered(lambda t: t.date_end and not t.cost_already_recorded)
                    work_center_cost += work_order._cal_cost(times=time_lines)
                    time_lines.write({'cost_already_recorded': True})
                qty_done = finished_move.product_uom._compute_quantity(
                    finished_move.quantity_done, finished_move.product_id.uom_id)
                extra_cost = self.extra_cost * qty_done
                total_cost = - sum(consumed_moves.sudo().stock_valuation_layer_ids.mapped('value')) + work_center_cost + extra_cost
                byproduct_moves = self.move_byproduct_ids.filtered(lambda m: m.state == 'done' and m.quantity_done > 0)
                byproduct_cost_share = 0
                for byproduct in byproduct_moves:
                    if byproduct.cost_share == 0:
                        continue
                    byproduct_cost_share += byproduct.cost_share
                    if byproduct.product_id.cost_method in ('fifo', 'average'):
                        byproduct.price_unit = total_cost * byproduct.cost_share / 100 / byproduct.product_uom._compute_quantity(byproduct.quantity_done, byproduct.product_id.uom_id)
                        by_product_svl = byproduct.sudo().stock_valuation_layer_ids
                        self._correct_svl_je(by_product_svl, byproduct, byproduct.price_unit)
                if finished_move.product_id.cost_method in ('fifo', 'average'):
                    finished_move.price_unit = total_cost * float_round(1 - byproduct_cost_share / 100, precision_rounding=0.0001) / qty_done
                    total_cost = finished_move.price_unit
                    self.lot_producing_id.real_price = total_cost
                fg_svl = finished_move.stock_valuation_layer_ids and finished_move.stock_valuation_layer_ids[0] or []
                self._correct_svl_je(fg_svl, finished_move, total_cost)
        return res

    def _correct_svl_je(self, svl, stock_move, total_cost):
        account_move_id = svl.account_move_id
        svl.unit_cost = total_cost / (svl.quantity if svl.quantity>0 else 1)
        svl.value = svl.unit_cost * svl.quantity

        if not account_move_id:
            svl._validate_accounting_entries()
        else:
            # Change the SVl with correct cost
            account_move_id.button_draft()
            # The Valuation Layer has been changed,
            # now we have to edit the STJ Entry
            for ji_id in account_move_id.line_ids:
                if ji_id.credit != 0:
                    ji_id.with_context(check_move_validity=False).write(
                        {"credit": total_cost}
                    )
                else:
                    ji_id.with_context(check_move_validity=False).write(
                        {"debit": total_cost}
                    )
            account_move_id.action_post()

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

    def _get_move_raw_values(
        self,
        product_id,
        product_uom_qty,
        product_uom,
        operation_id=False,
        bom_line=False,
    ):
        vals = super()._get_move_raw_values(
            product_id, product_uom_qty, product_uom, operation_id, bom_line
        )
        vals.update({"qty_planned": vals.get("product_uom_qty")})
        return vals

    def _create_workorder(self):
        res = super()._create_workorder()
        for production in self:
            for workorder in production.workorder_ids:
                workorder.duration_planned = workorder.duration_expected
        return res

    def _check_sn_uniqueness(self):
        """ Alert the user if the serial number as already been consumed/produced 
            WIP Module is also creating other JE with Virtual / Production Location.
            We need to bypass the check for Current Production, there can be multiple moves with Virtual Production for same SN in WIP module.
        """
        if self.product_tracking == 'serial' and self.lot_producing_id:
            if self._is_finished_sn_already_produced(self.lot_producing_id):
                raise UserError(_('This serial number for product %s has already been produced', self.product_id.name))

        for move in self.move_finished_ids:
            if move.has_tracking != 'serial' or move.product_id == self.product_id:
                continue
            for move_line in move.move_line_ids:
                if self._is_finished_sn_already_produced(move_line.lot_id, excluded_sml=move_line):
                    raise UserError(_('The serial number %(number)s used for byproduct %(product_name)s has already been produced',
                                      number=move_line.lot_id.name, product_name=move_line.product_id.name))

        for move in self.move_raw_ids:
            if move.has_tracking != 'serial':
                continue
            for move_line in move.move_line_ids:
                if float_is_zero(move_line.qty_done, precision_rounding=move_line.product_uom_id.rounding):
                    continue
                message = _('The serial number %(number)s used for component %(component)s has already been consumed',
                    number=move_line.lot_id.name,
                    component=move_line.product_id.name)
                co_prod_move_lines = self.move_raw_ids.move_line_ids

                # Check presence of same sn in previous productions
                duplicates = self.env['stock.move.line'].search_count([
                    ('lot_id', '=', move_line.lot_id.id),
                    ('qty_done', '=', 1),
                    ('state', '=', 'done'),
                    ('location_dest_id.usage', '=', 'production'),
                    ('production_id', '!=', False),
                    ('production_id', '!=',self.id)  #In this core odoo method only this change has been added.
                ])
                if duplicates:
                    # Maybe some move lines have been compensated by unbuild
                    duplicates_returned = move.product_id._count_returned_sn_products(move_line.lot_id)
                    removed = self.env['stock.move.line'].search_count([
                        ('lot_id', '=', move_line.lot_id.id),
                        ('state', '=', 'done'),
                        ('location_dest_id.scrap_location', '=', True)
                    ])
                    unremoved = self.env['stock.move.line'].search_count([
                        ('lot_id', '=', move_line.lot_id.id),
                        ('state', '=', 'done'),
                        ('location_id.scrap_location', '=', True),
                        ('location_dest_id.scrap_location', '=', False),
                    ])
                    # Either removed or unbuild
                    if not ((duplicates_returned or removed) and duplicates - duplicates_returned - removed + unremoved == 0):
                        raise UserError(message)
                # Check presence of same sn in current production
                duplicates = co_prod_move_lines.filtered(lambda ml: ml.qty_done and ml.lot_id == move_line.lot_id) - move_line
                if duplicates:
                    raise UserError(message)
