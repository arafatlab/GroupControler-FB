import re
from datetime import datetime, timedelta, timezone

from fbchat_v2 import SendAPI

from modules.group_api import GroupAPI, GroupAPIError
from modules.group_store import GroupStore
from modules.members import format_member
from config import DRY_RUN


HELP_TEXT = """
╔══════════════════════════════╗
       🌸 HINATA — COMMAND GUIDE
╚══════════════════════════════╝

📌 GENERAL COMMANDS
/help                         — Show this command guide
/groupinfo                    — View group information
/admins                       — List group admins
/members                      — List group members
/info @name or ID             — View member information
/rules                        — Show group rules

⏰ REMINDER COMMANDS
/remind 10m message           — Set a reminder
/reminders                    — View pending reminders
/cancelremind ID              — Cancel your reminder

🛡️ ADMIN ONLY COMMANDS
/addrules text                — Set or update group rules
/removerules                  — Remove group rules
/up @name or ID               — Promote a member to admin
/down @name or ID             — Demote an admin
/warn @name or ID reason      — Warn a member
/warnings                     — View group warnings
/warns @name or ID            — View a member's warnings
/kick @name or ID             — Remove a member from the group

👥 MEMBER COMMANDS
/report @name or ID reason    — Report a member

🕒 TIME FORMATS
10m  = 10 minutes
2h   = 2 hours
1d   = 1 day

🔎 MEMBER IDENTIFICATION
• Use the member's exact displayed name or Facebook ID.
• Name matching must be unique.
• If multiple members have the same name, use their Facebook ID.

💡 QUICK TIPS
• Replace @name or ID with the actual member's name or Facebook ID.
• Replace reason with a brief explanation.
• Admin commands are available only to authorized group admins.

━━━━━━━━━━━━━━━━━━━━━━━━
       🌸 HINATA BOT
   Your Friendly Group Assistant
━━━━━━━━━━━━━━━━━━━━━━━━
"""


ADMIN_COMMANDS = {
    "/addrules", "/removerules", "/up", "/down",
    "/warn", "/warnings", "/warns", "/kick",
}


