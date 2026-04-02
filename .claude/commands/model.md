Set the default executor model. The argument should be a Gemini model name.

Read `.a2a/status.json`, set the `defaultModel` field to the provided model name, and write the file back.

Common models:
- `gemini-2.5-flash` — fast, cheap, good for simple tasks
- `gemini-2.5-pro` — better reasoning for complex tasks
- `gemini-2.5-flash-preview-image` — image understanding for visual tasks

If no argument provided, show the current default model from status.json.

Example: `/model gemini-2.5-pro` sets the default to gemini-2.5-pro.
To clear: `/model none` sets defaultModel to null (uses Gemini CLI default).
