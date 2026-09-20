"""Server-side resolution of language-keyed term maps."""

DEFAULT_LANGUAGES = ("mul", "en")


def resolve_label(labels: dict[str, str], languages=DEFAULT_LANGUAGES) -> str | None:
    """First label found for the given languages in order, then any label; None if none."""
    for language in languages:
        if labels.get(language):
            return labels[language]
    for label in labels.values():
        if label:
            return label
    return None
