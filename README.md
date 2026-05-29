# pyylmao

Reconstruction of the `pyylmao` IRC bot from WeeChat logs in the `diverse-deer`
Incus VM.

Implemented in this first pass:

- IRC client with `PING`/`PONG`, `NICK`/`USER`, channel join, and `PRIVMSG` replies.
- OpenRouter chat triggers observed in logs: `gpt, ...`, `gpt ...`, `grok, ...`,
  `grok ...`, `@grok ...`, `@@grok ...`, `!ai ...`, and `!summary ...`.
  Leading request options include `maxh=N`, `temperature=N`, and quoted
  `system="..."`.
- Stateful `!alias list|get|set|delete|set-default|get-default` model alias
  management, including alias chat triggers such as `@d ...`, `@@glm ...`, and
  `hy2, ...`.
- `!models` compact OpenRouter model listing with context length and current
  input/output pricing.
- `$llm <model>` LLM pricing lookup with logged provider tables and OpenRouter
  model metadata fallback.
- URL title previews in the `━━☛ title` style.
- YouTube URL previews in the logged
  `▶ title | channel [duration] views likes date` style, using `yt-dlp`
  metadata when available with a YouTube player/oEmbed fallback plus
  best-effort public view/like counts. The logo and metadata chunks use the
  original IRC color islands: red background for `▶`, light-grey background
  around each padded stats/date island. If YouTube blocks anonymous `yt-dlp`
  extraction,
  `PYYLMAO_YOUTUBE_COOKIES` can point at a cookies file.
- Twitter/X status previews for logged `twitter.com`, `x.com`, `xcancel`, and
  `nitter` URL forms, plus `run cmd_name=twitter` / `!twitter <id-or-url>`
  compatibility for the command-debug workflow.
- `ligma.pro/@user/<status-id> [all]` Mastodon status previews in the logged
  generated-command style, including avatar rendering, stats, and optional
  reply rendering.
- `nostr:<note|nevent|event-id|npub>` Nostr post previews, including NIP-19
  parsing, relay fetches, profile metadata lookup, optional avatar rendering,
  and `read_command nostr` / `run cmd_name=nostr` compatibility.
- `!pheno [location]` generated `phenoguessr` reconstruction with the logged
  start, wrong-guess, correct-guess, no-active-game, and unresolved-location
  replies. State and settings live under `commands.phenoguessr`, including
  `output_mode` and `img2irc_args` for image rendering.
- `!ansi2irc <url>` / `!irc2ansi <url>` URL-based ANSI/IRC conversion with
  CP437 detection, SAUCE stripping, basic ANSI cursor/color handling, and
  `read_command ansi2irc` / `run cmd_name=ansi2irc` compatibility.
- `ping` / `p0ng!` liveness reply.
- `?<domain>` Domainr-style domain status checks such as `active`,
  `undelegated inactive`, and `premium reserved`.
- `!host <hostname-or-ip>` forward/reverse DNS lookup and `!crt <hostname>` /
  `?crt <hostname>` CertSpotter certificate table lookup.
- `.horoscope <sign>` daily horoscope lookup with the historical dot-prefixed
  trigger and full zodiac-sign matching.
- `!gay <text>` animated rainbow GIF generation, with generated images served
  from a configurable web directory.
- `!godsays [count]` quoted random-word oracle with the logged `Meaning:`
  interpretation line and quiet behavior for non-matching free-form prompts.
- `!blair` / `!blair2` pinned `@r000t@ligma.pro` Mastodon status dumps using
  the working `accounts/1/statuses?pinned=true` endpoint from the logs.
- `!kill <id>` / `!kill all` cancellation for running async bot jobs.
- `!reload [module]` and `!rehash` maintenance compatibility replies for logged
  handler/config reload commands.
- `!test <args>` debug/challenge response that echoes parsed arguments and a
  four-digit relay code.
- Stateful `!enable <trigger>` / `!disable <trigger>` command toggles for known
  reconstructed and generated triggers. Unknown names return the logged
  `Trigger ... does not exist` reply instead of creating inert future toggles.
- Stateful `!kv get|set|query|append|del|info|modes` nested key/value
  inspection and mutation with dot paths, quoted keys, bracket indexes,
  list slices such as `[-2:]`, literal query values such as `"ok"`,
  `|length`, and `|keys` queries. Missing/null `|keys` paths keep the logged
  jq-style `null (null) has no keys` error, and malformed jq key syntax such as
  `._not-gay` or single-quoted channel keys keeps the logged compile-error
  shape. `set` renders the newer logged `Set <path> to:` value tree;
  unsupported verbs keep the logged `unknown error, op=... args=[...]` shape.
