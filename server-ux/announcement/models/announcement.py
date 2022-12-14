# Copyright 2022 Tecnativa - David Vidal
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import api, fields, models


class AnnouncementLog(models.Model):
    _name = "announcement.log"
    _description = "Log user reads"
    _order = "create_date desc"

    announcement_id = fields.Many2one(comodel_name="announcement")


class Announcement(models.Model):
    _name = "announcement"
    _description = "User announcements"
    _order = "notification_date, sequence asc, id"

    active = fields.Boolean(copy=False)
    sequence = fields.Integer()
    name = fields.Char(string="Title", required=True)
    content = fields.Html()
    announcement_type = fields.Selection(
        selection=[
            ("specific_users", "Specific users"),
            ("user_group", "User groups"),
        ],
        default="specific_users",
        required=True,
    )
    specific_user_ids = fields.Many2many(
        comodel_name="res.users",
        domain=[("share", "=", False)],
        inverse="_inverse_specific_user_ids",
    )
    user_group_ids = fields.Many2many(comodel_name="res.groups")
    allowed_user_ids = fields.Many2many(
        comodel_name="res.users",
        relation="announcement_res_users_allowed_rel",
        compute="_compute_allowed_user_ids",
        compute_sudo=True,
        store=True,
    )
    allowed_users_count = fields.Integer(
        compute="_compute_allowed_user_ids", compute_sudo=True, store=True,
    )
    read_announcement_count = fields.Integer(
        compute="_compute_read_announcement_count", store=True,
    )
    notification_date = fields.Datetime()
    notification_expiry_date = fields.Datetime()

    def _inverse_specific_user_ids(self):
        """Used to set users pendant announcements when they're set in the announcement
        itself"""
        for announcement in self:
            for user in announcement.specific_user_ids.filtered(
                lambda x: announcement
                not in (x.read_announcement_ids + x.pendant_announcement_ids)
            ):
                user.pendant_announcement_ids |= announcement

    @api.depends("specific_user_ids", "user_group_ids")
    def _compute_allowed_user_ids(self):
        self.allowed_user_ids = False
        self.allowed_users_count = False
        for announcement in self.filtered(
            lambda x: x.announcement_type == "specific_users"
        ):
            announcement.allowed_user_ids = announcement.specific_user_ids
            announcement.allowed_users_count = len(announcement.specific_user_ids)
        for announcement in self.filtered(
            lambda x: x.announcement_type == "user_group"
        ):
            announcement.allowed_user_ids = announcement.user_group_ids.users
            announcement.allowed_users_count = len(announcement.user_group_ids.users)

    def _compute_read_announcement_count(self):
        logs = self.env["announcement.log"].read_group(
            [("announcement_id", "in", self.ids)],
            ["announcement_id"],
            ["announcement_id"],
        )
        result = {
            data["announcement_id"][0]: (data["announcement_id_count"]) for data in logs
        }
        for announcement in self:
            announcement.read_announcement_count = result.get(announcement.id, 0)

    @api.onchange("announcement_type")
    def _onchange_announcement_type(self):
        if self.announcement_type == "specific_users":
            self.user_group_ids = False
        elif self.announcement_type == "user_group":
            self.specific_user_ids = False

    def action_announcement_log(self):
        """Return a set of fungible transient records to see altogether read logs
        and pendant users"""
        self.ensure_one()
        read_logs = self.env["announcement.log"].search(
            [("announcement_id", "in", self.ids)]
        )
        pendant_users = self.allowed_user_ids.filtered(
            lambda x: x not in read_logs.create_uid
        )
        read_pendant_log = self.env["read.announcement.wizard"].create(
            [
                {
                    "user_id": log.create_uid.id,
                    "date": log.create_date,
                    "announcement_id": self.id,
                    "read_state": "read",
                }
                for log in read_logs
            ]
        )
        read_pendant_log += self.env["read.announcement.wizard"].create(
            [{"user_id": user.id, "read_state": "pendant"} for user in pendant_users]
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "read.announcement.wizard",
            "views": [[False, "tree"]],
            "domain": [("id", "in", read_pendant_log.ids)],
            "context": dict(self._context, create=False, group_by=["read_state"]),
            "name": "Read Logs",
        }
