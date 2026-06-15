from typing import Optional

# Predefined productivity list for apps and domains
PRODUCTIVE_APPS = {
    "code.exe",
    "idea64.exe",
    "visualstudio.exe",
    "devenv.exe",
    "msvsmon.exe",
    "powershell.exe",
    "cmd.exe",
    "bash.exe",
    "git.exe",
    "slack.exe",
    "discord.exe",
    "teams.exe",
    "zoom.exe",
    "terminal.exe",
    "cursor.exe",
    "sublime_text.exe",
    "notepad++.exe",
    "pycharm.exe",
    "clion.exe",
}

BROWSER_APPS = {
    "chrome.exe",
    "firefox.exe",
    "msedge.exe",
    "iexplore.exe",
    "safari.exe",
    "brave.exe",
    "opera.exe"
}

PRODUCTIVE_DOMAINS = {
    "github.com",
    "stackoverflow.com",
    "google.com",
    "gitlab.com",
    "docs.microsoft.com",
    "aws.amazon.com",
    "localhost",
    "atlassian.net",
    "jira.com",
    "python.org",
    "npmjs.com",
    "mdn.mozilla.org",
    "wikipedia.org",
    "fastapi.tiangolo.com",
    "sqlalchemy.org"
}

UNPRODUCTIVE_DOMAINS = {
    "youtube.com",
    "facebook.com",
    "twitter.com",
    "reddit.com",
    "instagram.com",
    "netflix.com",
    "tiktok.com",
    "pinterest.com",
    "twitch.tv"
}


def classify_activity(app_name: Optional[str], domain: Optional[str]) -> str:
    """Classifies an activity as productive, unproductive, or neutral."""
    app_lower = (app_name or "").lower()
    domain_lower = (domain or "").lower()

    if app_lower in BROWSER_APPS or (not app_lower and domain_lower):
        # Check domain classification
        for prod in PRODUCTIVE_DOMAINS:
            if prod in domain_lower:
                return "productive"
        for unprod in UNPRODUCTIVE_DOMAINS:
            if unprod in domain_lower:
                return "unproductive"
        return "neutral"

    # Check app classification
    for prod in PRODUCTIVE_APPS:
        if prod in app_lower:
            return "productive"

    return "neutral"
