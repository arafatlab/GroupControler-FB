def find_member(members, query):
    """Resolve a member by exact numeric ID or unique case-insensitive name."""
    query = str(query or "").strip()
    if query.startswith("@"):
        query = query[1:].strip()

    if not query:
        return None, "missing"

    if query.isdigit():
        for member in members:
            if str(member.get("id")) == query:
                return member, None
        return None, "not_found"

    matches = [
        member for member in members
        if str(member.get("name", "")).casefold() == query.casefold()
    ]

    if len(matches) == 1:
        return matches[0], None
    if len(matches) > 1:
        return None, "ambiguous"
    return None, "not_found"


def format_member(member):
    return (
        f"{member.get('name', 'Unknown')}\n"
        f"Facebook ID: {member.get('id', 'Unknown')}"
    )