- `!list` / `!listen` active-command reporting, including `No commands running.`
  when the run queue is empty.
- `!cmds` log-style command inventory table, including generated commands
  written by `write_command`.
- `!chess [gid] <new|move|show|draw|resign>` persistent IRC chess games with
  logged Unicode board rendering and python-chess move validation.
- `!cowsay <text>` speech bubble rendering with the logged standard bubble
  shape, gated by the historical `cows` trigger name.
- `!hf` Hugging Face trending model list in the observed `HF Trending` format.
- `!imdb <title>` movie/series lookup with runtime, genre, plot, director,
  writer, cast, IMDb rating, and title URL.
- `!ud <term>` / `!urban <term>` Urban Dictionary lookup using the logged
  `Definitions for ...` block, examples prefixed with `┃`, and no-entry
  response.
- `!define <word>` dictionaryapi.dev lookup rendered as the logged word,
  phonetic, part-of-speech headings, bullet definitions, and examples.
- `!curl <url>` / `!curl2 <url>` text URL fetchers with line output,
  truncation protection, and `curl2` blank-line compaction for ANSI/text dumps.
- `!cat <file>` local text file output from a configured safe file directory.
- `!mdcat <file>` local markdown file rendering from a configured safe file
  directory, including the logged options prelude and missing-file diagnostics.
- `!figlet <font> <text>` / `!fg <font> <text>` FIGlet rendering, including
  logged bad-font diagnostics and a built-in `Calvin_S` fallback.
- `!light [color] [brightness]` safe no-op light controller compatibility,
  with logged color-change replies and brightness-only quiet operation.
- `!livebench [-top N] [-sort column [asc|desc]] [+simple] [categories]`
  LiveBench leaderboard tables fetched from the public LiveBench site, with
  logged simple/full column layouts and category sorting.
- `!ufc [options]` live ESPN UFC card lookup, including logged help text,
  event/fighter filters, old key/value arguments, numbered/fight-night/main
  filters, and compact fight stat rows.
- `!tools` / `!tools enabled` LLM tool inventory table in the modern logged
  style, plus `+tool` / `-tool` toggles for the LLM tool schema set.
- LLM tool-calling backends for the logged command/debug workflow:
  `read_command`, `write_command`, `revise_pattern`, `install_packages`, `run`,
  `irc_command`, `get_chat_history`, disabled-by-default IRC/default helpers
  such as `channel_list`, `get_channel_users`, `llm_version`, `llm_time`, and
  `eval`, skill helpers including disabled-by-default `query_skills` /
  `update_skill`, memory helpers, web-backed `semantic_search`, `save_artifact`,
  `read_artifact`, and `list_artifacts`. Tool calls emit the logged `<tool> args: {...}` trace lines
  before the model answer. `run` supports both shell commands and the logged
  `cmd_name`/`args` form for generated command artifacts, reconstructed bot
  commands, saved Python debug artifacts, and subprocess execution. `save_artifact` writes text artifacts into the
  served asset directory, accepts the logged optional `create_dirs` argument
  for nested paths, and returns a public URL when the image-server /
  cloudflared service is running. `irc_command` records raw IRC command
  requests and sends them through the live IRC connection in the running bot.
- The log-created public `eval` debug command is reconstructed with the
  generated-command pattern `(?i)\beval\b\s*(.*)`. It evaluates the captured
  Python expression, emits printed stdout before the result, keeps generated
  command globals per invocation, and preserves the logged persistent
  `__builtins__` mutation behavior used for later debug imports.
