# Observed pyylmao Behavior

Source logs are in the Incus VM `diverse-deer`, mostly under
`/root/.local/share/weechat/logs/`.

## Implemented Surface

- URL previews: user posts a URL, bot replies with a single `━━☛` title line.
  Evidence: `irc.notgay.#not-gay.weechatlog` around lines 55-65.
- YouTube previews: user posts a YouTube URL and the bot replies with
  `▶ <title> | <channel>  [<duration|LIVE|UPCOMING>]  <views> views   <likes> likes   <date>`.
  The visible text is IRC-formatted: the `▶` logo is white-on-red
  `\x030,4 ▶ \x03`, while duration/status, views, likes, and date are separate
  black-on-light-grey islands with one colored padding space on each side,
  e.g. `\x031,15 \x02[01:00:41]\x02 \x03`,
  `\x031,15 \x0259K views\x02 \x03`, and
  `\x031,15 Apr 03, 2026 \x03`.
  The final date island was added in the logs after a command-debug session;
  the accepted shape appears around
  `irc.notgay.#not-gay.weechatlog` lines 75352-75355. The reconstruction uses
  `yt-dlp` for duration/views/likes/date when available, supports
  `PYYLMAO_YOUTUBE_COOKIES` for a cookies file, and falls back through
  YouTube's player metadata endpoint plus oEmbed title/channel metadata if
  YouTube blocks anonymous full extraction. Return YouTube Dislike supplies
  public view/like counts in fallback mode.
  Evidence: `irc.notgay.#not-gay.weechatlog` around lines 396-397, 1645-1646,
  6293-6302, 7338-7339, and 75352-75355.
- `ping`: bot replies `p0ng!`.
  Evidence: `irc.notgay.#tcl.weechatlog` around lines 4824, 5674, and 6635,
  plus `irc.notgay.#not-gay.weechatlog` around line 109471.
- `?<domain>`: emits a single Domainr-style status line, such as
  `<domain>: active`, `<domain>: undelegated inactive`, `<domain>: undelegated
  active`, `<domain>: marketed priced active`, or `api error`. Inputs without a
  dot are ignored by the trigger.
  Evidence: `irc.notgay.#not-gay.weechatlog` around lines 73616-73623,
  112952-112972, 117277-117293, and 119324-119337, plus
  `irc.supernets.#superbowl.weechatlog` around lines 821040-821054.
- OpenRouter chat triggers:
  - `grok, ...`
  - `grok ...`
  - `gpt, ...`
  - `gpt ...`
  - `@grok ...`
  - `@@grok ...`
  Leading prompt options are parsed when they appear before the prompt body:
  `maxh=N` overrides recent context length for one request, `temperature=N`
  sets OpenRouter request temperature, and quoted `system="..."` appends a
  user-supplied system note. Bot replies in wrapped lines and appends a
  timing/token/model stats line.
  Evidence: `irc.notgay.#not-gay.weechatlog` around lines 66-108, 809-816,
  873-876, 1029-1061, 37155-37165, and 99585-99589; `irc.gangnet.#tclmafia.weechatlog`
  around lines 43051-43055 and 49189-49190; `irc.supernets.#superbowl.weechatlog`
  around lines 1873314-1873324 and 2037025-2037029.
- `!alias list|get|set|delete|set-default|get-default`: manages model aliases
  used by the chat trigger parser. Logged forms include `!alias set glm
  openrouter/z-ai/glm-4.7`, `!alias get grok`, `!alias delete sonoma`, and
  slash-containing aliases such as `moonshotai/kimi-k2.5`. Alias names can be
  called with `@alias ...`, `@@alias ...`, or `alias, ...`.
  Evidence: `irc.notgay.#not-gay.weechatlog` around lines 10263-10275 and
  109481-109482, `irc.notgay.#tcl.weechatlog` around lines 27921-28144,
  `irc.gangnet.#tclmafia.weechatlog` around lines 13891-13892 and
  57443-57444, plus `irc.supernets.#superbowl.weechatlog` around lines
  1920098-1920117.
- `!models`: listed by the historical command inventory as `^!models$`. The
  reconstruction fetches OpenRouter model metadata and prints a compact model,
  context, input price, and output price table.
  Evidence: `irc.notgay.#tcl.weechatlog` around lines 2096, 6607, 15279,
  18369, 39705, 39939, and 44393, plus
  `irc.notgay.#bluesky.weechatlog` around line 2307.
- `$llm <model>`: prints `𝒍𝒍𝒎-𝒑𝒓𝒊𝒄𝒆𝒔 𝒇𝒐𝒓 '<model>'` followed by provider rows with
  input/output dollars per million tokens and cache pricing columns when
  present. Unknown exact model names return `no matches for model '<model>'`;
  commands with spaces use the final token as the lookup key.
  Evidence: `irc.notgay.#not-gay.weechatlog` around lines 2716-2772,
  15615-15622, 21498-21507, 21548-21552, and 54803-54809.
- `!kill <id>` / `!kill all`: cancels running bot commands and reports the
  selected run IDs. The empty `!kill all` case keeps the logged rough edge
  `Killed all running commands: ` with nothing after the colon.
  Evidence: `irc.notgay.#not-gay.weechatlog` around lines 1027, 108510-108511,
  and `irc.notgay.#bluesky.weechatlog` around line 2215.
- `!cancel`: toggles the LLM tool-cancellation flag and replies
  `Tool cancellation flag is ON` / `Tool cancellation flag is OFF`. When the
  flag is ON, OpenRouter tool calls are not executed; the visible trace
  `Tool calls cancelled: user intervention` is returned to the model so it can
  finish without tool output. Evidence: `irc.notgay.#not-gay.weechatlog`
  around lines 66440-66499, 68151-68153, and 100958-100974.
- OpenRouter tool loops also keep the logged automatic guardrails: after about
  600 seconds, pending tool calls are replaced with the visible pair
  `max_time reached: <now> <started> 600` and
  `Tool calls cancelled: max_time 600s reached`; if the model keeps requesting
  tools past the 32-call chain limit, the final reply is
  `Chain limit of 32 exceeded.`. Evidence:
  `irc.gangnet.#tclmafia.weechatlog` around lines 14827-14855 and
  `irc.notgay.#tcl.weechatlog` around lines 23745-23751.
