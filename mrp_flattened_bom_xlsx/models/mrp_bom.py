# Copyright 2018 ForgeFlow S.L.
#   (http://www.forgeflow.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import models


class MrpBom(models.Model):
    """ Defines bills of material for a product or a product template """

    _inherit = "mrp.bom"

    def _get_flattened_totals(self, factor=1, totals=None, level=None):
        """Calculate the **unitary** product requirements of flattened BOM.
        *Unit* means that the requirements are computed for one unit of the
        default UoM of the product.
        :returns: dict: keys are components and values are aggregated quantity
        in the product default UoM.
        """
        self.ensure_one()
        if level is None:
            level = 1
        if totals is None:
            totals = {}
        factor /= self.product_uom_id._compute_quantity(
            self.product_qty, self.product_tmpl_id.uom_id, round=False
        )
        for line in self.bom_line_ids:
            sub_bom = self._bom_find(product=line.product_id)
            if sub_bom:
                new_factor = factor * line.product_uom_id._compute_quantity(
                    line.product_qty, line.product_id.uom_id, round=False
                )
                #if totals.get(line.product_id):
                #    totals[line.product_id]['total'] += (
                #        factor
                #        * line.product_uom_id._compute_quantity(
                #            line.product_qty, line.product_id.uom_id, round=False
                #        )
                #    )
                #else:
                totals[len(totals)+1] = {'total':(
                    factor
                    * line.product_uom_id._compute_quantity(
                        line.product_qty, line.product_id.uom_id, round=False
                    )
                ), 'level': level, 'bom': sub_bom.code, 'type': sub_bom.type, 'bom_plm': sub_bom.flsp_bom_plm_valid, 'track': line.product_id.tracking, 'prod': line.product_id}

                level += 1
                sub_bom._get_flattened_totals(new_factor, totals, level)
                level -= 1
            else:
                # if totals.get(line.product_id):
                #    totals[line.product_id]['total'] += (
                #        factor
                #        * line.product_uom_id._compute_quantity(
                #            line.product_qty, line.product_id.uom_id, round=False
                #        )
                #    )
                # else:
                totals[len(totals)+1] = {'total':(
                    factor
                    * line.product_uom_id._compute_quantity(
                        line.product_qty, line.product_id.uom_id, round=False
                    )
                ), 'level': level, 'bom': '', 'type': '', 'bom_plm': '', 'track': line.product_id.tracking, 'prod': line.product_id}
        return totals
