# plasma-claude-usage

A small KDE Plasma 5 panel widget that shows how much of your Claude subscription limit is left: the Claude logo and a percentage. Companion of [plasma-codex-usage](https://github.com/aadegtyarev/plasma-codex-usage).

- The panel shows the window closer to running out (5-hour or weekly).
- The tooltip lists both windows with their reset times and says how old the numbers are.
- The percentage turns orange at 20% and red at 10%.
- A click opens a menu: **Refresh** and **Open usage page** (claude.ai/settings/usage). The same items are in the right-click menu.

The UI is in English with a Russian translation.

## Where the numbers come from

Claude Code has no command that prints subscription limits, but after each API response it passes them to its [status line](https://code.claude.com/docs/en/statusline) command as `rate_limits` (`five_hour`, `seven_day`). `claude-usage record` is meant to be that command: it saves the latest readings to `~/.local/state/plasma-claude-usage/rate-limits.json` and prints nothing, so the status line stays empty. The widget reads that file once a minute; no network, no credentials.

Limitations that follow from it:

- The numbers are as fresh as the last Claude Code answer in a terminal on this computer. Usage on claude.ai, in the apps, on other machines or in `claude -p` shows up only after the next interactive answer. The tooltip says when the data is from.
- Once a window's reset time passes, the widget shows it as full (100%) until Claude Code reports the new window.
- Claude Code sends `rate_limits` only for claude.ai subscriptions (documented for Pro, Max and Ultra; it also works on Team), and only after the first answer of a session.

## Install

1. Download the `.deb` from [Releases](https://github.com/aadegtyarev/plasma-claude-usage/releases) and install it:

   ```sh
   sudo apt install ./plasma-claude-usage_*_all.deb
   ```

2. Set the Claude Code status line in `~/.claude/settings.json`:

   ```json
   "statusLine": {
     "type": "command",
     "command": "claude-usage record"
   }
   ```

   If you already have a status line script, call `claude-usage record` from it with the same JSON on stdin, for example `echo "$input" | claude-usage record`.

3. Add **Claude Usage** to a panel (right-click the panel → Add Widgets). If Plasma does not list it yet, restart Plasma or log out and back in.

## Command line

```sh
$ claude-usage
{"remainingPercent": 64, "windows": {"five_hour": {"remainingPercent": 64, "resetsAt": 1795613400}, "seven_day": {"remainingPercent": 95, "resetsAt": 1796198400}}, "recordedAt": 1795612830}
```

On failure it prints `{"error": "not_set_up"}` (the status line has never run `claude-usage record`) or `{"error": "no_limits"}` (Claude Code has not sent limits yet) and exits with 1.

Several Claude Code sessions may write the same file. An idle session re-renders its status line with the numbers of its last answer, so a reading is kept only if it is not older than the stored one: usage only grows within a window, and a later reset time means a new window.

## Development

```sh
python3 -m unittest discover -s tests -v
```

The tests also check that `po/*.po` match the strings in the QML. To add a language, copy `po/ru.po` to `po/<language>.po` and translate the `msgstr` lines.

GitHub Actions builds the `.deb` on every push and attaches it to a release for `v*` tags.

## Disclaimer

Anthropic, Claude and Claude Code are trademarks of Anthropic. This is an independent, unofficial project; it is not affiliated with, endorsed by or supported by Anthropic. The Claude logo is used only to identify the service the widget reports on.

## License

MIT, see [LICENSE](LICENSE). The Claude logo is not covered by it.