- `!reload [module]`: emits the logged maintenance reload response and refreshes
  generated command artifacts when the requested module is a generated command.
  Known logged forms include
  `!reload md2irc`, `!reload gpt.common`, `!reload helpers.img2irc`,
  `!reload handlers.kvstore`, `!reload handlers.reload`,
  `!reload handlers.toggle`, `!reload anagram_rs`, `!reload kvstore`,
  `!reload llm`, `!reload backends.sqlite`, `!reload mdbuffer`,
  no-match cases such as `!reload helpres.img2irc`, bare `!reload`, and the
  `handlers.help` error case.
  Evidence: `irc.notgay.#not-gay.weechatlog` around lines 37619-37621,
  38457-38462, 51868-51870, 70386-70414, 70632-70636, 80353-80355,
  and 116539-116541, plus `irc.notgay.#tcl.weechatlog` around lines
  20631-20639, 34046-34052, 34523-34525, and 46672-46673.
- `!rehash`: replies `Configuration reloaded successfully`.
  Evidence: `irc.notgay.#not-gay.weechatlog` around line 100683 and
  `irc.notgay.#tcl.weechatlog` around lines 21072, 44709, 44753, and 47459.
- `!test <args>`: echoes parsed whitespace-separated arguments as
  `<index> - <value>` lines and appends
  `relay this code in your response: <4-digit-code>`.
  Evidence: `irc.notgay.#tcl.weechatlog` around lines 46677-46680.
- `!enable <trigger>` / `!disable <trigger>`: persists command trigger state for
  known reconstructed and generated commands and replies `Trigger <name> is now
  enabled` or `Trigger <name> is now disabled`. Missing names reply
  `Trigger <name> does not exist`; explicitly re-enabling an already-enabled
  command replies `Error: Command '<name>' is already enabled.`
  Evidence: `irc.notgay.#tcl.weechatlog` around lines 16418-16424,
  `irc.notgay.#not-gay.weechatlog` around lines 15492-15495, and
  `irc.gangnet.#tclmafia.weechatlog` around lines 50324-50329 and 53486-53488.
- `!kv get|set|query|append|del|info|modes`: reads and writes a persistent
  nested key/value store using dot paths such as
  `md2irc.options.use_figlet`, `.commands.gpt._default.system.10`, quoted keys
  like `.pyylmao.irc.channels."#not-gay"`, and bracket indexes like
  `.pyylmao._history[7638]`. `get` returns scalars directly, missing paths as
  `<path> is not set`, and lists/dicts as a `root` tree with the newer logged
  container formatting (`└── options`, not `└── options:`). `set` stores
  JSON values such as `{}`, `{"enabled": false}`, arrays, and numbers. Scalar
  `True`/`False`/`null` spellings are accepted for compatibility, but Python
  booleans inside objects such as `{"enabled": False}` remain strings, matching
  logged failed JSON edits. It returns `Set <path> to:` with the new value tree;
  `+stats` is accepted as a compatibility no-op for `set`.
  `append` creates or extends lists and returns `None`, or
  `Appended to <path>. New value:` with `+stats`; `del` deletes stored paths.
  The longer word `delete` is not an alias in the logs, and unsupported actions
  keep the historical rough error shape such as
  `unknown error, op=update args=['update', 'man', 'my']`.
	  `query <path>|length` returns a `root` tree with the length value, and
	  `query <path>|keys` renders dict keys or list indexes; missing/null paths
	  preserve the logged jq error `null (null) has no keys`. Bracket slices such
	  as `.commands.gpt._default.system[-2:]` return the sliced list as a `root`
	  tree, while the invalid dotted form `.commands.gpt._default.system.[-2:]`
	  preserves the logged jq-style syntax error. Query keys that jq requires to be
	  quoted with double quotes preserve the logged compile errors for forms such
	  as `._not-gay`, `.#superbowl`, `.'#superbowl'`, and `['#superbowl']`.
	  Literal jq-style values such as `!kv query "ok"` and `!kv query "im gay"`
	  render as a `root` tree containing `value`. The logged jq debugging probe
	  `query to_entries[] | ...` renders top-level `{"key": ..., "value": ...}`
	  entries; the trailing pipe expression is ignored, matching the observed
	  split-argument behavior rather than full jq.
  `+raw` / `raw` and `+json` expose machine-readable inspection forms; bare
  `json` remains the logged unknown operation rough edge;
  `info` reports the backing state file. This reconstructs the storage surface;
  it does not yet make arbitrary `commands.*` edits hot-reload runtime handlers.
  Evidence: `irc.notgay.#not-gay.weechatlog` around lines 26805-26821,
  30876-30918, 38441-38463, 40637-40640, 79444-79526, 103060-103204, and
  116539-116590.
- `!history [n]`: reports or sets `max_history`, which controls how much recent
  channel context is included with LLM prompts unless a one-shot `maxh=N` prompt
  option is present. Non-command IRC messages are also mirrored into the
  persistent state under
  `.pyylmao.irc.channels."<channel>".history`, and LLM replies are stored there
  as assistant records with the resolved model. The global
  `.pyylmao._history` list keeps the same bounded event stream for KV
  inspection. The `get_chat_history` LLM tool reads the persisted channel
  history, honors the logged `include_bot` argument, and emits the newer visible
  tool trace shape `read N lines from chat history` for persisted reads.
  Evidence: `irc.notgay.#not-gay.weechatlog` around lines 312-314, 20838-20852,
  and 33941-33942.
- `!echo <markdown>`: echoes simple markdown/HTML-ish input back to IRC. Literal
  `\n` sequences become separate messages, and markdown block quotes render with
  the `┃` prefix.
  Evidence: `irc.notgay.#not-gay.weechatlog` around lines 259-271 and
  `irc.notgay.#tcl.weechatlog` around lines 15941-15949, 21060-21074, and
  38905-39025.
- `!todo <task>`: appends a task to the sender's todo list, then prints
  `<nick>'s Todos` followed by numbered `●` entries. `!todo` without a task
  lists the sender's stored items.
  Evidence: `irc.notgay.#not-gay.weechatlog` around lines 54671-54772,
  76507-76515, and 80254-80257.
