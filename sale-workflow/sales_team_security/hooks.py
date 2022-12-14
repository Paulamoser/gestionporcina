# Copyright 2018-2016 Tecnativa - Pedro M. Baeza
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import SUPERUSER_ID, api


def post_init_hook(cr, registry):
    """At installation time, propagate the parent sales team to the children
    contacts that have this field empty, as it's supposed that the intention
    is to have the same.
    """
    cr.execute(
        """UPDATE res_partner
        SET team_id=parent.team_id
        FROM res_partner AS parent
        WHERE parent.team_id IS NOT NULL
        AND res_partner.parent_id = parent.id
        AND res_partner.team_id IS NULL"""
    )
    # At installation time, we need to sync followers
    with api.Environment.manage():
        env = api.Environment(cr, SUPERUSER_ID, {})
        partners = env["res.partner"].search(
            [
                ("parent_id", "=", False),
                ("is_company", "=", True),
                "|",
                ("user_id", "!=", False),
                ("child_ids.user_id", "!=", False),
            ]
        )
        partners._add_followers_from_salesmans()