- Generated Python command artifacts from `write_command` are routable at
  runtime via their stored regex pattern, the modern `llm.Toolbox` class API,
  the logged `entrypoint(args, channel, nickname, username, hostname)` shape,
  and older `run(bot, channel, sender, args)` / `command(bot, args)` callables.
  Script-style artifacts can also use a fallback `main()` callable, or a clear
  script body such as a shebang/top-level print when no standard callable exists.
  Stored trigger regexes are searched, not only matched at the start, preserving
  the logged generated `eval` behavior where an unanchored pattern fired later
  in a normal chat line.
  The `run` tool can execute class-only `llm.Toolbox` commands directly when no
  legacy callable exists. Injected `connection` objects include the logged raw
  IRC helpers plus `get_nickname()`, state-backed `channels`, and a
  python-irc-style `reactor.server()` / `reactor.channels` shim for generated
  command compatibility.
  The OpenRouter tool registry also exposes command-backed tools directly by
  command name when a router command runner is available, so reconstructed
  commands such as `define` and generated commands can be called as LLM tools
  with an `args` string instead of going through a separate wrapper.
  Top-level python-irc compatibility imports are bundled for generated/debug
  code: `import irc.bot`, `import irc.client`, `import irc.strings`, and
  `from irclib import client`. The shim exposes `Reactor`, `ServerConnection`,
  `SingleServerIRCBot`, parsed `Event.source.nick/user/host`, `Event.args`,
  basic IRC case folding, and raw IRC forwarding through the live bot
  connection. The raw connection surface includes common python-irc helpers such
  as `action`, `ctcp_reply`, `privmsg_many`, `ping`, `send_items`, and handler
  registration no-ops used by generated/debug snippets.
  Class-based commands can also trigger on IRC events such as `join`, `part`,
  `quit`, `nick`, `kick`, `ctcp`, `notice`, and `invite`, match fields such as
  `raw_line` and `nickname`, and route printed output with `send_to`.
  `!reload <name>` refreshes a generated command from disk. `write_command`
  accepts logged `code` arguments, treats `content` as a description when both
  are present, infers module or class `pattern = ...` assignments, emits the
  logged dependency scan result, and `read_command` can read generated artifacts
  back by name, including `<generated_dir>/<name>.py` files and historical
  `<generated_dir>/<name>/__init__.py` packages whose JSON state metadata is
  missing or stale. `read_command` also resolves the log-proven `ansi2irc`,
  `twitter`, `nostr`, and `phenoguessr` command sources and KV
  helper/API names `kv_get`, `kv_set`, `kv_append`, `kv_merge`, `kv_delete`,
  `kv_query`, `KvContext`, and `KvResult` to the reconstructed backend source.
  Generated command modules receive a scoped `kv` helper, with compatibility
  support for `from pyylmao.kv.backends.sqlite import KvContext` and the logged
  trivia-cache style `kv.merge(path, dict_value)` API.
  The generated-command/top-level `llm` shim supports nested
  `llm.get_model(...).prompt(...).text()` calls with schema hints, system
  prompts, temperature options, image attachments, and the logged
  `llm.get_tools()` inventory shape for command/debug tooling, including
  artifact helpers such as `save_artifact` and `read_artifact` even when they
  are not rendered as separate `!tools` table rows. This keeps
  `import llm` working both inside generated command modules and in saved
  Python debug artifacts. Explicitly requested generated commands are returned
  as callable `llm.get_tools()` entries, preserving the command-as-tool shape
  used by the original bot's command framework.
- `!help`, `!queued`, and `!new <name>` radio surfaces, gated by the `radio`
  trigger.
- `!history [n]` to report or set the recent context line count used for LLM
  prompts, with per-prompt `maxh=N` overrides. Recent IRC messages are also persisted under
  `.pyylmao.irc.channels."<channel>".history` and `.pyylmao._history` for
  `!kv` inspection and the `get_chat_history` LLM tool.
- Logged golem control commands: `!> clear` / `!clear` clear channel prompt
  history, while `!> key=value` and `!> -key` update persisted golem params.
- `!echo <markdown>` simple markdown echoing, including escaped `\n` expansion
  and block quote rendering with `┃`.
- `!palette99` fixed two-digit IRC color-index grid.
- Stateful per-nick `!todo <task>` lists rendered as `nick's Todos` with
  numbered `●` entries.
- Stateful `!remindme` / `!reminder` / `!reminders` creation, listing, and
  per-message expired reminder alerts.
- Stateful `!vtrade` with `claim`, `buy`, `sell`, `confirm`, currency
  conversion, portfolio views, `*` graph leaderboard, 120 second confirmation
  windows, Yahoo price lookup, and FXRatesAPI currency lookup.
- `!stock <ticker> [days|all]` Yahoo chart lookup rendered as the logged
  terminal-style price graph.
- `!zscore [question]` ANU QRNG-backed coin flip, bit imbalance, p-value, and
  outlook meter, with logged-style URL errors when the QRNG API is unavailable.
- `!fortune [question]` I Ching-style yarrow throw with primary/changing
  hexagrams, line art, interpretation text, and `stalks thrown`.
- `!weather <location>` current conditions using wttr.in and
  `!forecast <location>` seven-day forecasts using Open-Meteo, matching the
  compact current-condition line and forecast table seen in logs.