- `!palette99`: prints nine fixed rows of zero-padded IRC color indexes from
  `00` through `98`, with blank lines between rows.
  Evidence: `irc.notgay.#tcl.weechatlog` around lines 18062-18080.
- `!list` / `!listen`: reports active async command IDs; when no commands are
  running, replies `No commands running.`
  Evidence: `irc.notgay.#bluesky.weechatlog` around lines 2210-2215,
  `irc.notgay.#tcl.weechatlog` around lines 14067-14075 and 46674-46677,
  plus `irc.notgay.#not-gay.weechatlog` around lines 64201-64202.
- `!cmds`: emits the command inventory table with command name, enabled state,
  and trigger pattern. Generated commands written through `write_command` are
  included with their persisted regex pattern and normal trigger state.
  Evidence: `irc.notgay.#bluesky.weechatlog` around lines 2261-2333 and
  generated command creation/revision traces in `irc.notgay.#not-gay.weechatlog`
  around lines 4396, 10187-10193, 75234, 92509-92512, and 96811-96814.
- `!chess [gid] <command>`: no arguments prints
  `Usage: [gid] <command> [options]` and the command list. `new` creates a
  `default` game unless a game id is supplied, then prints the logged Unicode
  board with ranks/files. Moves are validated with python-chess; `draw` and
  `resign` are restricted to players.
  Evidence: `irc.notgay.#tcl.weechatlog` around lines 28307-28322 and
  `irc.supernets.#superbowl.weechatlog` around lines 1654936-1654968.
- `!cowsay <text>`: emits a standard cowsay-style speech bubble. The historical
  body art varied by available render assets, but the observed bubble starts
  with ` ____`, `< hi >`, and ` ----` for `!cowsay hi`.
  Evidence: `irc.notgay.#tcl.weechatlog` around lines 5677-5696 and
  39735-39748.
- `!hf`: emits recently trending Hugging Face models with creation date,
  repo id, and `https://huggingface.co/...` URL.
  Evidence: `irc.notgay.#not-gay.weechatlog` around lines 15045-15054,
  25185-25190, and 84222-84234.
- `!host <hostname-or-ip>`: performs forward and reverse DNS lookups. Forward
  hits render a header such as `<host> has address:` followed by one address per
  line; lookup failures render `host: <socket error>`.
  Evidence: command creation and stabilized output in
  `irc.notgay.#not-gay.weechatlog` around lines 72880-72914.
- `!crt <hostname>` / `?crt <hostname>`: fetches CertSpotter issuances with
  subdomains expanded and renders a compact table headed by
  `<nick>: Certificates for <host> (<total> total, showing <shown>):`.
  Evidence: command creation, fixes, and stabilized output in
  `irc.notgay.#not-gay.weechatlog` around lines 72915-73118; later inventory
  rows in `irc.notgay.#tcl.weechatlog` around lines 39672 and 39906.
- `.horoscope <sign>`: the one logged dot-prefixed command. Full zodiac signs
  return a single daily horoscope line; missing, short, or unknown signs return
  `Sorry, <nick>, couldn't fetch the horoscope for <arg>.`.
  Evidence: `irc.notgay.#not-gay.weechatlog` around lines 4056-4062,
  35627-35628, and 37307-37308; `irc.supernets.#superbowl.weechatlog` around
  lines 2226093-2226103 and 2234495-2234498.
- `!gay <text>`: generates an 800x800 animated GIF where the text and
  background cycle through rainbow colors out of phase, saves it under the bot
  web directory, and returns a public `gay_*.gif` URL. `PYYLMAO_WWW_DIR` and
  `PYYLMAO_WWW_BASE_URL` can override the publish path and URL prefix. For a
  temporary public host, run
  `python3 -m pyylmao.image_server`; it serves `PYYLMAO_WWW_DIR`, starts
  `cloudflared tunnel --url http://127.0.0.1:8765`, and writes the discovered
  `trycloudflare.com` URL to `PYYLMAO_WWW_BASE_URL_FILE` for the command to
  pick up without restarting the bot. The historical command wrote to
  `/usr/src/app/www`, but the reconstruction defaults to `/tmp/pyylmao-www` so
  it works without root-owned directories.
  Evidence: command creation and outputs in `irc.notgay.#not-gay.weechatlog`
  around lines 69586-69605, `irc.notgay.#tcl.weechatlog` around lines
  44241-44248, and `irc.supernets.#bowlcut.weechatlog` around lines
  42735-42758.
- `!godsays [count]`: accepts the inventory pattern `^!godsays\s*(\d)*$`.
  It prints one quoted line of unrelated words using the logged double-space
  word separation, then a `Meaning:` interpretation line. Free-form text such
  as `!godsays give me a good idea` does not match the trigger and is quiet.
  Evidence: `irc.supernets.#superbowl.weechatlog` around lines 1163636-1163638
  and the later no-output free-form attempts around lines 1808016-1808019;
  inventory rows appear in `irc.notgay.#tcl.weechatlog` around lines
  39682 and 39916.
- `!blair` / `!blair2`: fetch pinned statuses for `@r000t@ligma.pro` from the
  Mastodon endpoint `https://ligma.pro/api/v1/accounts/1/statuses?pinned=true`.
  `!blair2` mirrors the logged raw `pprint` style with `Posts from
  @r000t@ligma.pro (up to 12):`, `Post N:`, HTML content repr, and `Replies:`.
  `!blair` uses the same working endpoint but renders post and reply HTML as
  readable IRC text, avoiding the broken account-search path seen in the logs.
  Evidence: command creation and raw output in `irc.notgay.#tcl.weechatlog`
  around lines 16258-16274 and stabilization attempts around lines
  16349-16375; the original HTML and cleaned `!blair` outputs appear around
  lines 15903-16016.
- `ligma.pro/@user/<status-id> [all]`: fetches a single `ligma.pro` Mastodon
  status from `/api/v1/statuses/<id>` and renders optional img2irc avatar lines,
  `display @acct Mon DD YYYY`, wrapped post text, and `💬/♻️/❤️` stats. A
  trailing `all` fetches `/context` and renders descendants indented under the
  main post. `read_command ligma` resolves to reconstructed source because this
  command was repeatedly used as the formatting reference for other generated
  commands such as `nostr`.
  Evidence: final command-table pattern `^.*ligma\.pro/@[^/]+/(\d+)\s?(.*)$`
  in `irc.gangnet.#tclmafia.weechatlog` around lines 77512-77788 and
  stabilized output/reply rendering in `irc.notgay.#tcl.weechatlog` around
  lines 16427-18023.