class GroupCommandHandler:
    def __init__(self, session):
        self.session = session
        self.bot_id = str(session.get("FacebookID") or "")
        self.api = SendAPI()
        self.groups = GroupAPI(session)
        self.store = GroupStore()
        self.dry_run = DRY_RUN

    async def send(self, thread_id, message, message_id=None):
        if self.dry_run:
            print(f"\n[DRY RUN] Group command reply:\n{message}")
            return False

        kwargs = {
            "dataFB": self.session,
            "contentSend": str(message),
            "threadID": str(thread_id),
            "typeChat": None,
        }
        if message_id:
            kwargs["replyMessage"] = True
            kwargs["messageID"] = str(message_id)

        result = await self.api.send(**kwargs)
        return isinstance(result, dict) and bool(result.get("success"))

    async def _admins(self, thread_id):
        return await self.groups.get_admin_ids(thread_id)

    async def _is_admin_command_allowed(self, thread_id, sender_id, message_id):
        try:
            admins = await self._admins(thread_id)
        except Exception as error:
            await self.send(
                thread_id,
                f"⚠️ Admin status যাচাই করা যায়নি: {type(error).__name__}",
                message_id,
            )
            return False

        if str(sender_id) not in admins:
            await self.send(thread_id, "⛔ এই command শুধু group admin ব্যবহার করতে পারবেন।", message_id)
            return False

        if not self.bot_id or self.bot_id not in admins:
            await self.send(
                thread_id,
                "⚠️ আগে group admins-কে আমাকে Admin করতে হবে। "
                "তারপর এই command ব্যবহার করা যাবে।",
                message_id,
            )
            return False

        return True

    async def _members(self, thread_id):
        return await self.groups.get_members(thread_id)

    async def _resolve_member(self, thread_id, query):
        value = str(query or "").strip()
        if value.startswith("@"):
            value = value[1:].strip()

        if not value:
            return None, "missing"

        # Refresh the database from a validated Facebook snapshot first.
        await self.groups.sync_group_members(thread_id, self.store)

        result = self.store.resolve_member(thread_id, value)
        status = result.get("status")

        if status != "ok":
            return None, status

        stored = result["member"]

        # Keep the existing command handlers' expected member format.
        member = {
            "id": str(stored["user_id"]),
            "name": stored.get("name") or "Unknown",
            "profile_url": stored.get("profile_url"),
            "avatar_url": stored.get("avatar_url"),
        }

        return member, None

    async def _reply_member_error(self, thread_id, message_id, error):
        messages = {
            "missing": "⚠️ Member name বা Facebook ID দাও।",
            "not_found": "⚠️ এই group-এ member পাওয়া যায়নি।",
            "ambiguous": "⚠️ একই নামে একাধিক member আছে। Facebook ID ব্যবহার করো।",
        }
        await self.send(thread_id, messages.get(error, "⚠️ Member খুঁজে পাওয়া যায়নি।"), message_id)

    @staticmethod
    def _parse_reminder(argument):
        match = re.match(r"^(\d+)(m|h|d)\s+(.+)$", argument.strip(), re.I)
        if not match:
            return None

        amount = int(match.group(1))
        unit = match.group(2).lower()
        message = match.group(3).strip()

        if amount < 1 or not message:
            return None

        delta = {
            "m": timedelta(minutes=amount),
            "h": timedelta(hours=amount),
            "d": timedelta(days=amount),
        }[unit]

        return datetime.now(timezone.utc) + delta, message

    async def handle(self, message):
        if not isinstance(message, dict) or message.get("type") != "thread":
            return False

        body = message.get("body")
        if not isinstance(body, str):
            return False

        body = body.strip()
        if not body.startswith("/"):
            return False

        parts = body.split(maxsplit=1)
        command = parts[0].casefold()
        argument = parts[1].strip() if len(parts) > 1 else ""

        # /hinata remains reserved for the existing AI handler.
        if command == "/hinata":
            return False

        thread_id = str(message.get("replyToID") or "")
        sender_id = str(message.get("userID") or "")
        message_id = message.get("messageID")

        if not thread_id or not sender_id:
            return True

        if command == "/help":
            await self.send(thread_id, HELP_TEXT, message_id)
            return True

        # Admin-only commands: verify requester first, then bot.
        if command in ADMIN_COMMANDS:
            if not await self._is_admin_command_allowed(thread_id, sender_id, message_id):
                return True

        try:
            if command == "/kick":
                if not argument:
                    await self.send(
                        thread_id,
                        "Usage: /kick @member full name or Facebook ID",
                        message_id,
                    )
                else:
                    member, error = await self._resolve_member(
                        thread_id, argument
                    )

                    if error:
                        await self._reply_member_error(
                            thread_id, message_id, error
                        )
                    elif member["id"] in {
                        str(self.bot_id), str(sender_id)
                    }:
                        await self.send(
                            thread_id,
                            "⚠️ নিজেকে বা bot account-কে kick করা যাবে না।",
                            message_id,
                        )
                    else:
                        admin_ids = await self.groups.get_admin_ids(thread_id)

                        if member["id"] in set(map(str, admin_ids)):
                            await self.send(
                                thread_id,
                                "⚠️ অন্য group admin-কে /kick দিয়ে সরানো যাবে না।",
                                message_id,
                            )
                        else:
                            await self.groups.remove_member(
                                thread_id, member["id"]
                            )

                            await self.groups.sync_group_members(
                                thread_id, self.store
                            )
                            remaining = await self._members(thread_id)

                            if any(
                                str(item.get("id")) == member["id"]
                                for item in remaining
                            ):
                                raise GroupAPIError(
                                    "Member is still present after the "
                                    "Facebook removal request."
                                )

                            await self.send(
                                thread_id,
                                f"✅ {member['name']} has been removed "
                                "from the group.",
                                message_id,
                            )

            elif command == "/groupinfo":
                info = await self.groups.get_group_info(thread_id)
                if not isinstance(info, dict):
                    info = {}

                members = await self._members(thread_id)
                admins = await self._admins(thread_id)

                name = (
                    info.get("threadName")
                    or info.get("name")
                    or info.get("title")
                    or "Unavailable"
                )
                description = (
                    info.get("description")
                    or info.get("threadDescription")
                    or "Unavailable"
                )

                await self.send(
                    thread_id,
                    f"👥 GROUP INFORMATION\n"
                    f"Name: {name}\n"
                    f"Description: {description}\n"
                    f"Members: {len(members)}\n"
                    f"Admins: {len(admins)}",
                    message_id,
                )

            elif command == "/admins":
                admins = await self._admins(thread_id)
                members = await self._members(thread_id)
                by_id = {str(m.get("id")): m for m in members}
                lines = [
                    f"• {by_id.get(uid, {}).get('name', 'Unknown')} — {uid}"
                    for uid in admins
                ]
                await self.send(
                    thread_id,
                    "👑 GROUP ADMINS\n" + ("\n".join(lines) if lines else "No admins found."),
                    message_id,
                )

            elif command == "/members":
                members = await self._members(thread_id)
                lines = [
                    f"• {m.get('name', 'Unknown')} — {m.get('id', '?')}"
                    for m in members[:60]
                ]
                extra = f"\n...and {len(members) - 60} more." if len(members) > 60 else ""
                await self.send(
                    thread_id,
                    f"👥 MEMBERS ({len(members)})\n"
                    + ("\n".join(lines) if lines else "No members found.")
                    + extra,
                    message_id,
                )

            elif command == "/info":
                member, error = await self._resolve_member(thread_id, argument)
                if error:
                    await self._reply_member_error(thread_id, message_id, error)
                else:
                    admins = await self._admins(thread_id)
                    role = "Admin" if member["id"] in admins else "Member"
                    await self.send(
                        thread_id,
                        f"👤 MEMBER INFO\n{format_member(member)}\nRole: {role}",
                        message_id,
                    )

            elif command == "/rules":
                rules = self.store.get_rules(thread_id)
                await self.send(
                    thread_id,
                    f"📜 GROUP RULES\n{rules}" if rules else "এই group-এর rules এখনো set করা হয়নি।",
                    message_id,
                )

            elif command == "/addrules":
                if not argument:
                    await self.send(thread_id, "Usage: /addrules <rules text>", message_id)
                else:
                    self.store.set_rules(thread_id, argument, sender_id)
                    await self.send(thread_id, "✅ Group rules updated.", message_id)

            elif command == "/removerules":
                removed = self.store.remove_rules(thread_id)
                await self.send(
                    thread_id,
                    "✅ Group rules removed." if removed else "এই group-এ কোনো rules set করা নেই।",
                    message_id,
                )

            elif command == "/remind":
                parsed = self._parse_reminder(argument)
                if not parsed:
                    await self.send(
                        thread_id,
                        "Usage: /remind 10m message\nTime units: m, h, d",
                        message_id,
                    )
                else:
                    remind_at, reminder_text = parsed
                    reminder_id = self.store.add_reminder(
                        thread_id, sender_id, reminder_text, remind_at.isoformat()
                    )
                    await self.send(
                        thread_id,
                        f"⏰ Reminder #{reminder_id} set for "
                        f"{remind_at.strftime('%Y-%m-%d %H:%M UTC')}.",
                        message_id,
                    )

            elif command == "/reminders":
                reminders = self.store.list_reminders(thread_id)
                lines = [
                    f"#{r['id']} — {r['message']} "
                    f"({r['remind_at']})"
                    for r in reminders[:30]
                ]
                await self.send(
                    thread_id,
                    "⏰ PENDING REMINDERS\n"
                    + ("\n".join(lines) if lines else "No pending reminders."),
                    message_id,
                )

            elif command == "/cancelremind":
                if not argument.isdigit():
                    await self.send(thread_id, "Usage: /cancelremind <ID>", message_id)
                else:
                    # Store permits the creator, or an admin, to cancel.
                    admins = await self._admins(thread_id)
                    cancelled = self.store.cancel_reminder(
                        int(argument), thread_id, sender_id,
                        is_admin=sender_id in admins,
                    )
                    await self.send(
                        thread_id,
                        "✅ Reminder cancelled." if cancelled
                        else "⚠️ Reminder not found or you cannot cancel it.",
                        message_id,
                    )

            elif command == "/report":
                bits = argument.split(maxsplit=1)
                if len(bits) != 2:
                    await self.send(thread_id, "Usage: /report @member reason", message_id)
                else:
                    member, error = await self._resolve_member(thread_id, bits[0])
                    if error:
                        await self._reply_member_error(thread_id, message_id, error)
                    else:
                        report_id = self.store.add_report(
                            thread_id, sender_id, member["id"], bits[1]
                        )
                        await self.send(
                            thread_id,
                            f"📩 Report #{report_id} saved for group admins.",
                            message_id,
                        )

            elif command in {"/up", "/down"}:
                member, error = await self._resolve_member(thread_id, argument)
                if error:
                    await self._reply_member_error(thread_id, message_id, error)
                elif member["id"] == self.bot_id:
                    await self.send(thread_id, "⚠️ Bot-এর নিজের role এভাবে পরিবর্তন করা যাবে না।", message_id)
                else:
                    await self.groups.set_admin(
                        thread_id,
                        member["id"],
                        promote=(command == "/up"),
                    )
                    action = "promoted to admin" if command == "/up" else "demoted from admin"
                    await self.send(
                        thread_id,
                        f"✅ {member['name']} {action}.",
                        message_id,
                    )

            elif command == "/warn":
                if "|" not in argument:
                    await self.send(
                        thread_id,
                        "Usage: /warn @member full name | reason\\n"
                        "Example: /warn @Kiyotaka Ayanokoji | spam",
                        message_id,
                    )
                else:
                    target_query, reason = argument.split("|", 1)
                    target_query = target_query.strip()
                    reason = reason.strip()

                    if not target_query or not reason:
                        await self.send(
                            thread_id,
                            "Usage: /warn @member full name | reason",
                            message_id,
                        )
                    else:
                        member, error = await self._resolve_member(
                            thread_id, target_query
                        )
                        if error:
                            await self._reply_member_error(
                                thread_id, message_id, error
                            )
                        else:
                            warning_id = self.store.add_warning(
                                thread_id, member["id"], sender_id, reason
                            )
                            await self.send(
                                thread_id,
                                f"⚠️ Warning #{warning_id} issued to {member['name']}.\\n"
                                f"Reason: {reason}",
                                message_id,
                            )

            elif command in {"/warnings", "/warns"}:
                target_id = None
                if command == "/warns":
                    member, error = await self._resolve_member(thread_id, argument)
                    if error:
                        await self._reply_member_error(thread_id, message_id, error)
                        return True
                    target_id = member["id"]

                warnings = self.store.get_warnings(thread_id, target_id)
                lines = [
                    f"#{w['id']} | User: {w['user_id']} | "
                    f"Reason: {w['reason']} | By: {w['admin_id']}"
                    for w in warnings[:30]
                ]
                await self.send(
                    thread_id,
                    "⚠️ WARNINGS\n" + ("\n".join(lines) if lines else "No warnings found."),
                    message_id,
                )

            else:
                # Unknown group slash commands are not sent to the AI.
                await self.send(
                    thread_id,
                    "Unknown group command. Use /help to see available commands.",
                    message_id,
                )

        except (GroupAPIError, Exception) as error:
            print(
                "[GROUP COMMAND ERROR]",
                command,
                type(error).__name__,
                str(error),
            )
            await self.send(
                thread_id,
                f"⚠️ Command failed: {type(error).__name__}. "
                "Facebook API response check করো।",
                message_id,
            )

        return True
