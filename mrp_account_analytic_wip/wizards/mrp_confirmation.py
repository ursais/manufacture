from odoo import models

class MrpConfirmation(models.TransientModel):
    _inherit = "mrp.confirmation"

    def do_confirm(self):
        for record in self:
            if record.working_duration == 0.0:
                record.date_end = record.date_start
            super().do_confirm()
