# Copyright (C) 2020 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class WorkCenterAnalyticStructure(models.Model):
    _name = "mrp.workcenter.analytic.structure"
    _description = "Work Center Analytic Structure"
    _rec_name = "product_id"

    # FIXME: cost_hour field automatically set onchange of work_center_id
    work_center_id = fields.Many2one(
        "mrp.workcenter",
        string="Work Center",
    )
    # TODO: limit product selection to Products with costing accounts configured
    product_id = fields.Many2one(
        "product.product",
        string="Product",
    )
    factor = fields.Float(
        string="Factor",
        default=1,
    )
