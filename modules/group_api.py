import json

from fbchat_v2._core._utils import formAll, post_form_json_async
from fbchat_v2._features._thread import (
    _addAdmin,
    _all_thread_data,
    _changeNickname,
)


class GroupAPIError(Exception):
    pass


class GroupAPI:
    def __init__(self, session):
        self.session = session
        self.thread_data = None

    async def refresh(self):
        result = await _all_thread_data.func(self.session)

        if not isinstance(result, dict) or not result.get("dataGet"):
            raise GroupAPIError("Facebook group data could not be loaded.")

        self.thread_data = result["dataGet"]
        return result

    async def _features(self, thread_id, command):
        if self.thread_data is None:
            await self.refresh()

        result = await _all_thread_data.features(
            self.thread_data,
            str(thread_id),
            command,
        )

        if isinstance(result, str):
            raise GroupAPIError(result)

        if isinstance(result, dict) and result.get("error"):
            raise GroupAPIError(str(result["error"]))

        return result

    async def get_group_info(self, thread_id):
        return await self._features(thread_id, "threadInfomation")

    async def get_admin_ids(self, thread_id):
        result = await self._features(thread_id, "getAdmin")

        if not isinstance(result, dict):
            raise GroupAPIError("Invalid admin list returned by Facebook.")

        admins = result.get("adminThreadList", [])

        if not isinstance(admins, (list, tuple, set)):
            raise GroupAPIError("Facebook returned an invalid admin list.")

        return [str(user_id) for user_id in admins if user_id]

    async def get_members(self, thread_id):
        result = await self._features(
            thread_id,
            "exportMemberListToJson",
        )

        if not isinstance(result, list) or not result:
            raise GroupAPIError("Invalid or empty Facebook member list.")

        members = []
        seen_ids = set()

        for item in result:
            if not isinstance(item, str):
                raise GroupAPIError("Invalid member record type.")

            try:
                record = json.loads(item)
            except (TypeError, json.JSONDecodeError) as exc:
                raise GroupAPIError("Malformed member JSON; snapshot rejected.") from exc

            if not isinstance(record, dict) or len(record) != 1:
                raise GroupAPIError("Invalid member JSON structure.")

            user_id, details = next(iter(record.items()))
            user_id = str(user_id).strip()

            if not user_id or not isinstance(details, dict):
                raise GroupAPIError("Member record has no valid Facebook ID.")

            if user_id in seen_ids:
                raise GroupAPIError("Duplicate Facebook member ID in snapshot.")

            reported_id = details.get("idFacebook")
            if reported_id and str(reported_id) != user_id:
                raise GroupAPIError("Member ID mismatch; snapshot rejected.")

            seen_ids.add(user_id)

            members.append({
                "id": user_id,
                "name": str(details.get("nameFB") or "Unknown"),
                "profile_url": details.get("profileUrl"),
                "avatar_url": details.get("avatarUrl"),
            })

        return members

    async def sync_group_members(self, thread_id, store):
        """Persist only a complete and internally consistent snapshot."""
        await self.refresh()

        members = await self.get_members(thread_id)
        group_info = await self.get_group_info(thread_id)

        try:
            expected_count = int(group_info["memberCount"])
        except (KeyError, TypeError, ValueError) as exc:
            raise GroupAPIError(
                "Facebook member count unavailable; snapshot rejected."
            ) from exc

        if expected_count != len(members):
            raise GroupAPIError(
                f"Incomplete member snapshot: Facebook reports "
                f"{expected_count}, received {len(members)}. "
                "Database was not changed."
            )

        admin_ids = await self.get_admin_ids(thread_id)
        member_ids = {member["id"] for member in members}

        if not set(admin_ids).issubset(member_ids):
            raise GroupAPIError(
                "Admin list does not match member snapshot; "
                "database was not changed."
            )

        try:
            return store.sync_members(
                thread_id,
                members,
                admin_ids=admin_ids,
            )
        except (TypeError, ValueError) as exc:
            raise GroupAPIError(
                f"Could not save the group member snapshot: {exc}"
            ) from exc

    async def set_nickname(self, thread_id, user_id, nickname):
        result = await _changeNickname.func(
            self.session,
            str(thread_id),
            str(user_id),
            str(nickname),
        )

        if not isinstance(result, dict):
            raise GroupAPIError("Invalid Facebook nickname response.")

        if result.get("status") != "success":
            raise GroupAPIError(
                str(result.get("message", "Nickname update failed."))
            )

        return result

    async def remove_member(self, thread_id, user_id):
        """Request removal through Facebook's legacy group endpoint."""
        url = "https://www.facebook.com/chat/remove_participants/"
        data_form = formAll(self.session, requireGraphql=False)
        data_form.update({
            "uid": str(user_id),
            "tid": str(thread_id),
        })

        payload = await post_form_json_async(
            url,
            data_form,
            self.session["cookieFacebook"],
            strip_for_loop_prefix=True,
        )

        if not isinstance(payload, dict):
            raise GroupAPIError("Invalid Facebook member-removal response.")

        if payload.get("error"):
            raise GroupAPIError(
                f"Facebook rejected member removal: {payload['error']}"
            )

        return payload

    async def set_admin(self, thread_id, user_id, promote=True):
        result = await _addAdmin.func(
            self.session,
            str(thread_id),
            str(user_id),
            statusChoice=bool(promote),
        )

        if not isinstance(result, dict):
            raise GroupAPIError("Invalid Facebook admin response.")

        if result.get("status") != "success":
            raise GroupAPIError(
                str(result.get("message", "Admin update failed."))
            )

        return result