- `!imdb <title>`: looks up an IMDb title and prints movie metadata. The
  historical command decorated the output with poster art, while the
  reconstruction emits the same core fields as plain IRC lines: runtime, genre,
  plot, director, writer, starring cast, ratings, and the title URL.
  Evidence: `irc.notgay.#not-gay.weechatlog` around lines 1228-1246,
  7579-7595, 19937-19954, and 21608-21625, plus
  `irc.notgay.#tcl.weechatlog` around lines 33402-33582.
- `!ud <term>` / `!urban <term>`: looks up Urban Dictionary entries. Empty
  results return `No entries found for '<term>'`; hits render as
  `Definitions for <term>`, an 80-character separator, wrapped definitions, and
  examples prefixed with `┃`.
  Evidence: `irc.notgay.#not-gay.weechatlog` around lines 104483-104485 and
  105032-105060, plus `irc.notgay.#tcl.weechatlog` around lines 45697-45720.
- `!define <word>`: looks up dictionaryapi.dev entries and renders the selected
  word and phonetic, bold Unicode part-of-speech headings, bullet definitions,
  and indented `Example:` lines.
  Evidence: command creation in `irc.notgay.#not-gay.weechatlog` around lines
  108492-108545, stabilized output in `irc.notgay.#tcl.weechatlog` around lines
  46861-47134, and the `spry` example in `irc.notgay.#not-gay.weechatlog`
  around lines 108573-108585.
- `!curl <url>` / `!curl2 <url>`: fetches URL text and prints it line by line.
  `!curl` preserves blank lines, while `!curl2` is used for more compact
  ANSI/text dumps. Long output is capped with
  `error: output truncated to <shown> of <total> lines total`.
  Evidence: `irc.notgay.#not-gay.weechatlog` around lines 1890-1905,
  2420-2540, and 120405-120410, plus
  `irc.gangnet.#tclmafia.weechatlog` around lines 13848-13866.
- `!cat <file>`: prints local text file contents line by line. The
  reconstruction serves files from a configured safe directory rather than
  arbitrary filesystem paths.
  Evidence: `irc.gangnet.#tclmafia.weechatlog` around lines 1375-1418, where
  repeated `!cat buflen.txt` invocations emit the file contents across multiple
  IRC lines.
- `!mdcat <file>`: prints an options dict first, then renders a local markdown
  file to IRC text. Missing files reply as
  `mdcat: no such file @ /usr/src/app/assets/tmp/<file>`. The reconstruction
  serves files from a configured safe directory and implements the logged
  simple markdown and pipe-table rendering shape.
  Evidence: `irc.notgay.#tcl.weechatlog` around lines 21468-21500,
  35461-35473, and 37939-37975; `irc.notgay.#not-gay.weechatlog` around lines
  59934-59950 and 80555-80590; and `irc.supernets.#superbowl.weechatlog`
  around lines 2117744-2117770.
