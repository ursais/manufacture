# Copyright (C) 2020 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class MRPWorkcenter(models.Model):
    _inherit = "mrp.workcenter"

    analytic_product_id = fields.Many2one(
        "product.product",
        string="Cost Type",
    )


class MRPWorkorder(models.Model):
    _inherit = "mrp.workorder"

    def write(self, vals):
        res = super().write(vals)
        if vals.get("duration"):
            AnalyticLine = self.env["account.analytic.line"].sudo()
            for rec in self.filtered("workcenter_id.analytic_product_id"):
                existing_lines = AnalyticLine.search([("workorder_id", "=", rec.id)])
                if existing_lines:
                    for line in existing_lines:  # TODO: use single write()
                        line.unit_amount = rec.duration
                        line.on_change_unit_amount()
                else:
                    line_vals = {
                        "name": "{} / {}".format(rec.production_id.name, rec.name),
                        "account_id": rec.production_id.analytic_account_id.id,
                        "date": rec.date_start,
                        "company_id": rec.company_id.id,
                        "manufacturing_order_id": rec.production_id.id,
                        "product_id": rec.workcenter_id.analytic_product_id.id,
                        "unit_amount": rec.duration,
                        "workorder_id": rec.id,
                    }
                    analytic_line = AnalyticLine.create(line_vals)
                    analytic_line.on_change_unit_amount()
        return res
