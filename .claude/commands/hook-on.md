Enable the UserPromptSubmit hook so it fires on every prompt.

Read `.claude/settings.local.json` and ensure the `hooks` section contains:

```json
"hooks": {
  "UserPromptSubmit": [
    {
      "matcher": "",
      "hooks": [
        {
          "type": "command",
          "command": "python \".a2a/workflow-reminder.py\""
        }
      ]
    }
  ]
}
```

Write the file back with this hooks section present.

Tell the user: "Hook enabled — restart Claude session for it to take effect."