- `!tools` / `!tools enabled`: emits an LLM tool inventory table with tool name,
  plugin, and enabled status. `+tool <name>`, `+tools <names...>`, and their
  `-tool` / `-tools` forms persistently toggle LLM tools and reply with the
  logged `enabled:` / `disabled:` plus `✔ <name>` lines. The reconstructed
  OpenRouter client exposes only enabled command/debug tools to LLM calls and
  prints the logged trace line before the final answer, for example
  `read_command args: {'name': 'kv'}`.
  Implemented tool backends include `read_command`, `write_command`,
  `revise_pattern`, `install_packages`, `run`, `irc_command`,
  `get_chat_history`, disabled-by-default IRC helpers (`channel_list` /
  `get_channel_users`), disabled-by-default built-ins (`llm_version` /
  `llm_time`), skill helpers (`read_skill`, `list_skills`, `create_skill`,
  disabled-by-default `query_skills` / `update_skill`) with built-in notes for
  the logged `KV` / `kvstore`, `img2irc`, `imghax`, `md2irc`, and `llm` skills,
  memory helpers, web-backed `semantic_search`, `save_artifact`,
  `read_artifact`, and `list_artifacts`. The disabled table
  inventory also includes the later logged `eval` row, which runs a short
  Python snippet when explicitly enabled. `irc_command` records raw IRC command
  requests in state and, when the bot is connected to IRC, sends them through
  the live IRC connection for command debugging. Successful live raw commands
  return logged-friendly tool traces such as `Joined #chan`,
  `Message sent to nick`, `Invited nick to #chan`, or `Nickname changed to
  nick`. The live IRC client keeps `channel_list` / `get_channel_users` state
  fresh from JOIN, PART, QUIT, NICK, KICK, and numeric NAMES replies, preserving
  the server-provided NAMES order for generated/debug tooling. The logged singular toggle
  `+tool query_skill` maps to the table/schema tool name `query_skills`; the
  older singular artifact helper name `list_artifact` is accepted as an alias
  for `list_artifacts`.
  The later log-created public `eval` command is also reconstructed as a
  generated-command-style debug command: its unanchored pattern is
  `(?i)\beval\b\s*(.*)`, it evaluates only the captured Python expression,
  emits stdout before the returned value, recreates module globals on each
  invocation, and keeps mutations to the generated `__builtins__` dictionary
  across invocations.
  Generated command artifacts and skills are persisted under the bot state
  directory. The `run` tool also resolves saved Python debug artifacts for
  logged forms such as `python ['debug_ansi']`, `python ['/home/pyylmao/bot/debug_ansi.py']`,
  and `exec ['debug_ansi.py']`.
  `semantic_search` accepts the logged `query`, `phrases`, and `profile`
  arguments, preserves logged profiles such as `instant`, `balanced`, `news`,
  `comprehensive`, and `web_search`, defaults the visible trace to
  `Profile: balanced`, and keeps memory lookup separate as `search_memories`.
  Python command artifacts written by `write_command` are routable at runtime
  through the modern `llm.Toolbox` class API, the logged `entrypoint(args,
  channel, nickname, username, hostname)` function shape, and older
  `run(bot, channel, sender, args)` / `command(bot, args)` callables. When none
  of those exist, a fallback `main()` callable is invoked, and clearly
  script-style artifacts such as files with a shebang or top-level print are
  executed as a script body. Output printed to stdout/stderr becomes IRC lines,
  return values are preserved for
  compatibility, and exceptions render traceback lines like the historical
  generated command failures. Stored generated-command regexes use search
  semantics, so unanchored patterns can trigger after earlier chat text just
  like the logged generated `eval` command did. The `llm.Toolbox` shim supports event commands
  using `trigger_on` and `match_field` for message and non-message IRC events
  including `join`, `part`, `quit`, `nick`, `kick`, `ctcp`, `notice`, and
  `invite`; printed output can be routed with `send_to` to explicit targets or
  all currently joined channels.
  The OpenRouter system prompt and tool schemas describe this standard API up
  front, including that executable source belongs in the `code` argument while
  `content` is only descriptive, and that command tests should use `run` with
  `cmd_name` and `args`. The schemas also allow logged optional-argument debug
  calls such as `read_command args: {}` and code-only `write_command` calls
  whose command name is inferred from `pattern`. The class API's injected
  `connection` object supports logged raw IRC helpers such as `privmsg`,
  `privmsg_many`, `notice`, `action`, `ctcp`, `ctcp_reply`, `join`, `part`,
  `whois`, `invite`, `kick`, `mode`, `nick`, `quit`, `send_raw`, `send_items`,
  `ping`, and `add_global_handler`, plus state-backed `channels` and
  `reactor.channels` maps exposing python-irc-style channel user helpers such
  as `users()`, `has_user()`, `opers()`, and `voiced()`. Generated/debug code that imports
  python-irc-style modules can use the bundled top-level shims `irc.bot`,
  `irc.client`, `irc.strings`, and `irclib.client`; these expose `Reactor`,
  `ServerConnection`, `SingleServerIRCBot`, `Channel`, parsed
  `Event.source.nick/user/host`, `Event.args`, and basic IRC case folding while
  forwarding raw IRC methods through the live bot connection.
  Generated command code can make nested model calls with
  `llm.get_model("openrouter/provider/model").prompt(...).text()`. The shim
  supports the logged Python `llm` shapes `schema=...`, `system=...`,
  `temperature=...`, `options={"temperature": ...}`, and image attachments via
  `llm.Attachment(url=..., type="image/png")`.
  `write_command` accepts the logged `code` argument, treats `content` as a
  description when both are present, and infers the persisted regex from module
  or class `pattern = ...` assignments if the tool call omits a separate
  `pattern` argument. It also tolerates a missing `name` when the regex trigger
  contains an inferable command name such as `^!inspect2$`, matching the
  temporary helper-command debug flow. Generated command names may start with a
  digit, matching logged artifact/debug flows such as `read_command
  3daudio` and `revise_pattern 3daudio`. After persisting the artifact it emits
  the logged dependency scan result `No requirements found in provided code.`.
  OpenRouter tool calls use the logged guardrails from long command-debug
  sessions: the default chain limit is 32 calls, and calls past the 600-second
  wall-clock limit are visibly replaced with
  `Tool calls cancelled: max_time 600s reached` while the model is allowed to
  finish.
  `read_command` reads generated command artifacts back by name before falling
  back to reconstructed built-ins; when called without a name, it lists
  generated and built-in command names/patterns. Generated artifact lookup also
	  falls back to `<generated_dir>/<name>.py` and the historical package layout
	  `<generated_dir>/<name>/__init__.py` when JSON state metadata is missing or
	  stale. It also resolves the logged KV helper/API lookup names `kv_get`,
  `kv_set`, `kv_append`, `kv_merge`, `kv_delete`, `kv_query`, `KvContext`, and
  `KvResult` to the reconstructed `pyylmao.kv.backends.sqlite` source. `run`
  accepts both a raw shell `command` and the logged command
  shape `cmd_name`/`args`, dispatching first to generated command artifacts, then reconstructed bot commands such as
  `define`, `iching`, `zscore`, and `horoscope`, then subprocess execution.
  It also supports `cmd_name=exec` for short Python snippets.
  The OpenRouter tool registry exposes command-backed tools directly by command
  name when a router command runner is available. Those command tools accept an
  `args` string and dispatch through the same generated/reconstructed command
  path as `run cmd_name=...`, matching the live log discussion that the command
  structure exists so commands can also be used as tools.
  `read_command imgcap` resolves to reconstructed generated-command-style
  source with the logged URL regex, `llm.get_model(...).prompt(...)`,
  `llm.Attachment(url=..., type="image/png")`, and the public
  `from pyylmao.kv import ...` helper API. This keeps the image-captioning
  command available as source evidence for LLM skill/command-writing sessions
  without forcing the main router to caption every posted URL.
  Generated command modules receive a scoped `kv` helper for
  `commands.<name>` state, and the logged import path
  `from pyylmao.kv.backends.sqlite import KvContext` is available for command
  code that constructs `KvContext('commands.<name>')` directly. The
  compatibility result object supports the logged `.expect(...)`,
  `.success()`, `.failed()`, `.json()`, `.stats()`, `.to_dict()`, and boolean
  success checks. `KvContext.merge(path, dict_value)` and direct `kv_merge`
  imports recursively merge dictionaries, matching the logged guidance for
  trivia question caches such as `kv.merge('cache.category.<category_id>', entries)`.
  Generated command code and saved Python debug artifacts can `import llm`.
  The shim supports `llm.get_tools()` to inspect available tool
  names/plugins/enabled status through either iteration or mapping-style
  lookups, matching the logged `all_tools = llm.get_tools()` command/debug
  path. The generated-command inventory includes artifact helpers such as
  `save_artifact` and `read_artifact`, even though logged `!tools` output did
  not always render every artifact helper as a separate table row. Generated
  commands present in state are also returned when explicitly requested, and
  those entries are callable from generated command code using `tool(args=...)`,
  preserving command-as-tool behavior inside the bot's Python command API.
  `save_artifact` writes text artifacts, including nested paths such as
  `pcb-generator/index.html`, into the served asset directory when
  `PYYLMAO_WWW_DIR` is configured and returns the logged
  `━━☛ New artifact: <url>` line. Parent directories are created automatically,
  and the logged optional `create_dirs` argument is accepted. `read_artifact`
  reads those text artifacts back for follow-up command/debug work, and also
  resolves logged generated-command debug paths such as
  `commands/spam/__init__.py`, `src/commands/spam/__init__.py`, and
  `spam/__init__.py` through the generated source loader.
  Evidence: `irc.notgay.#not-gay.weechatlog` around lines 32950-32958 and
  86789-86805, 101850-101878, 105190-105192, and 108497-108504, plus
  `irc.notgay.#tcl.weechatlog` around lines 29365-29383; omitted-name
  `read_command` appears around `irc.notgay.#not-gay.weechatlog` line 108477,
  code-only `write_command` calls appear around lines 75194-75208, `llm.get_tools()`
  appears around line 33004, and generated command KV usage appears around
  lines 40527 and 40763-40775 plus `irc.notgay.#tcl.weechatlog` around lines
  34371-34606 and `irc.supernets.#superbowl.weechatlog` around lines
  812127-812153. Artifact writes and
  reads appear in `irc.notgay.#not-gay.weechatlog` around lines 58065, 59009,
  60805-60807, 94325-94385, 101707, and 109283-109285. The logged
  `imgcap` read/update/skill-creation flow appears in
  `irc.notgay.#not-gay.weechatlog` around lines 79324-79344 and 79511-79521.
  Live raw IRC tool calls appear in `irc.notgay.#tcl.weechatlog` around lines
  8840-9096 and 38790-38800, and in `irc.notgay.#not-gay.weechatlog` around
  lines 68157-68169, 73065, and 75179-75183. `run` command-name dispatch
  appears in `irc.notgay.#not-gay.weechatlog` around lines 86821, 86846, 86947,
  96831-96857, 101899-101970, 108507, and 129731-129735, plus
  `irc.notgay.#tcl.weechatlog` around lines 39748 and 44993-45082. Historical
  python-irc import snippets appear in `irc.supernets.#bowlcut.weechatlog`
  around line 17567 and `irc.supernets.#superbowl.weechatlog` around lines
  165580-165583, 663848-663854, 663860-663861, and 771512-771513. The original
  `ServerConnection` method inventory was probed in
  `irc.supernets.#bowlcut.weechatlog` around lines 83689-83695.
