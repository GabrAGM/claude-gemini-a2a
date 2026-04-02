Disable the UserPromptSubmit hook so it no longer fires on every prompt.

Read `.claude/settings.local.json`, then remove or comment out the `hooks` section by setting it to an empty object, and write the file back.

Tell the user: "Hook disabled — restart Claude session for it to take effect."