- `!add`, `!del`, and `!blist` regex filter management for the
  feed-style commands seen in the Bluesky/TCL logs.
- `!img2irc` / `!img2irc2` URL image rendering with width, render, block, and
  basic color-adjustment options. `!hax <url> [width] [options]` is supported
  as the historical alias and is gated by the `imghax` trigger.
- Case-sensitive `!ascii <name>` art lookup with a small built-in seed set and
  optional `.txt` art directory.
- `!summary` / `!wsummary` webpage, PDF, and YouTube transcript summarization
  through OpenRouter.
- `!drink` starts a long-running Bluesky watcher that polls public Bluesky
  search for `!add` regex matches and emits matching posts.

Not yet complete:

- Full Bluesky firehose ingestion; current implementation uses Bluesky AppView
  search polling.
- Full historical `!ascii` art corpus.
- Exact logged `!summary` formatting and YouTube metadata display.
- YouTube live metadata can be limited by YouTube bot checks; title/channel
  fallback still works through oEmbed when full stats are blocked.
- Radio playback/search/queue backends; current implementation mirrors the
  logged help glossary, empty queue response, and local playlist creation only.
- Trigger toggles are applied only to commands that exist in the reconstructed
  command table or generated command store. Logs show missing generated command
  names returning `Trigger <name> does not exist` until the command is present.
- Reminder parsing is deterministic and covers the logged relative and common
  absolute forms; the historical command used an LLM for broader natural
  language parsing.
- Exact historical vTrade, `!stock`, and weather icon-selection fidelity.
- `!zscore` uses local system entropy with the logged QRNG-style output shape,
  not the historical external QRNG API.

## Run

Install project dependencies first so URL image rendering has Pillow available.
Do not put API keys in files. Export one key in the shell:

```bash
python3 -m pip install -e .
export OPENROUTER_API_KEY="..."
export PYYLMAO_SERVER="irc.notgay.men"
export PYYLMAO_PORT="6667"
export PYYLMAO_NICK="pyylmao"
export PYYLMAO_CHANNELS="#not-gay,#tcl"
python3 -m pyylmao
```

Useful optional settings:

- `PYYLMAO_TLS=1` for TLS servers.
- `PYYLMAO_DEFAULT_MODEL=openai/gpt-oss-120b`
- `PYYLMAO_GROK_MODEL=x-ai/grok-4.1-fast`
- `PYYLMAO_STATE=data/pyylmao-state.json`
- `PYYLMAO_ASCII_DIR=data/ascii` for additional `!ascii <name>` `.txt` files.
- `PYYLMAO_CAT_DIR=data/cat` for files served by `!cat <file>`.
- `PYYLMAO_MDCAT_DIR=data/mdcat` for files served by `!mdcat <file>`.
- `PYYLMAO_WWW_DIR=/tmp/pyylmao-www` for generated `!gay` GIFs.
- `PYYLMAO_WWW_BASE_URL` or `PYYLMAO_WWW_BASE_URL_FILE` for the public generated
  image URL prefix. Run `python3 -m pyylmao.image_server` to serve the directory
  and start a quick `cloudflared` tunnel.
- `PYYLMAO_ANU_QRNG_API_KEY` for ANU's current AWS-hosted Quantum Numbers API.
  Without it, `!zscore` tries the historical public QRNG endpoint.
- `PYYLMAO_BSKY_POLL_SECONDS=60`
- `PYYLMAO_BSKY_SEARCH_LIMIT=25`

## Docker

Build and test the same container image used at runtime:

```bash
docker compose build
docker compose run --rm tests
```

Create a local `.env` for IRC and API settings, then run the bot and generated
image tunnel together:

```bash
PYYLMAO_SERVER=irc.notgay.men
PYYLMAO_PORT=6667
PYYLMAO_NICK=pyylmao
PYYLMAO_CHANNELS=#not-gay,#tcl
OPENROUTER_API_KEY=...
```

```bash
docker compose up -d bot image-server
docker compose logs -f image-server
```

The `image-server` service runs `cloudflared` inside Docker and writes the
current public `trycloudflare.com` URL to the shared
`/var/lib/pyylmao/www-base-url` file. The bot reads that file when `!gay`
returns generated GIF URLs. `PYYLMAO_CLOUDFLARED_PROTOCOL` defaults to `http2`
for container-friendly tunnel startup.

## Tests

```bash
python3 -m unittest discover -s tests
```