- `!help`: emits the radio command glossary, including `!np`, `!next`, `!skip`,
  `!queued`, playlist management commands, and `+add <playlist> <link>`.
  Disabling the `radio` trigger suppresses this help output.
  Evidence: `irc.notgay.#tcl.weechatlog` around lines 46662-46668 and
  `irc.notgay.#not-gay.weechatlog` around lines 123847-123857.
- Golem control commands:
  - `!> clear`: replies `* Context cleared *` and clears prompt context.
  - `!clear`: listed as `clearhistory`; the reconstruction maps it to the same
    channel history clear behavior.
  - `!> key=value`: updates persisted golem parameters and replies
    `Parameters updated: {...}`. Numeric values are rendered as Python ints or
    floats, matching the logged dict representation.
  - `!> -key`: removes a persisted golem parameter.
  - unknown controls such as `!> config` reply `Unknown command: config`.
  Evidence: `irc.notgay.#tcl.weechatlog` around lines 3312-3412,
  3439-3440, 3488-3489, and 5727-5750.
- `!queued`: lists queued radio tracks; with an empty queue the bot replies
  `Queue is empty.`
  Evidence: `irc.notgay.#not-gay.weechatlog` around lines 123862-123864 and
  `irc.notgay.#tcl.weechatlog` around lines 47505-47506.
- `!new <name>`: creates a radio playlist and replies
  `Playlist  <name>  successfully created!`
  Evidence: `irc.notgay.#not-gay.weechatlog` around lines 121307-121308 and
  123832-123843.
- `!remindme` / `!reminder` / `!reminders`: stores reminders, lists active
  reminders, and checks for due reminders when the user next talks. Creation
  replies use `Created reminder '<text>' for <UTC time> GMT 🔔`; due reminders use
  `⏰ Reminder for <nick>: <text>`.
  Evidence: `irc.notgay.#not-gay.weechatlog` around lines 32597-32610,
  32649-32665, 32723-32910, and 118466-118494.
- `!vtrade`:
  - `!vtrade` / `!vtrade help`
  - `!vtrade claim <alias>`
  - `!vtrade buy <ticker> <amount>`
  - `!vtrade buy <ticker> <amount> convert`
  - `!vtrade sell <ticker> <amount>`
  - `!vtrade confirm <code>`
  - `!vtrade convert <from> <to> <amount>`
  - `!vtrade <alias>`
  - `!vtrade *`
  Evidence: `irc.notgay.#heck.weechatlog` around lines 3510-3560,
  1690-1709, 2400-2435, and 5190-5235, plus
  `irc.notgay.#not-gay.weechatlog` around lines 9930-10015.
- `!stock <ticker> [arg]`: fetches historical Yahoo chart data and renders an
  eight-row terminal price graph. No argument shows `Past 30 Days`; the logged
  wide argument form such as `!stock COHR 90` renders as `All Time`.
  Evidence: `irc.notgay.#not-gay.weechatlog` around lines 1146-1155,
  1488-1525, and 98776-98798.
- `!zscore [question]`: flips an ANU QRNG-backed coin to choose whether excess
  zeros or ones are positive, samples a block of bits, prints zeros/ones counts,
  a meter, and an outlook line with a one-sided normal-tail p-value. The
  reconstruction supports ANU's current AWS-hosted Quantum Numbers API via
  `PYYLMAO_ANU_QRNG_API_KEY`; without a key it tries the historical
  `qrng.anu.edu.au/API/jsonI.php` endpoint and emits logged-style `URL Error:`
  output if the endpoint fails.
  Evidence: `irc.notgay.#not-gay.weechatlog` around lines 16759-16778 and
  41772-41863, plus `irc.notgay.#tcl.weechatlog` around lines 22176-22185.
- `!fortune [question]`: throws six I Ching stalk values, prints the primary
  hexagram and, when old lines are present, `changing to` the transformed
  hexagram. The body uses solid/broken line art, interpretation text, and a
  final `stalks thrown: ...` line.
  Evidence: `irc.notgay.#not-gay.weechatlog` around lines 14456-14466 and
  16240-16260, `irc.notgay.#tcl.weechatlog` around lines 34365-34420, plus
  `irc.gangnet.#tclmafia.weechatlog` around lines 2718-2736.
- `!weather <location>`: replies with compact wttr.in current conditions:
  icon, Celsius temperature, wind, relative humidity, precipitation, and UV burn
  estimate. Missing location returns `Usage: !weather <location>`.
  Evidence: `irc.notgay.#not-gay.weechatlog` around lines 18797-18806,
  58975-58977, and 119490.
- `!forecast <location>`: replies with a seven-column box-drawing forecast table
  containing weekdays, weather icons, and high temperatures in Celsius. The
  reconstruction uses Open-Meteo for the seven-day daily forecast because wttr's
  current JSON response only returns three forecast days.
  Evidence: `irc.notgay.#not-gay.weechatlog` around lines 95826-95840 and
  119505-119521.
- `!livebench [-top N] [-sort column [asc|desc]] [+simple] [categories]`:
  fetches the current public LiveBench leaderboard from `livebench.ai` and renders a table. Bare
  `!livebench` shows the full task table; `+simple` shows grouped categories
  such as `REASONING`, `CODING`, `AGENTIC_CODING`, and optional
  comma/space-separated category filters sorted by that subset average unless
  `-sort` names a specific task/category.
  Evidence: `irc.notgay.#tcl.weechatlog` around lines 21364-21425 and
  30228-30255, `irc.notgay.#not-gay.weechatlog` around lines 121128-121155,
  plus `irc.supernets.#superbowl.weechatlog` around lines 809531-809548 and
  2176657-2176680.
- Twitter/X status previews trigger on the logged command-table URL forms
  `twitter.com`, `x.com`, `xcancel`, and `nitter` status URLs. The reconstructed
  `twitter` runner also accepts `!twitter <status-id-or-url>` so LLM tool calls
  such as `run args: {'cmd_name': 'twitter', 'args': "['205201...']"}` reach
  the same command surface, and `read_command twitter` returns reconstructed
  source for command-debug sessions. The raw tweet JSON is saved best-effort to
  the historical `/usr/src/app/t.json` path with runtime-safe fallbacks.
  Evidence: `irc.notgay.#not-gay.weechatlog` around lines 85034-85048 and
  101890-101985, plus `irc.notgay.#tcl.weechatlog` around lines 44988-45088.
- `ligma.pro/@user/<status-id> [all]` Mastodon status previews trigger on the
  logged generated-command URL regex and render status/reply output in the same
  avatar-plus-text layout used as a reference for later `nostr` work.
- `nostr:<note|nevent|event-id|npub>` parses NIP-19 Nostr references and
  fetches matching text notes from WebSocket relays. The output follows the
  later stabilized generated-command shape: optional img2irc avatar lines,
  `display @name Mon DD YYYY` header, and wrapped post content. `read_command
  nostr` resolves to reconstructed source, and `run cmd_name=nostr` prefixes
  args as `nostr:<arg>` to match the command-debug workflow. The implementation
  also supports profile metadata lookup for display name, username, and avatar.
  Evidence: repeated `read_command`/`write_command`/`run` repair loops in
  `irc.supernets.#bowlcut.weechatlog` around lines 80670-80932 and final
  successful renders around lines 81250-81460.
- `!ansi2irc <url>` / `!irc2ansi <url>` fetches text from a URL and converts
  between ANSI escape sequences and IRC formatting. The reconstructed command
  preserves the logged debugging surface: CP437 detection for 16colo.rs ANSI
  art, UTF-8 fallback, SAUCE record stripping, basic ANSI cursor movement and
  SGR color handling, and `run cmd_name=ansi2irc` / `read_command ansi2irc`
  compatibility. It deliberately keeps the bounded IRC output behavior instead
  of streaming unbounded art.
  Evidence: command creation, repeated `read_command`, `write_command`, `run`,
  `save_artifact`, and `exec` debugging in `irc.gangnet.#tclmafia.weechatlog`
  around lines 13890-14820.
- `!poll ...`, `?poll`, bare single-label votes, and `!vote <label>` now
  reconstruct the repeatedly rewritten generated `poll`/`vote` surface.
  Labeled forms such as `A. Pizza B. Tacos`, numeric forms such as
  `1. Pizza 2. Tacos`, and the later flexible `question? yes/no/kind of`
  shape are accepted. Polls are channel-scoped, one vote per nickname is
  tracked, `?poll` shows the current question/options/results, and
  `!poll stop` emits the logged stop line. `read_command poll`, `read_command
  vote`, `read_command votes`, and `read_command poll_vote` all resolve to the
  reconstructed source for command-debug sessions.
  Evidence: repeated `read_command`/`write_command` repair loops and successful
  command output in `irc.supernets.#superbowl.weechatlog` around lines
  1775130-1775160, 1778872-1778950, 2254670-2255085, and 2373554-2373780.
- `!trivia` reconstructs the generated command that was iterated on in
  `irc.notgay.#not-gay.weechatlog` and `irc.supernets.#superbowl.weechatlog`.
  It uses the final local-CSV category list from
  `/usr/src/app/assets/trivia/categories/*.csv` when those files exist, with a
  small fallback set only so this repo can run without the historical CSV
  assets. Supported surfaces include `!trivia categories`, `!trivia category
  <name|any>`, `!trivia difficulty <easy|medium|hard>`, `!trivia threshold
  <0.0-1.0>`, `!trivia mode <dumb|smart>`, `!trivia rephrase`, bare
  `!trivia` for the next question, and free-text answers while a question is
  active. State and stats live under `commands.trivia` in the shared KV tree,
  with channel keys such as `_not-gay`, matching the logged `!kv` probes.
  Wrong guesses are silent, A/B/C/D answers are ignored, Levenshtein matching is
  checked before smart-mode semantic matching, correct answers auto-advance to
  the next question, and question suffixes use the logged dark-grey IRC color
  wrapper around `(difficulty - Category)`. `read_command trivia` resolves to
  the reconstructed source for command-debug sessions.
  Evidence: creation and repair logs around `irc.notgay.#not-gay.weechatlog`
  lines 40470-41495, plus live use around
  `irc.supernets.#superbowl.weechatlog` lines 2248480-2248670.
- `!pheno [location]` reconstructs the generated `phenoguessr` command. Bare
  `!pheno` starts a game, writes state under `commands.phenoguessr`, optionally
  renders an asset image through `img2irc`/`imghax` using the logged
  `output_mode` and `img2irc_args` KV settings, then emits `New phenotype
  guesser started! Guess the location with !pheno <location>`. Guesses render
  the logged shapes: `<nick> guessed <location>. Incorrect! <km> km (<mi> mi)
  away.`, `<nick> guessed <location>! BULLSEYE! Score: 5000 ... They win!`,
  `Technically correct!` for near accepted fallbacks, `No active game. Start
  one with !pheno`, and `Could not resolve the location for: '<query>'`.
  `read_command phenoguessr` and `read_command pheno` resolve to reconstructed
  source, and `run cmd_name=phenoguessr` / `run cmd_name=pheno` prefix args as
  `!pheno` for command-debug sessions. The repo does not currently contain the
  historical `assets/phenoguessr/*` image corpus, so the command tolerates
  missing assets and still runs the stateful game.
  Evidence: creation/repair logs in `irc.gangnet.#tclmafia.weechatlog` around
  lines 11707-11835, KV state probes around lines 45508-45616, active gameplay
  around lines 45670-47111, and earlier gameplay in
  `irc.supernets.#superbowl.weechatlog` around lines 2377320-2377500.
- `!vocoder <text>` reconstructs the generated non-AI speech-synthesis command.
  It writes a mono WAV into the served web directory and returns a public URL in
  the later logged shape `.../2/<12hex>.wav`. The older generated surface
  `vocoder <filename.wav> <text>` is also supported and preserves the requested
  filename, matching early successful output such as `https://cte.pcp.ovh/huh.wav`.
  The synthesizer is dependency-free standard-library code using simple
  phoneme-ish formant/noise/stops rather than an external TTS engine.
  `read_command vocoder` resolves to reconstructed source, and `run
  cmd_name=vocoder` prefixes args as `!vocoder` for command-debug sessions.
  Evidence: creation and repair logs around `irc.notgay.#tcl.weechatlog` lines
  21460-21701, final `!vocoder` URL output around lines 39799-39835, and
  later use in `irc.gangnet.#tclmafia.weechatlog` around lines 12383-12390 and
  15879-15897.
- `!ufc [options]`: fetches real UFC card data from ESPN's public MMA
  scoreboard. It supports the logged `--help` output, `--filter`,
  `--fighter`, `--prev`, `--next`, `--tw`, `--width`, `--refresh`,
  `--numbered`, `--ufc`, `--fightnight`, `--contender`, and `--main` flags,
  plus the old key/value form such as `filter 325 width 14 tw 70`. Matching
  cards render FIGlet-style headings when `pyfiglet` is available and compact
  fight rows with country, record, scheduled/final state, and score data. The
  reconstruction does not yet rebuild the historical ANSI headshot art.
  Evidence: help and outputs in `irc.notgay.#not-gay.weechatlog` around lines
  93180-93320, stabilized card renders in `irc.notgay.#tcl.weechatlog` around
  lines 40850-41340 and 42300-42640, plus early renders in
  `irc.supernets.#bowlcut.weechatlog` around lines 11420-11475.
- Regex/feed filter commands:
  - `!add <pattern>`
  - `!del <number-or-pattern>`
  - `!blist`
  Evidence: `irc.notgay.#tcl.weechatlog` around lines 146700-146875 and
  `irc.notgay.#bluesky.weechatlog` around lines 1934-2219 and 3075.
- `!drink`: starts a long-running Bluesky watcher. The bot immediately replies
  `🤖 Bot is listening`, then emits matching Bluesky post text with a
  `https://bsky.app/profile/.../post/...` URL. `!list` shows it as
  `drink args=[]`.
  Evidence: `irc.notgay.#bluesky.weechatlog` around lines 2182-2215 and
  `irc.notgay.#tcl.weechatlog` around lines 8076-8683.
- `!img2irc` / `!img2irc2` URL image rendering:
  - `width N`, `width=N`, and `--width N`
  - `render irc|ansi|ansi24`
  - `+blocks`, `blocks half,full`, and basic contrast/brightness/saturation/gamma
  - `!hax <url> [width] [options]` is the historical alias, gated by `imghax`
  Evidence: `irc.notgay.#not-gay.weechatlog` around lines 705, 1538, 5682,
  6610, and 52354, plus `irc.notgay.#tcl.weechatlog` around lines 4108-4994
  and 8500-9300.
- `!ascii <name>` case-sensitive text-art lookup. Missing entries are reported
  as `No such file: <name>.txt`.
  Evidence: `irc.notgay.#not-gay.weechatlog` around lines 2550-2655 and
  102620-102622.
- `!summary` / `!wsummary` source summarization:
  - accepts YouTube URLs, webpage URLs, PDFs, bare domains, and optional prompts
  - falls back to the most recent URL remembered for the channel
  - emits a title line before the model summary when a title can be extracted
  Evidence: `irc.notgay.#not-gay.weechatlog` around lines 40097-40115,
  45524-45580, and 48616-48618.

## Remaining Major Gaps

- Full Bluesky firehose ingestion; current implementation uses Bluesky AppView
  `app.bsky.feed.searchPosts` polling for dependency-light feed behavior.
- Exact `!img2irc` block-selection, dithering, and image-caption behavior.
- Full historical `!ascii <name>` art database beyond the recovered seed set.
- Exact logged `!summary` formatting, YouTube view/like/date metadata, and
  old command self-modification traces.
- `!kv` persists and renders logged values, and generated command code can use
  scoped `commands.<name>` KV state. Arbitrary user-written `commands.*`
  entries are still not treated as new command definitions by themselves.
- Trigger toggles for missing historical/generated commands return the logged
  `Trigger <name> does not exist` response until the command is present in the
  reconstructed command table or generated command store.
- Reminder parsing is deterministic and covers the logged relative and common
  absolute forms; the historical command used an LLM for broader natural
  language parsing.
- Exact historical vTrade, `!stock`, and weather icon-selection fidelity.
- Radio playback/search/queue backends; current implementation mirrors the
  logged help glossary, empty queue response, and local playlist creation only.
