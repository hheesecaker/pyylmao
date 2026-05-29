# Agent Handoff: pyylmao

## Project Goal

This repository reconstructs the historical `pyylmao` IRC bot from WeeChat logs stored inside the Incus VM `diverse-deer`. The implementation should match observed user-facing behavior from logs, especially for `!kv` and the LLM tools used to create, inspect, debug, and run generated commands.

Use log evidence as the source of truth. When behavior is uncertain, mine the logs first, then implement the narrowest behavior that moves the reconstruction closer to the observed bot.

## Environment Notes

- Work from `/home/ubuntu/pyylmao`.
- Run the bot and tests in Docker. The user explicitly asked that this whole thing run in Docker.
- This directory is now a git repository on branch `main`, pushed to `https://github.com/hheesecaker/pyylmao.git`. Use normal `git status` / `git diff` locally, but keep secrets out of commits.
- Use `apply_patch` for file edits.
- Historical WeeChat logs are in the Incus VM `diverse-deer` under `/root/.local/share/weechat/logs/*.weechatlog`.
- The live bot runtime is in its own Incus VM, `pyylmao-bot`. Do not run the bot in `diverse-deer`; that VM is the log/WeeChat source.
- `rg` may not be installed inside Incus. Install it first:

```sh
sudo -n incus exec diverse-deer -- sh -lc 'command -v rg >/dev/null 2>&1 || apk add ripgrep >/dev/null; rg -n "pattern" /root/.local/share/weechat/logs/irc.*.weechatlog'
```

## Docker Workflow

Use Docker for verification:

```sh
sudo -n docker compose build
sudo -n docker compose run --rm tests
sudo -n docker compose up -d --force-recreate bot image-server
sudo -n docker compose ps
sudo -n docker compose exec -T image-server sh -lc 'for i in $(seq 1 20); do test -s /var/lib/pyylmao/www-base-url && cat /var/lib/pyylmao/www-base-url && exit 0; sleep 1; done; exit 1'
sudo -n docker compose logs --tail=80 bot image-server
```

After recreating `image-server`, the quick Cloudflared URL changes. The last known live tunnel after the latest work was:

```text
https://followed-lewis-located-faster.trycloudflare.com
```

Do not assume that URL is still current; read `/var/lib/pyylmao/www-base-url` from the container.

## Incus Live Deployment

As of May 28, 2026, `pyylmao` is running inside the separate Alpine Incus VM `pyylmao-bot` from:

```text
/opt/pyylmao-current
```

The live deployment uses Docker Compose project `pyylmao` with this VM-local override:

```text
/opt/pyylmao-current/compose.incus.yml
```

`pyylmao-bot` is an Alpine 3.22 VM. VM-specific setup:

- Docker is installed with `docker-cli-compose`.
- `/etc/docker/daemon.json` uses `storage-driver: vfs`, `bridge: none`, and disables iptables/ip6tables because this Incus VM did not expose overlayfs or nftables support.
- The running VM root filesystem is about 10GiB after `growpart /dev/sda 2` and `resize2fs /dev/sda2`. The Incus root device has been set to 16GiB, but the running VM did not see a larger block device without a restart; avoid rebooting solely for this unless disk pressure makes it necessary, because restarting `image-server` will change the quick Cloudflared URL.
- Runtime and build networking use host networking in the compose override.
- The compose override also sets host networking on the `tests` service build; without that, Docker can fail inside this Incus VM with `network bridge not found` during build layers.
- Persistent runtime state is in Docker volume `pyylmao_pyylmao-data`.
- The old `diverse-deer` Docker containers were stopped after the runtime volume was copied to `pyylmao-bot`.
- Because Docker uses `vfs`, repeated rebuilds can consume VM disk quickly. It is safe to prune stopped test containers and unused image/build cache with `docker container prune -f`, `docker image prune -f`, and `docker builder prune -f`; do not prune volumes. If the VM is tight, stop/remove only the old `bot` container and prune its image before rebuilding, while leaving `image-server` running to preserve the tunnel.
- If the bot restart-loops on `socket.gaierror: [Errno -3] Temporary failure in name resolution`, check `/etc/resolv.conf` in `pyylmao-bot` before debugging bot code. During the latest recreate it was empty; restoring `nameserver 1.1.1.1` and `nameserver 8.8.8.8` fixed DNS and let the bot reconnect.

Useful live-deployment commands:

```sh
sudo -n incus exec pyylmao-bot -- sh -lc 'cd /opt/pyylmao-current && docker compose -p pyylmao -f compose.yml -f compose.incus.yml ps'
sudo -n incus exec pyylmao-bot -- sh -lc 'cd /opt/pyylmao-current && docker compose -p pyylmao -f compose.yml -f compose.incus.yml logs --tail=80 bot image-server'
sudo -n incus exec pyylmao-bot -- sh -lc 'cd /opt/pyylmao-current && docker compose -p pyylmao -f compose.yml -f compose.incus.yml run --rm tests'
sudo -n incus exec pyylmao-bot -- sh -lc 'cd /opt/pyylmao-current && docker compose -p pyylmao -f compose.yml -f compose.incus.yml exec -T image-server cat /var/lib/pyylmao/www-base-url'
```

The bot is configured there for:

```text
server: irc.notgay.men
port: 6667
tls: false
channel: #not-gay
nick: pyylmao_oss
line delay: 0 seconds
```

OpenRouter is configured via the VM-local `/opt/pyylmao-current/.env` in `pyylmao-bot`. Do not print, copy, or commit secrets from that file.

This was verified with an independent IRC client that saw `pyylmao_oss` in `#not-gay` NAMES. Private IRC checks confirmed `ping` returns `p0ng!`, `@gpt respond with exactly OK` returns `OK`, the OpenRouter footer includes colored cents/cumulative-cost formatting, `!reload yolo` reloads, `!yolo` returns a number, and `.random 1 3` runs through the generated callable compatibility path.

After the latest Alpine VM container restart, a fresh independent IRC client check saw `pyylmao_oss` answer private `ping` with `p0ng!`; previous private checks confirmed `!reload backends.sqlite` returned `reloaded:` and `- pyylmao.kv.backends.sqlite`.

## Current Status

The test suite currently passes locally, in Docker, and inside the Alpine `pyylmao-bot` VM:

```text
487 tests passed
```

The repository has been pushed to:

```text
https://github.com/hheesecaker/pyylmao.git
```

The local remote is token-free. GitHub auth was supplied only as a one-shot HTTP header for the initial push; do not store PATs or OpenRouter keys in `.git/config`, remotes, `.env`, AGENTS.md, or committed files.

Recent focused suites also passed:

```text
python3 -m unittest tests.test_llm_tools
python3 -m unittest tests.test_generated_commands
python3 -m unittest tests.test_router tests.test_weather tests.test_link_preview
python3 -m unittest tests.test_generated_commands tests.test_llm_tools tests.test_kvstore
python3 -m unittest tests.test_helpers tests.test_generated_commands tests.test_llm_tools
python3 -m unittest tests.test_generated_commands tests.test_irc tests.test_router
python3 -m unittest tests.test_llm_tools tests.test_generated_commands tests.test_router
python3 -m unittest tests.test_llm_tools tests.test_generated_commands tests.test_llm tests.test_router
python3 -m unittest tests.test_reload_command tests.test_router
python3 -m unittest tests.test_router tests.test_llm
python3 -m unittest tests.test_generated_commands tests.test_llm tests.test_llm_tools
python3 -m unittest tests.test_kvstore tests.test_router
python3 -m unittest tests.test_twitter tests.test_llm_tools tests.test_router
python3 -m unittest tests.test_nostr tests.test_llm_tools tests.test_router
python3 -m unittest tests.test_ansi2irc tests.test_llm_tools tests.test_router
python3 -m unittest tests.test_irc tests.test_llm_tools
python3 -m unittest tests.test_llm_tools tests.test_generated_commands
python3 -m unittest tests.test_router tests.test_llm_tools
python3 -m unittest tests.test_vocoder tests.test_router tests.test_llm_tools
python3 -m unittest tests.test_ligma tests.test_router tests.test_llm_tools
python3 -m unittest tests.test_phenoguessr tests.test_router tests.test_llm_tools
python3 -m unittest tests.test_generated_commands tests.test_llm_tools
python3 -m unittest tests.test_compat_imports tests.test_generated_commands tests.test_llm_tools
python3 -m unittest tests.test_eval_command tests.test_router tests.test_llm_tools
python3 -m unittest tests.test_generated_commands tests.test_llm_tools tests.test_router
python3 -m unittest tests.test_link_preview tests.test_router tests.test_generated_commands tests.test_llm_tools
python3 -m unittest tests.test_link_preview tests.test_router tests.test_llm_tools
python3 -m unittest tests.test_link_preview
python3 -m unittest tests.test_llm_tools tests.test_generated_commands
python3 -m unittest tests.test_irc tests.test_router
python3 -m unittest tests.test_ytsearch tests.test_router tests.test_llm_tools
python3 -m unittest tests.test_generated_commands tests.test_irc
python3 -m unittest tests.test_invite tests.test_router tests.test_llm_tools
python3 -m unittest tests.test_generated_commands tests.test_compat_imports tests.test_irc
python3 -m unittest tests.test_random_command tests.test_router tests.test_llm_tools
python3 -m unittest tests.test_cp tests.test_router tests.test_llm_tools tests.test_generated_commands
python3 -m unittest tests.test_pmall tests.test_llm_tools tests.test_generated_commands
python3 -m unittest tests.test_seen tests.test_router tests.test_llm_tools
python3 -m unittest tests.test_link_preview tests.test_ytsearch
python3 -m unittest tests.test_llm_tools tests.test_router tests.test_generated_commands
python3 -m unittest tests.test_generated_commands tests.test_compat_imports tests.test_llm_tools
python3 -m unittest tests.test_compat_imports tests.test_llm_tools tests.test_generated_commands
```

After the latest historical GPT helper-module compatibility change, focused local tests, the full local suite, Docker tests, and the full suite inside the Alpine `pyylmao-bot` image all passed with 487 tests. This follows log evidence where the original bot exposed or reloaded `pyylmao.commands.gpt.common`, `pyylmao.commands.gpt.billing`, `pyylmao.commands.gpt.mdbuffer`, `llm.models`, and `llm.tools`. The reconstructed package now provides those import paths: `gpt.common` re-exports prompt/model/tool formatting helpers and small `parse_prompt`/`resolve_model` compatibility wrappers, `gpt.billing` exposes cost/cents helpers, `gpt.mdbuffer` exposes an `MDBuffer` markdown-rendering buffer, and `llm.models` / `llm.tools` re-export the generated-command model/tool shims. `read_command gpt.common`, `read_command gpt.tools`, `read_command gpt.billing`, and `read_command mdbuffer` now resolve to source. The live Alpine bot container was rebuilt and recreated without recreating `image-server`; a direct live-container probe confirmed the new imports, wrappers, and `read_command` aliases, and a fresh independent IRC check confirmed `pyylmao_oss` is in `#not-gay` and private `ping -> p0ng!`. The image-server tunnel remained `https://followed-lewis-located-faster.trycloudflare.com` because the service was left running. After pruning stopped containers/unused images/build cache without touching volumes, the Alpine VM root filesystem was about 92% used.

After the latest historical LLM API import compatibility change, focused local tests, the full local suite, Docker tests, and the full suite inside the Alpine `pyylmao-bot` image all passed with 485 tests. This follows log evidence where the original `pyylmao.commands.gpt.__init__` imported helpers from `pyylmao.commands.gpt.tools`, then failed until `read_artifact` / singular `list_artifact` were restored and `!reload gpt.tools` returned `- pyylmao.commands.gpt.tools`. The reconstructed package now exists as `pyylmao.commands.gpt.tools` and exports callable wrappers for the LLM/debug/artifact/history/IRC/skill/memory/search APIs, including `read_command`, `write_command`, `run`, `irc_command`, `save_artifact`, `read_artifact`, `list_artifacts`, `list_artifact`, `get_tools`, and `get_enabled_tools`. Those wrappers bind to the same generated-command runtime state/event/raw-IRC sender exposed through `import llm`, so generated commands can call the historical import path and still operate on the bot's state. Additional logged compatibility surfaces were added: `llm.model(...)` aliases `llm.get_model(...)`, and `from pyylmao.config import _CONFIG` now works. The live Alpine bot container was rebuilt and recreated without recreating `image-server`; a direct live-container generated-command probe confirmed the historical import path, `llm.model`, artifact helpers, enabled tool lookup, and `read_command('ping')`, and a fresh independent IRC check confirmed `pyylmao_oss` is in `#not-gay` and private `ping -> p0ng!`. The image-server tunnel remained `https://followed-lewis-located-faster.trycloudflare.com` because the service was left running. After deployment, the Alpine VM root filesystem was about 92% used because Docker uses `vfs`; stopped containers/images/build cache were pruned without touching volumes before rebuild.

After the latest command-backed LLM tool schema parity change, focused local tests, the full local suite, Docker tests, and the full suite inside the Alpine `pyylmao-bot` image all passed with 483 tests. The OpenRouter registry no longer advertises every row in `COMMANDS` as a callable command tool: it now exposes only reconstructed synchronous commands that the router command runner can actually execute, while leaving async/image preview/source-only surfaces such as `drink`, `img2irc`, `imgcap`, `youtube`, `radio`, and the postponed `anagram` out of direct tool schemas. Enabled generated commands are still exposed as before. `read_command` source parity was tightened for newly exposed command-tool names such as `bwatchadd`, `bwatchdel`, `bwatchlist`, `chess`, `clearhistory`, `curl2`, `llm_alias`, `palette99`, and `ping`, and command-tool dispatch now synthesizes the original trigger shapes for non-obvious commands such as `bwatchadd -> !add`, `bwatchlist -> !blist`, `cmdlist -> !cmds`, `chkdomain -> ?domain`, `howsblair -> !blair`, `llm_alias -> !alias`, and bare poll `vote`. The live Alpine bot container was rebuilt and recreated without recreating `image-server`; direct live-container checks confirmed `cows` and `cmdlist` are exposed while `imgcap` and `youtube` are not, `cows` executes through the command runner, and `imgcap` returns `Unknown tool: imgcap` as a direct tool. A fresh independent IRC check confirmed `pyylmao_oss` is in `#not-gay` and private `ping -> p0ng!`. The image-server tunnel remained `https://followed-lewis-located-faster.trycloudflare.com` because the service was left running. After pruning stopped containers/unused images/build cache without touching volumes and rebuilding the bot image, the Alpine VM root filesystem was about 92% used.

After the latest YouTube raw IRC formatting/date fallback parity change, focused local tests, the full local suite, Docker tests, and the full suite inside the Alpine `pyylmao-bot` image all passed with 482 tests. A public IRC probe against the original `pyylmao` on `irc.gangnet.org #tclmafia` captured the exact raw YouTube preview control-code layout: logo `\x030,4 ▶ \x0f`, title/channel inside `\x031,15 ... \x0f`, duration as `\x031,15[00:03:34]\x0f`, counts with only the numeric part bold such as `\x031,15 \x021777.3M\x02 views \x03`, likes ending with reset, and the date as a bold island `\x031,15 \x02Oct 25, 2009\x02\x0f`. `pyylmao/link_preview.py` now renders that layout instead of the previous approximation that left the title uncolored, bolded whole count labels, and left dates non-bold. The web fallback also inspects `ytInitialPlayerResponse` and HTML metadata for dates/durations when `yt-dlp`/player extraction is partial, while `videoDescriptionHeaderRenderer` still supplies Shorts dates such as `May 02, 2026`. The live Alpine bot container was rebuilt and recreated without recreating `image-server`; direct live-container checks confirmed the raw renderer and a live Shorts fetch with `May 02, 2026`, and a fresh independent private IRC check confirmed `pyylmao_oss` is in `#not-gay`, `ping -> p0ng!`, and a private `dQw4w9WgXcQ` preview arrived with the original color/reset layout and bold `Oct 25, 2009` date. The image-server tunnel remained `https://followed-lewis-located-faster.trycloudflare.com` because the service was left running. After deployment, the Alpine VM root filesystem was about 92% used because Docker uses `vfs`; stopped containers/images/build cache were pruned without touching volumes before rebuild.

After the latest `seen` generated-command/API parity change, focused local tests, the full local suite, Docker tests, and the full suite inside the Alpine `pyylmao-bot` image all passed with 482 tests. This follows original `irc.supernets.#superbowl` logs where `seen` was created through `write_command` with pattern `^!seen (.+)$`, debugged with `read_command seen`, used `from pyylmao.kv.backends.sqlite import kv_get`, returned `malcom was last seen pon 2025-12-23 08:44:03 UTC saying: !seen malcom`, and later returned `User ryan not found in history.` when no channel-history entry existed. `pyylmao/seen.py` reconstructs the source/API surface, `read_command seen` resolves, `!seen <nick>` searches KV-backed channel history with both historical `nick` and current `nickname` keys, preserves the logged `pon` typo and missing-user wording, and treats `!seen <sender>` as the current line to match the logged self-query behavior. The command-backed LLM tool runner now passes `LLMToolContext.target` into reconstructed command dispatch instead of always using `_sync`, so channel-sensitive command tools such as `seen` operate on the model's active channel. The live Alpine bot container was rebuilt and recreated without recreating `image-server`; direct live-container checks confirmed `read_command seen` and rendered history output, and a fresh independent private IRC check confirmed `ping -> p0ng!` plus live `!seen <client-nick>` output. The image-server tunnel remained `https://followed-lewis-located-faster.trycloudflare.com` because the service was left running. After deployment, the Alpine VM root filesystem was about 92% used because Docker uses `vfs`; stopped containers/images/build cache were pruned without touching volumes before rebuild.

After the latest `pmall` source/debug parity change, focused local tests, the full local suite, Docker tests, and the full suite inside the Alpine `pyylmao-bot` image all passed with 478 tests. This follows the live `irc.notgay.#not-gay` generated-command/debug flow where `pmall` used the standard `class Tool(llm.Toolbox)` API, `event.target`, `connection.get_nickname()`, `connection.privmsg(...)`, and `pyylmao.history_store.channel_users(...)` to private-message every channel user except the bot and sender. Clean-state `read_command pmall` now resolves to reconstructed source containing `class Tool(llm.Toolbox)`, `_onload`, `channel_users`, and `connection.privmsg`, while runtime tests verify a pmall-style generated command sends `PRIVMSG bob :[alice] smoke` and prints `PM sent to 1 users`. The live Alpine bot container was rebuilt and recreated without recreating `image-server`; direct live-container checks confirmed both live-state and clean-state `read_command pmall`, and a fresh independent IRC check confirmed private `ping -> p0ng!`. The image-server tunnel remained `https://followed-lewis-located-faster.trycloudflare.com` because the service was left running. After deployment, the Alpine VM root filesystem was about 92% used because Docker uses `vfs`; stopped containers/images/build cache were pruned without touching volumes before rebuild.

After the latest `cp` generated-command parity change, focused local tests, the full local suite, Docker tests, and the full suite inside the Alpine `pyylmao-bot` image all passed with 476 tests. This follows the live `irc.notgay.#not-gay` flow where a generated command named `cp` was created with pattern `^tcl cp (.+)$`, repeatedly inspected with `read_command cp`, changed to print md2irc output instead of returning it, and finally rendered the logged table shape for `tcl cp btc eth` (`Ticker 🭍 Price (USD)`, BTC/ETH rows, and the md2irc table footer). `pyylmao/cp.py` reconstructs that command with CoinGecko `simple/price`, common ticker aliases, md2irc table rendering, unknown-ticker reporting, `read_command cp`, trigger-gated router dispatch, and command-tool dispatch through `run`/direct LLM command tools as `cp -> tcl cp`. The same work also maps log-observed LLM debug probes `read_command convo` and `read_command @@` to the router source so models can inspect the conversation/LLM trigger implementation instead of getting a false missing-command result. The live Alpine bot container was rebuilt and recreated without recreating `image-server`; direct live-container checks confirmed `read_command cp`, `read_command convo`, `read_command @@`, enabled `cp` state, and a live `tcl cp btc eth` render with BTC/ETH prices, and a fresh independent IRC check confirmed private `ping -> p0ng!`. The image-server tunnel remained `https://followed-lewis-located-faster.trycloudflare.com` because the service was left running. After deployment, the Alpine VM root filesystem was again about 92% used because Docker uses `vfs`; stopped containers/images/build cache were pruned without touching volumes before rebuild.

After the latest `random` generated-command parity change, focused local tests, the full local suite, Docker tests, and the full suite inside the Alpine `pyylmao-bot` image all passed with 472 tests. This follows the live `irc.gangnet.#tclmafia` log flow where `random` was created, rewritten to the final pattern `^\.random\s*(.*)$`, inspected with `read_command random`, and then used as evidence that standard generated-command APIs needed to work. `pyylmao/random_command.py` reconstructs the final generated artifact shape: `read_command random` resolves, `.random` returns `Random number: <n>` for 1..100, `.random 50` returns `Random number between 1 and 50: <n>`, `.random 1 3` returns `Random number between 1 and 3: <n>`, and final rough edges such as `.random 10-20 -> Error: Please provide valid numbers` are preserved. The command table exposes `random True ^\.random\s*(.*)$`, router handling is trigger-gated, and command-tool dispatch maps `random` to `.random`. The live Alpine bot container was rebuilt and recreated without recreating `image-server`; direct live-container checks confirmed `read_command random`, enabled trigger state, and `.random 1 3` routing, and a fresh independent IRC check confirmed private `ping -> p0ng!`. The image-server tunnel remained `https://followed-lewis-located-faster.trycloudflare.com` because the service was left running. After deployment, the Alpine VM root filesystem was again about 92% used because Docker uses `vfs`; stopped containers/images/build cache were pruned without touching volumes before rebuild.

After the latest `invite` generated-command parity change, focused local tests, the full local suite, Docker tests, and the full suite inside the Alpine `pyylmao-bot` image all passed with 469 tests. This follows original `irc.supernets.#bowlcut` logs where a generated command named `invite` had pattern `^!invite (\S+) (\S+)$`, appeared in `!cmds` as `invite False`, and eventually settled on the final logged API `from pyylmao.ircbot import bot` plus `bot.connection.invite(nick, channel)` after earlier `irc_command` and `from tools import irc_command` attempts failed. `pyylmao/invite.py` reconstructs the final behavior: `read_command invite` resolves to source containing the `pyylmao.ircbot` import, the trigger is disabled by default, disabled `!invite ...` routing is quiet, and when enabled it sends raw `INVITE <nick> :<channel>` and returns `Invited <nick> to <channel>`. The live Alpine bot container was rebuilt and recreated without recreating `image-server`; direct live-container checks confirmed `read_command invite`, default disabled state, and quiet disabled routing with no raw IRC sent, and a fresh independent IRC check confirmed private `ping -> p0ng!`. The image-server tunnel remained `https://followed-lewis-located-faster.trycloudflare.com` because the service was left running. After deployment, the Alpine VM root filesystem was again about 92% used because Docker uses `vfs`; unused containers/images/build cache were pruned without touching volumes, but the active rebuilt image still consumes most remaining space.

After the latest `ytsearch` read/command-surface parity change, focused local tests, the full local suite, Docker tests, and the full suite inside the Alpine `pyylmao-bot` image all passed with 467 tests. This follows original `irc.supernets.#bowlcut` logs where a generated command named `ytsearch` was repeatedly inspected with `read_command ytsearch`, appeared in `!cmds` as `ytsearch False ^!yt (.+)$`, and rendered YouTube API search results as two lines per result with YouTube-style `▶` output, duration, views, likes, published date, description, and `youtu.be` URL. `pyylmao/ytsearch.py` reconstructs that command using `YOUTUBE_API_KEY` when enabled; it is intentionally disabled by default through the command table default so live `!yt ...` does not spam unless explicitly enabled. `read_command ytsearch` resolves to source, `!enable ytsearch` enables the trigger, and the router gates `!yt` on that trigger. The live Alpine bot container was rebuilt and recreated without recreating `image-server`; direct live-container checks confirmed `read_command ytsearch`, default `ytsearch` disabled state, and quiet disabled `!yt` routing, and a fresh independent IRC check confirmed private `ping -> p0ng!`. The image-server tunnel remained `https://followed-lewis-located-faster.trycloudflare.com` because the service was left running. During VM deployment, building both `bot` and `tests` simultaneously hit Docker `vfs` disk pressure; pruning unused build cache/layers and building only the single shared `bot` image avoided duplicate export. Volumes were not pruned. After deployment, the Alpine VM root filesystem was about 92% used.

After the latest LLM/generated-command user-list API parity change, focused local tests, the full local suite, Docker tests, and the full suite inside the Alpine `pyylmao-bot` image all passed with 465 tests. This follows the live `pmall` debug flow where the model tried `read_command userlist`, `read_command names`, and `read_command users`, then had to grep/cat `history_store.py` to discover `channel_users()`: those three `read_command` aliases now resolve directly to the channel-history source. Class-based generated commands also now receive `channel=event.channel or event.target` plus explicit `target=event.target`, so private-message/direct target contexts get the same non-empty target that legacy generated entrypoints already received. The live Alpine bot container was rebuilt and recreated without recreating `image-server`; direct live-container checks confirmed `read_command userlist`, `names`, and `users` expose `def channel_users`, and a fresh independent IRC check confirmed private `ping -> p0ng!`. The image-server tunnel remained `https://followed-lewis-located-faster.trycloudflare.com` because the service was left running. During VM deployment, Docker `vfs` again hit `no space left on device`; the old bot container plus stopped containers/unused images/build cache were pruned without touching volumes, then tests and bot recreation succeeded. After deployment, the Alpine VM root filesystem was about 92% used.

After the latest YouTube partial-metadata/date fallback and IRC color separator parity change, focused local tests, the full local suite, Docker tests, and the full suite inside the Alpine `pyylmao-bot` image all passed with 464 tests. YouTube preview fetching no longer stops at a partial `yt-dlp` result or title-only oEmbed result: it merges available metadata from `yt-dlp`, the YouTube player endpoint, YouTube web `ytInitialData` / `videoDescriptionHeaderRenderer`, and oEmbed/Return YouTube Dislike. This fixes current live cases where `pyylmao_oss` only emitted title/channel or title plus stats while the original `pyylmao`/`pyylmeaux` emitted trailing dates, e.g. `The Voice Actors In Your Headphones | String and Tell  [00:01:00]  1.5M views   69K likes   May 02, 2026` in logs. The web fallback parses absolute page dates such as `May 2, 2026`, day-first dates such as `2 May 2026`, and short-lived relative strings such as `Premiered 15 hours ago`; it also extracts views/likes from header factoids when available. Stats-only output now inserts an uncolored separator between grey islands, so raw IRC has separate color islands such as `\x031,15 \x021.5M views\x02 \x03 \x031,15 \x0269K likes\x02 \x03 \x031,15 May 02, 2026 \x03` instead of adjacent color resets. The live Alpine bot container was rebuilt and recreated without recreating `image-server`; direct live-container checks confirmed the recent `RJbIE7ITDqc`, `uhteFgfVxvo`, and `QrLQXIb8jfA` URLs now include dates, and a fresh independent IRC check confirmed private `ping -> p0ng!` plus a private Shorts URL response with colored stats islands and `May 02, 2026`. The image-server tunnel remained `https://followed-lewis-located-faster.trycloudflare.com` because the service was left running. After deployment, the old bot container/image and unused build cache were pruned without touching volumes; the Alpine VM root filesystem was about 86% used.

After the latest `write_command` generated-command load-check parity change, focused local tests, the full local suite, Docker tests, and the full suite inside the Alpine `pyylmao-bot` image all passed with 461 tests. `write_command` still writes the target command and surfaces target import stdout/stderr, but now also load-checks the generated command set and reports stale broken generated modules as logged, e.g. `Skipping command elliotsearch due to load error: ModuleNotFoundError("No module named 'pymupdf'")` after a successful `livebench` write. This matches log evidence where writing unrelated commands sometimes exposed an existing generated-command load failure. The live Alpine bot container was rebuilt and recreated without recreating `image-server`; direct live-container checks confirmed the stale-load-error output shape, and a fresh independent IRC check confirmed `pyylmao_oss` is in `#not-gay` and private `ping` returns `p0ng!`. The image-server tunnel remained `https://followed-lewis-located-faster.trycloudflare.com` because the service was left running. After deployment, unused Docker image/build cache was pruned without touching volumes and the Alpine VM root filesystem was about 84% used.

After the latest YouTube date and IRC color island parity change, focused local tests, the full local suite, Docker tests, and the full suite inside the Alpine `pyylmao-bot` image all passed with 461 tests. YouTube previews now fetch upload dates through the YouTube player metadata fallback when `yt-dlp` is blocked, then enrich with oEmbed/Return YouTube Dislike data as needed. The raw IRC output wraps the visible padding in the metadata background color, matching the logged correction: logo `\x030,4 ▶ \x03`, bold duration/views/likes islands such as `\x031,15 \x02[01:00:41]\x02 \x03`, and a non-bold date island such as `\x031,15 Apr 03, 2026 \x03`. Stripping IRC codes leaves the logged visible shape, e.g. `▶   The Sam Hyde Show: Looksmaxxing feat. Androgenic | Sam Hyde  [01:00:41]  59K views   4K likes   Apr 03, 2026 `. The live Alpine bot container was rebuilt and recreated without recreating `image-server`; direct live-container checks confirmed the padded raw renderer and a live `dQw4w9WgXcQ` fetch returned `Oct 25, 2009`, and a fresh independent IRC check confirmed `pyylmao_oss` is in `#not-gay`, private `ping` returns `p0ng!`, and a private YouTube URL response arrived over IRC with the padded color bytes and date. The image-server tunnel remained `https://followed-lewis-located-faster.trycloudflare.com` because the service was left running. After deployment, unused Docker image/build cache was pruned without touching volumes and the Alpine VM root filesystem was about 84% used.

After the latest generated-command channel/user compatibility and YouTube preview shape parity change, focused local tests, the full local suite, Docker tests, and the full suite inside the Alpine `pyylmao-bot` image all passed with 460 tests. Class-based generated commands now receive a `connection.channels` map and `connection.reactor.channels` alias populated from persisted `pyylmao.irc.channels.<channel>.users` state; `Channel` exposes python-irc-style helpers such as `users()`, `has_user()`, `opers()`, `voiced()`, `add_user()`, `remove_user()`, and `change_nick()`, preserving mode prefixes from stored user metadata. This covers `pmall`-style generated commands that inspect channel membership and send private messages through the injected connection. YouTube previews now render the final logged output shape with the upload date as the last island, e.g. ` ▶   The Sam Hyde Show: Looksmaxxing feat. Androgenic | Sam Hyde  [01:00:41]  59K views   4K likes   Apr 03, 2026`; `yt-dlp` upload/release/timestamp metadata is normalized to `Mon DD, YYYY`, `yt-dlp` bot-check errors are quieted, `PYYLMAO_YOUTUBE_COOKIES` can point at a cookies file, and the anonymous fallback still uses YouTube oEmbed title/channel metadata with Return YouTube Dislike counts when full extraction is blocked. The live Alpine bot container was rebuilt and recreated without recreating `image-server`; direct live-container checks confirmed the date-island renderer and `connection.channels` helpers, and a fresh independent IRC check confirmed `pyylmao_oss` is in `#not-gay` and private `ping` returns `p0ng!`. The image-server tunnel remained `https://followed-lewis-located-faster.trycloudflare.com` because the service was left running. To work around Docker `vfs` disk pressure, the old bot container/image was stopped and pruned before rebuilding; volumes were not pruned, and the Alpine VM root filesystem was about 84% used after deployment.

After the latest generated-command script fallback compatibility change, focused local tests, the full local suite, Docker tests, and the full suite inside the Alpine `pyylmao-bot` image all passed with 457 tests. This closes the current live `write_command` failure mode where script-style artifacts such as `ching_chong.py` were accepted but later returned `generated command ching_chong has no entrypoint`: generated commands now still prefer `llm.Toolbox`, `entrypoint`, `run`, `command`, and `<name>_command`, but fall back to `main()` and clearly script-like files such as shebang/top-level-print artifacts when no standard callable exists. `MessageEvent.type` now aliases `event_type` for additional python-irc-style compatibility. The live Alpine bot container was rebuilt and recreated without recreating `image-server`; a direct live-container check confirmed the persisted `!ching_chong` artifact now returns a generated line instead of the no-entrypoint error, and a fresh independent IRC check confirmed `pyylmao_oss` is in `#not-gay`, private `ping` returns `p0ng!`, and private `!ching_chong` responds. The image-server tunnel remained `https://followed-lewis-located-faster.trycloudflare.com` because the service was left running. After deployment, unused Docker image/build cache was pruned without touching volumes and the Alpine VM root filesystem was back to about 70% used.

After the latest command-as-tool API parity change, focused local tests, the full local suite, Docker tests, and the full suite inside the Alpine `pyylmao-bot` image all passed with 455 tests. This follows the live log discussion that pyylmao's command structure exists so commands can also be used as tools. The OpenRouter tool registry now exposes command-backed tools directly by command name when a router command runner is available: reconstructed commands such as `define` and generated commands accept an `args` string and dispatch through the same generated/reconstructed path as `run cmd_name=...`. The generated-command `llm.get_tools()` shim now also returns explicitly requested generated commands as callable entries, so generated code can use shapes like `llm.get_tools(["toolsmoke"])["toolsmoke"](args="inner")`. The live Alpine bot container was rebuilt and recreated without recreating `image-server`; a direct live-container smoke check confirmed direct `define`, direct generated command, and in-command callable `llm.get_tools()` execution, and a fresh independent IRC check confirmed `pyylmao_oss` is in `#not-gay` and returns `p0ng!` to private `ping`. The image-server tunnel remained `https://followed-lewis-located-faster.trycloudflare.com` because the service was left running.

After the latest generated-command regex parity change, focused local tests, the full local suite, Docker tests, and the full suite inside the Alpine `pyylmao-bot` image all passed with 451 tests. `GeneratedCommandStore` now uses regex search semantics for both legacy generated command patterns and `llm.Toolbox.pattern`, matching log evidence where the generated `eval` command's unanchored pattern `(?i)\beval\b\s*(.*)` fired inside a longer ordinary message (`... eval 1+2+3`). This is a `write_command`/runtime parity fix: generated commands with anchored patterns behave the same, while unanchored generated patterns now match the original pyylmao behavior. The live Alpine bot container was rebuilt and recreated without recreating `image-server`; a direct live-container smoke check confirmed an unanchored generated regex fires mid-line, and a fresh independent IRC check confirmed `pyylmao_oss` is in `#not-gay` and returns `p0ng!` to private `ping`. The image-server tunnel remained `https://followed-lewis-located-faster.trycloudflare.com` because the service was left running.

After the latest log-created `eval` debug command parity change, focused local tests, the full local suite, Docker tests, and the full suite inside the Alpine `pyylmao-bot` image all passed with 449 tests. `pyylmao/eval_command.py` reconstructs the generated command created in `irc.supernets.#bowlcut.weechatlog` with pattern `(?i)\beval\b\s*(.*)`: it evaluates the captured Python expression, emits stdout before the result, exposes the logged generated-command globals (`channel`, `nickname`, `username`, `hostname`, `args`, `pattern`, `entrypoint`), recreates globals for each invocation, and preserves persistent `__builtins__` mutations. `read_command eval` resolves to this source. The Incus compose override now also sets host networking for the `tests` service build after an Alpine VM build hit Docker's `network bridge not found` path. The live Alpine bot container was rebuilt and recreated without recreating `image-server`; direct live-container checks confirmed `read_command eval` and logged examples such as `eval "LIVE"`, unanchored `... eval 1+2+3`, and `eval args`, and a fresh independent IRC check confirmed `pyylmao_oss` is in `#not-gay` and returns `p0ng!` to private `ping`. The image-server tunnel remained `https://followed-lewis-located-faster.trycloudflare.com` because the service was left running.

After the latest expanded python-irc/raw IRC compatibility change, focused local tests, the full local suite, Docker tests, and the full suite inside the Alpine `pyylmao-bot` image all passed with 443 tests. This follows log evidence where generated/debug code used `event.args`, `event.source.nick`, `connection.add_global_handler`, and the original `irc.client.ServerConnection` surface (`action`, `ctcp_reply`, `privmsg_many`, `ping`, `send_items`, etc.). `MessageEvent.args` now aliases `arguments`, `irc.client.Event` parses `nick!user@host` into a source object, and both injected generated-command connections and `pyylmao.ircbot.bot.connection` expose the broader raw IRC helper set. The live Alpine bot container was rebuilt and recreated without recreating `image-server`; a direct live-container check confirmed the new event/connection helpers, and a fresh independent IRC check confirmed `pyylmao_oss` is in `#not-gay` and returns `p0ng!` to private `ping`. The image-server tunnel remained `https://followed-lewis-located-faster.trycloudflare.com` because the service was left running.

After the latest python-irc compatibility shim change, focused local tests, the full local suite, Docker tests, and the full suite inside the Alpine `pyylmao-bot` image all passed with 441 tests. This closes the live log-backed generated-command debug failure `ModuleNotFoundError: No module named 'irc'`: top-level `import irc.bot`, `import irc.client`, `import irc.strings`, and `from irclib import client` now work. The shim exposes `irc.client.Reactor`, `irc.client.ServerConnection`, `irc.bot.SingleServerIRCBot`, `irc.bot.Channel`, `irc.strings.lower`, and `irc.strings.IRCFoldedCase`, and forwards raw IRC methods through the same live raw sender used by `pyylmao.ircbot`. The live Alpine bot container was rebuilt and recreated without recreating `image-server`; direct live-container checks confirmed the imports and python-irc helpers, and a fresh independent IRC check confirmed `pyylmao_oss` is in `#not-gay` and returns `p0ng!` to private `ping`. The image-server tunnel remained `https://followed-lewis-located-faster.trycloudflare.com` because the service was left running.

After the latest generated-command API compatibility change, focused local tests, the full local suite, Docker tests, and the full suite inside the Alpine `pyylmao-bot` image all passed with 439 tests. This fixed the live log-backed failure where a generated command hit `Error: 'ConnectionProxy' object has no attribute 'reactor'`: injected class-based command connections now expose `get_nickname()`, `get_server_name()`, `is_connected()`, and a small python-irc-style `reactor` shim with `server()`, `connections`, no-op processing methods, and `disconnect_all()`. Direct `run cmd_name=...` now executes class-only `llm.Toolbox` generated commands when no legacy `entrypoint`/`run`/`command` callable exists, so the standard class API can be tested without adding a duplicate legacy entrypoint. The live Alpine bot container was rebuilt and recreated without recreating `image-server`; a direct live-container check confirmed `ConnectionProxy().get_nickname()` returns `pyylmao_oss`, `connection.reactor.server() is connection`, and class-only `run` output, and a fresh independent IRC check confirmed `pyylmao_oss` is in `#not-gay` and returns `p0ng!` to private `ping`. The image-server tunnel remained `https://followed-lewis-located-faster.trycloudflare.com` because the service was left running.

After the latest `phenoguessr` generated-command parity change, focused local tests, the full local suite, Docker tests, and the full suite inside the Alpine `pyylmao-bot` image all passed with 437 tests. `pyylmao/phenoguessr.py` reconstructs the generated `phenoguessr` / `!pheno` command: `read_command phenoguessr` and `read_command pheno` resolve to source, `!pheno` starts a game, state/settings live under `commands.phenoguessr`, `output_mode`/`img2irc_args` drive image rendering while missing historical assets are tolerated, and guesses preserve the logged no-active-game, unresolved-location, incorrect, `BULLSEYE`, and `Technically correct!` response shapes. The live Alpine bot container was rebuilt and recreated without recreating `image-server`; a direct live-container check confirmed `read_command pheno` and a temporary `!pheno` flow, and a fresh independent IRC check confirmed `pyylmao_oss` is in `#not-gay` and returns `p0ng!` to private `ping`. The image-server tunnel remained `https://followed-lewis-located-faster.trycloudflare.com` after this work because the service was left running.

After the latest `ligma` generated-command parity change, focused local tests, the full local suite, Docker tests, and the full suite inside the Alpine `pyylmao-bot` image all passed with 431 tests. `pyylmao/ligma.py` reconstructs the generated `ligma` command: `read_command ligma` resolves to source, posted `ligma.pro/@user/<status-id> [all]` URLs trigger the final logged regex, `/api/v1/statuses/<id>` is rendered with optional img2irc avatar lines, Mastodon display/acct/date, wrapped status text, and `💬/♻️/❤️` stats, and trailing `all` fetches `/context` replies indented under the main post. Live local and live-container fetches of `https://ligma.pro/@r000t/115453354808572799` returned the logged Nietzschean Ekko Enjoyer text and stats. The live Alpine bot container was rebuilt and recreated without recreating `image-server`; a direct live-container check confirmed `read_command ligma` and live status rendering. A fresh independent IRC check confirmed private `ping` still returns `p0ng!`. The image-server tunnel remained `https://followed-lewis-located-faster.trycloudflare.com` after this work because the service was left running.

After the latest `vocoder` generated-command parity change, focused local tests, the full local suite, Docker tests, and the full suite inside the Alpine `pyylmao-bot` image all passed with 425 tests. `pyylmao/vocoder.py` reconstructs the generated non-AI speech-synthesis command: `read_command vocoder` resolves to source, `!vocoder <text>` writes a mono WAV under the served web directory and returns the later logged URL shape `<base>/2/<12hex>.wav`, and the early legacy form `vocoder <filename.wav> <text>` still preserves the requested filename. It uses dependency-free standard-library synthesis rather than external TTS. The live Alpine bot container was rebuilt and recreated without recreating `image-server`; a direct live-container check confirmed `read_command vocoder`, final `!vocoder` URL/file creation, and legacy filename output. A fresh independent IRC check confirmed private `ping` still returns `p0ng!`. The image-server tunnel remained `https://followed-lewis-located-faster.trycloudflare.com` after this work because the service was left running.

After the latest `trivia` generated-command parity change, focused router/tool tests, the full local suite, Docker tests, and the full suite inside the Alpine `pyylmao-bot` image all passed with 419 tests. `pyylmao/trivia.py` now reconstructs the high-frequency generated `trivia` command from the logs: `read_command trivia` resolves to source, router handling covers `!trivia categories`, category/difficulty/threshold/mode settings, bare `!trivia`, `rephrase`, silent wrong guesses, correct-answer auto-advance, and KV state/stats under `commands.trivia.state.<channel_key>` with `_not-gay`-style keys. It reads final local CSV categories from `assets/trivia/categories/*.csv` when present and uses a small fallback set only when the historical CSV assets are absent. The live Alpine bot container was rebuilt and recreated without recreating `image-server`; a direct live-container check confirmed `read_command trivia` resolves and the Mount Rainier/Washington trivia flow updates `commands.trivia.state._not-gay`. A fresh independent IRC check confirmed private `ping` still returns `p0ng!`. The image-server tunnel remained `https://followed-lewis-located-faster.trycloudflare.com` after this work because the service was left running.

After the latest `poll`/`vote` generated-command parity change, focused tests, the full local suite, Docker tests, and the full suite inside the Alpine `pyylmao-bot` image all passed with 417 tests. The live Alpine bot container was rebuilt and recreated without recreating `image-server`; a direct live-container check confirmed `read_command poll` and `read_command votes` resolve to reconstructed source and that `!poll Favorite? A. Pizza B. Tacos`, bare `B`, and `!poll stop` produce the expected poll lifecycle lines. A fresh independent IRC check confirmed private `ping` still returns `p0ng!`. The image-server tunnel remained `https://followed-lewis-located-faster.trycloudflare.com` after this work because the service was left running.

After the latest `imgcap` source/debug parity change, focused tests, the full local suite, Docker tests, and the full suite inside the Alpine `pyylmao-bot` image all passed with 415 tests. The live Alpine bot container was rebuilt and recreated without recreating `image-server`; a direct live-container check confirmed `read_command imgcap` returns source containing the logged URL regex, `pyylmao.kv` imports, and `llm.Attachment`, and an independent IRC client confirmed private `ping` still returns `p0ng!`. The image-server tunnel remained `https://followed-lewis-located-faster.trycloudflare.com` after this work because the service was left running.

After the latest LLM tool schema compatibility change, the full suite passed locally, in Docker, and inside the `pyylmao-bot` Docker image with 415 tests. The schema now advertises logged optional-argument debug calls that runtime already supported: `read_command args: {}` lists command inventory, and code-only `write_command` calls can infer the command name from `pattern`. The live Alpine bot container was rebuilt and recreated; a direct live-container check confirmed `read_command` and `write_command` both expose empty required-argument lists and the `write_command` description includes `name is optional`, and a fresh independent IRC check confirmed `pyylmao_oss` returns `p0ng!` to private `ping`. Previous live work confirmed the digit-leading generated-command compatibility change in Docker and inside the `pyylmao-bot` image with 415 tests: logged `read_command 3daudio` / `revise_pattern 3daudio` artifact-debug flows allow generated command files/state keys such as `3daudio.py` while preserving the public name `3daudio`; a direct live-container check confirmed the running bot image sanitizes `3daudio.py` to `3daudio`. `image-server` was left running to preserve the tunnel. Previous checks confirmed `!kv query to_entries[] | ...` renders a `root` tree with top-level `key`/`value` entries. Previous checks confirmed the OpenRouter tool loop uses the logged 32-call chain limit and emits the logged max-time cancellation traces (`max_time reached: <now> <started> 600` plus `Tool calls cancelled: max_time 600s reached`) when a tool call is requested after 600 seconds. Previous checks confirmed the empty `!kill all` rough edge passed locally, in Docker, and inside the `pyylmao-bot` Docker image. A direct live-container check confirmed the no-running-commands case returns `Killed all running commands: ` with nothing after the colon, matching historical pyylmao logs. Previous checks confirmed persisted channel history still returns plain history text to the model while the visible trace says `read 2 lines from chat history`, matching the newer log shape; synthetic `NAMES` input populates `get_channel_users` in server order (`pyylmao_oss`, then mode-stripped names), and the real live `#not-gay` state had 20 users with `pyylmao_oss` present after reconnect; bare `!kv json commands.urban` returns `unknown error, op=json args=['json', 'commands.urban', '']`, matching log evidence where bare `json` is an unsupported action while `+json` remains the supported flag form; `semantic_search` preserves the logged `Profile: news` trace instead of collapsing it to `balanced`; `write_command` can infer a generated command name from a clear regex trigger such as `^!vmcheck$`; private `!cancel` toggles `Tool cancellation flag is ON` then `OFF`; common raw IRC commands format as logged-friendly traces such as `Joined #not-gay` and `Message sent to cj`; `read_command ansi2irc` resolves to reconstructed source; and `!ansi2irc` detects CP437 input from a live 16colo.rs ANSI file, strips trailing SAUCE metadata, and preserves the `FIRE 2026 ANSI CALENDAR` footer. Previous checks confirmed `read_command nostr` resolves to reconstructed source, the logged `nevent` reference parses to a kind-1 event, and a real relay fetch from inside the Docker image returns `weev @weev Apr 19 2026`; `read_command twitter` resolves to reconstructed source, Twitter/X status URL parsing works, raw tweet JSON writes to the runtime fallback path, `read_command` and `run` work against a temporary generated command stored in the historical package layout `<generated_dir>/<name>/__init__.py`, private `!kv query .commands.trivia.state._not-gay|keys` returned the logged `gay/0 is not defined` jq compile error, private `!kv query .cfg|keys` returned `query error: ValueError('null (null) has no keys')`, private `!kv query "ok"` returned the logged literal `root` value tree shape, private `!kv query .commands.gpt._default.system[-2:]` returned the logged sliced `root` tree shape, and a direct container check confirmed the invalid dotted slice `.commands.gpt._default.system.[-2:]` returns the logged jq-style syntax error. Previous private checks confirmed `import llm; llm.get_tools(["save_artifact", "read_artifact", "list_artifacts"])` returns all three artifact helpers with `llm_artifact_tools` and `enabled=True`, `semantic_search` returns `Profile: instant` plus web results for `example domain`, `read_command kv_get` resolves to backend source, top-level `import llm; llm.get_tools()` works, `!enable urban -> Trigger urban does not exist` plus duplicate explicit enable errors, `!kv update man my` returns `unknown error, op=update args=['update', 'man', 'my']`, and `@gpt maxh=0 temperature=0 respond with exactly LIVEOPT` returned `LIVEOPT`:

```text
Ran 415 tests in 0.407s
OK
```

## Implemented / Important Behavior

### Command Toggles / `!cmds`

`!enable <trigger>` and `!disable <trigger>` now validate the target against the reconstructed command table plus generated commands present in state or as `<generated_dir>/<name>.py` files. This matches log evidence such as unknown generated commands returning `Trigger <name> does not exist` before a command exists, followed by `Trigger <name> is now enabled` once the command is present.

Unknown trigger names return:

```text
Trigger <name> does not exist
```

Enabling a command that has already been explicitly enabled returns:

```text
Error: Command '<name>' is already enabled.
```

Do not treat user-facing command spellings as toggle names unless logs show it. For example, `!enable urban` returned `Trigger urban does not exist`, while `!enable urbandict` returned `Trigger urbandict is now enabled`; the `!urban`/`!ud` command itself is still gated by the `urbandict` trigger.

### `!kv`

`pyylmao/kvstore.py` implements the observed command surface:

- `!kv get`, `set`, `query`, `append`, `del`, `info`, `modes`
- JSON/raw/stats flags
- bare `!kv json path` intentionally remains an unsupported action, matching logged output; use `!kv get +json path`
- dotted paths, bracket indexes, quoted path components
- scalar `get` output and tree rendering consistent with current evidence
- `set` parses strict JSON values and scalar `True`/`False`/`null` compatibility, but Python booleans inside objects such as `{"reasoning": {"enabled": False}}` remain strings. This matches logs where malformed JSON/Python-ish object edits were stored as text and later fixed with lowercase JSON booleans.
- query expressions such as `.commands.gpt|keys`, `.path|length`, list slices like `.commands.gpt._default.system[-2:]`, literal jq-style values such as `!kv query "ok"`, and the logged `to_entries[]` debugging probe, which renders top-level `{"key": ..., "value": ...}` entries while ignoring the trailing pipe expression; missing/null `|keys` paths return the logged jq-style `null (null) has no keys` error, and logged jq-style compile errors are preserved for malformed query syntax such as `.commands.gpt._default.system.[-2:]`, `.commands.trivia.state._not-gay|keys`, `.pyylmao.irc.channels.#superbowl.history|length`, `.pyylmao.irc.channels.'#superbowl'.history|length`, and `.pyylmao.irc.channels['#superbowl'].history|length`
- unsupported actions keep the logged rough edge, e.g.
  `!kv update man my -> unknown error, op=update args=['update', 'man', 'my']`
  and `!kv delete man -> unknown error, op=delete args=['delete', 'man', '']`;
  use `del`, not `delete`

`pyylmao/kv/backends/sqlite.py` provides `KvContext` compatibility for generated commands. Generated command modules get a module-level `kv` helper scoped to `commands.<command_name>`. `KvContext.merge(path, dict_value)` recursively merges dictionaries, matching the logged generated-command guidance for trivia cache writes such as `kv.merge('cache.category.<category_id>', entries)`.

Generated commands can also import direct KV helpers from either `pyylmao.kv` or `pyylmao.kv.backends.sqlite`: `kv_get`, `kv_set`, `kv_append`, `kv_merge`, `kv_delete`, and `kv_query`. This matches logged generated command code that used `from pyylmao.kv import kv_get, kv_set, kv_delete, kv_query`, plus the logged `kv.merge(...)` cache guidance.

Do not add `!kvset` without stronger evidence. A prior log pass found generated/model text suggesting it, but not a clear user command invocation.

### LLM / Debug Tools

`pyylmao/llm_tools.py` implements the key command-creation/debugging tools:

- `read_command`, `write_command`, `revise_pattern`
- `install_packages`, `run`, `eval`
- `get_chat_history`, `irc_command`, `channel_list`, `get_channel_users`
- `read_skill`, `list_skills`, `create_skill`, `query_skills`, `update_skill`
- `remember`, `forget`, `search_memories`, `semantic_search`
- `save_artifact`, `read_artifact`, `list_artifacts`

Compatibility details already implemented:

- `read_command` accepts logged aliases such as `kv.py`, `reminder`, `urban`, `stock`, `fortune`, `ascii`, `drink`, `hf`, `teste`, `youtube`, and `yt`.
- `read_command` also maps log-proven reconstructed surfaces: `forecast -> weather`, `link_title -> link_preview`, `gpt -> router`, helper module `md2irc -> pyylmao.helpers.md2irc`, and KV helper/API names `kv_get`, `kv_set`, `kv_append`, `kv_merge`, `kv_delete`, `kv_query`, `KvContext`, and `KvResult` to `pyylmao.kv.backends.sqlite`. Do not map `cert`/`ssl` aliases to `crt`; logs show the original bot failed to find those names and the user corrected the model to `crt`.
- `read_command eval` resolves to the reconstructed source for the public generated-style debug command created through `write_command` in the logs. Its unanchored pattern is `(?i)\beval\b\s*(.*)`, so ordinary messages containing a later standalone `eval` word can trigger it just like the logged `grok doesn't like ... eval 1+2+3` example. The command intentionally uses Python `eval()` only, not `exec()`, emits `Eval error: <exception>` on failures, prints captured stdout before the returned value, uses per-invocation generated-command globals, and keeps mutations to the generated `__builtins__` dictionary across invocations.
- `read_command imgcap` resolves to reconstructed generated-command-style source with the logged URL regex, public `pyylmao.kv` helper imports, and `llm.get_model(...).prompt(..., attachments=[llm.Attachment(...)])`. This is based on the logged `imgcap` read/update flow that was used to create the `LLM` skill. It is intentionally source/debug parity only; the main router is not wired to caption every posted URL.
- `read_command` and `run` can use generated command source at `<generated_dir>/<name>.py` or the historical package layout `<generated_dir>/<name>/__init__.py`, even when the JSON state entry is missing or stale. This keeps recovered/generated source files usable after state restores or partial volume copies.
- `write_command` accepts logged `code`, descriptive `content`, and `pattern` shapes. If both `code` and `content` are present, `code` is persisted as source and `content` is stored as a description. If `name` is missing but the regex trigger clearly names a command, such as `^!inspect2$`, the generated command name is inferred from the trigger. Generated command names may start with digits, matching logged artifact/debug flows such as `read_command 3daudio` and `revise_pattern 3daudio`. It returns `No requirements found in provided code.`, then immediately load-checks the target module and the generated command set. Target import-time stdout/stderr and generated-command load errors are returned visibly, matching logged lines such as `Skipping command vocoder due to load error: ModuleNotFoundError("No module named 'pydub'")` and unrelated stale errors such as `Skipping command elliotsearch due to load error: ModuleNotFoundError("No module named 'pymupdf'")`.
- The OpenRouter system prompt and `write_command`/`run` tool schemas now explicitly describe the standard generated-command APIs before the model starts writing code. They tell the model to put executable Python in `code`, keep `content` as description, prefer `class Tool(llm.Toolbox): ... _onload(...)`, accept legacy `entrypoint(args, channel, nickname, username, hostname)`, and test commands through `run` with `cmd_name`/`args`. Tool schemas intentionally allow logged optional-argument debug calls such as `read_command args: {}` and code-only `write_command` calls whose command name is inferred from `pattern`. The OpenRouter tool loop uses the logged 32-call chain limit (`Chain limit of 32 exceeded.`) and suppresses tool calls requested after the logged 600-second wall-clock limit with `max_time reached: <now> <started> 600` plus `Tool calls cancelled: max_time 600s reached`.
- Leading prompt options observed in logs are parsed before OpenRouter calls: `maxh=N` overrides channel history for that request, `temperature=N` sets the request temperature, and quoted `system="..."` is appended to the system prompt. Malformed tokens such as `maxh=1translate` are left in the user prompt instead of being consumed.
- Generated command runtime compatibility includes the modern reference API from `https://cte.pcp.ovh/2/commands.html`: `import llm; class Tool(llm.Toolbox): pattern = r"..."; def _onload(self): ...`, sync or async `_onload`, constructor injection for `event`, `args`, `channel`, `nickname`, `username`, `hostname`, and `connection`, plus legacy `entrypoint(args, channel, nickname, username, hostname)`. Generated regex triggers use search semantics rather than start-only matching, matching the logged generated `eval` command whose unanchored pattern fired later in a line. Direct `run cmd_name=...` executes class-only `llm.Toolbox` commands when no legacy callable is present, matching live repair flows where the model used `run` to test a standard class API command. Older generated shapes `run(bot, channel, sender, args)`, `command(bot, args)`, and `<name>_command(...)` are also supported because current live attempts generated those forms. Script-style fallbacks now cover `main()` and clearly script-like files such as shebang/top-level-print artifacts when no standard callable exists, fixing current `write_command` artifacts that otherwise failed with `generated command <name> has no entrypoint`.
- The generated-command/top-level `llm` shim now exposes `llm.get_model(...).prompt(...).text()`, including a simple `schema=...` hint path, `system=...`, direct or `options={"temperature": ...}` temperature control, and `llm.Attachment(url=..., type="image/png")` image attachments. It also exposes `llm.get_tools()`, returning an iterable/mapping-like inventory whose entries have `name`, `plugin`, and `enabled` attributes. This inventory includes the artifact tools `save_artifact`, `read_artifact`, and `list_artifacts`, even though the logged `!tools` table did not always render every artifact helper row. Explicitly requested generated commands are also returned as callable entries, e.g. `llm.get_tools(["name"])["name"](args="...")`, preserving command-as-tool behavior inside generated command code. This matches logged command/skill patterns such as `llm.get_model('openrouter/openai/gpt-oss-120b')`, `model.prompt(..., schema=IrcPoll)`, `all_tools = llm.get_tools()`, and the generated LLM skill's attachment notes. Top-level `import llm` works in generated modules and saved Python debug artifacts.
- The OpenRouter LLM tool registry exposes command-backed tools directly by command name when the router command runner is present. These command tools accept `args` and dispatch through the same generated/reconstructed command path as `run cmd_name=...`, so the LLM can call reconstructed commands such as `define` or generated commands as standard tools without wrapping them in a shell command.
- Historical helper imports are available through `pyylmao.helpers`: `from pyylmao.helpers import md2irc` returns UTF-8 bytes and supports `output_fn=print`, and `from pyylmao.helpers import img2irc` returns newline-separated image render output from keyword args such as `width`, `render`, `blocks`, and `contrast`.
- `pyylmao.config` exports logged path constants `BASE_DIR`, `ASSETS_DIR`, and `DATA_DIR`; in the Docker runtime they resolve to `/app`, `/app/assets`, and `/app/data`.
- `pyylmao.runner._find_toolbox_class(module)` exists for historical debug/run tooling and returns the first `llm.Toolbox` subclass found in a module.
- Class-based generated commands can trigger on IRC events through `trigger_on`/`match_field`, including `pubmsg`, `privmsg`, `join`, `part`, `quit`, `nick`, `kick`, `ctcp`, `notice`, and `invite`. `send_to` supports a channel/nick string, a list, `all`, `*`, and simple placeholders such as `channel`, `target`, and `nickname`. The live IRC client now parses those events and routes generated `Toolbox` output accordingly.
- `MessageEvent` also provides python-irc-style compatibility fields used in logged examples: `event.arguments` and `event.args` return the event text as the first argument, `event.type` aliases the generated event type, and `event.source.nick`/`user`/`host` mirror the parsed IRC prefix.
- Generated commands can use logged raw-IRC compatibility helpers: legacy modules get a global `irc_command("RAW IRC LINE")`, and `from pyylmao.ircbot import bot` exposes `bot.connection.join(...)`, `invite(...)`, `privmsg(...)`, `notice(...)`, `part(...)`, `kick(...)`, `mode(...)`, `nick(...)`, `quit(...)`, and `send_raw(...)`. This is backed by the same live raw IRC sender as the LLM `irc_command` tool. Do not add `from tools import irc_command` or `from src.bot import ...`; logs show those imports failed in the original.
- Class-based generated commands receiving the injected `connection` object can also call `privmsg`, `privmsg_many`, `notice`, `action`, `ctcp`, `ctcp_reply`, `join`, `part`, `whois`, `names`, `list`, `topic`, `admin`, `info`, `ison`, `links`, `lusers`, `motd`, `oper`, `pass_`, `ping`, `pong`, `invite`, `kick`, `mode`, `nick`, `quit`, `disconnect`, `send_raw`, `send_raw_OLD`, `send_items`, `cap`, `add_global_handler`, `remove_global_handler`, `process_data`, `close`, `reconnect`, `set_keepalive`, `sasl_login`, `get_nickname`, `get_server_name`, and `is_connected`; `connection.reactor.server()` returns the connection, `connection.reactor.connections` contains it, and the reactor process methods are safe no-ops. Queued raw IRC commands are forwarded through the live raw sender after `_onload()` completes.
- Generated code that expects python-irc can use bundled top-level compatibility modules: `import irc.bot`, `import irc.client`, `import irc.strings`, and `from irclib import client`. `irc.client.Event` exposes `args`, `arguments`, and parsed `source.nick/user/host`; `irc.client.Reactor().server()` returns a `ServerConnection` whose raw IRC methods queue through the live raw sender; `irc.bot.SingleServerIRCBot` provides `connection`, `reactor`, `channels`, `config`, `servers`, `_connect`, `connect`, `start`, `die`, `disconnect`, `_join_channels`, `_dispatcher`, DCC no-op helpers, and `get_version`; `irc.strings.lower` and `IRCFoldedCase` provide basic IRC case folding.
- The live `irc_command` sender now returns logged-friendly success traces for common raw IRC commands, e.g. `Joined #chan`, `Parted #chan`, `Message sent to nick`, `Invited nick to #chan`, `Nickname changed to nick`, and request-sent lines for `WHO`/`NAMES`/`WHOIS`, instead of the earlier generic `sent IRC command: ...` wording.
- The live IRC client maintains the KV-backed channel user state read by `channel_list` and `get_channel_users`. It updates users from numeric `NAMES` replies and JOIN/PART/QUIT/NICK/KICK events, strips IRC mode prefixes such as `@` and `+`, and preserves the server-provided user order. This matches logged flows where the model joined a channel, called `get_channel_users`, then acted on the returned names.
- `run` supports generated commands, reconstructed command runner dispatch, `exec`, `python`, `python3`, and saved Python artifact execution. It handles logged forms like `python ['debug_ansi']`, `python ['/home/pyylmao/bot/debug_ansi.py']`, and `exec ['debug_ansi.py']`.
- `eval` with no `code` argument returns `No code provided` rather than throwing a Python argument error.
- `semantic_search` accepts logged `query`, `phrases`, and `profile` arguments and performs dependency-light web search. Profiles default to `balanced` and also accept logged values such as `instant`, `news`, `comprehensive`, and `web_search`. Tool traces expose the visible `Profile: <profile>` line like the logs; `search_memories` remains the separate memory lookup tool.
- `get_chat_history` emits visible tool traces matching both logged shapes: fallback context reads use `read N lines after filter`, while persisted channel-history reads use the newer `read N lines from chat history`.
- `!cancel` toggles the persisted LLM tool-cancellation flag and returns `Tool cancellation flag is ON` / `Tool cancellation flag is OFF`. While the flag is ON, OpenRouter tool calls are suppressed with the visible trace `Tool calls cancelled: user intervention`, then the model is allowed to finish without the cancelled tool output. This matches logged intervention flows around long or unsafe tool chains.
- LLM tool traces now expose bounded results for debug tools where the logs showed visible output: `write_command`, `revise_pattern`, `run`, `save_artifact`, and `irc_command`. They intentionally do not dump full `read_command` source or `read_artifact` contents as automatic traces.
- `read_artifact` missing files return `Error: <basename>`, matching logs such as `/etc/issue -> Error: issue`. The historical attachment typo is preserved: `Unable to access attachment. Please verifythe file or provide additional details.` When artifact paths match logged generated-command debug paths such as `commands/spam/__init__.py`, `src/commands/spam/__init__.py`, or `spam/__init__.py`, `read_artifact` falls back to the same generated source resolver as `read_command`.
- `save_artifact` accepts the logged optional `create_dirs` argument; parent
  artifact directories are created automatically for nested paths.
- `list_artifact` singular is accepted as an alias for `list_artifacts`.
- `query_skill` singular maps to `query_skills`.
- Built-in `read_skill` docs exist for `KV`/`kvstore`, `img2irc`, `imghax`, `md2irc`, and `llm`; state-created skills override built-ins.

### Reload / Maintenance

`pyylmao/reload_command.py` reproduces logged maintenance responses and generated command reloads:

- Bare `!reload` returns `no handler modules found`.
- `!rehash` returns `Configuration reloaded successfully`.
- Generated command names still reload through the generated command store, e.g. `!reload yolo -> generated_commands.yolo`.
- Log-proven module queries include `md2irc`, `gpt.common`, `gpt.tools`, `helpers.img2irc`, `handlers.kvstore`, `handlers.reload`, `handlers.toggle`, `anagram_rs`, `backends.sqlite`, `pyylmao.kv.backends.sqlite`, `pyylmao.config`, `pyylmao.utils`, `mdbuffer`, and `gpt.billing`.
- High-fanout historical queries are explicit: `!reload llm` returns the logged `llama_index.*llm*` module list plus `llm`, and `!reload kvstore` returns the logged `llama_index.core.storage.kvstore*` modules plus `pyylmao.handlers.kvstore`.
- Logged no-match/error cases are preserved for `gpt.billingD`, `helpres.img2irc`, `handlers.reloadd`, `commands.bsort`, `commands.reminders`, `commands.urbandict`, and `handlers.help`.

LLM prompt prefixes are handled by `parse_llm_prompt` and the default alias table in `pyylmao/aliases.py`. Log-mined prompt forms include:

- Built-in trigger forms: `gpt, ...`, `gpt: ...`, `@gpt ...`, `@@gpt ...`, `grok, ...`, `grok: ...`, bare `gpt ...`/`grok ...`, `@grok ...`, `@@grok ...`, `!ai ...`, and direct model IDs such as `@@openrouter/provider/model ...`.
- Default alias prompts from `!alias list2`: `flash`, `nano`, `mini`, `gpt5`, `banana`, `hermes`, `sonoma`, `gronk`, `mistral`, `mini41`, `nano41`, `nano41o`, `gabe`, `sonnet`, `grok4`, `grok3`, `gpt41`, `minimax`, `grox`, `code`, `sherlock`, `kimi`, `dash`, `bert`, `pyylmao`, `chimera`, `d`, `speciale`, `venice`, and `glm`.
- Additional log-observed aliases now built in: `hy`, `hy2`, `q`, `mm`, `nemo`, `nemo9`, `luna`, `lite`, `hunter`, and `g`.

`hy, ...` is especially high-confidence: logs show `!alias set hy openrouter/tencent/hy3-preview`, followed by hundreds of `hy, ...` prompts and tool-using `@@hy ...` prompts.

### Artifacts and Images

`save_artifact` writes under the artifact/web directory and returns:

```text
━━☛ New artifact: <url>
```

Nested artifact paths such as `web apps/demo.html`, `pcb-generator/index.html`, and `2/phlegm_clicker_v2.html` are supported. Parent directories are created automatically, the logged optional `create_dirs` argument is accepted, and path traversal is rejected.

The `image-server` service runs Cloudflared and writes the public URL file. Keep this running when testing image/artifact behavior, especially `!gay`, `!img2irc`, and generated HTML/image artifacts.

### Twitter/X

`pyylmao/twitter.py` reconstructs the logged `twitter` command table entry for `twitter.com`, `x.com`, `xcancel`, and `nitter` status URLs. `run cmd_name=twitter` and `!twitter <status-id-or-url>` both route through the same renderer, so LLM tool calls can pass either a full URL or a bare status ID. `read_command twitter` returns the reconstructed source. Raw tweet JSON is saved best-effort to the historical `/usr/src/app/t.json` location with runtime-safe fallbacks.

### Ligma

`pyylmao/ligma.py` reconstructs the logged generated `ligma` command. It triggers on `ligma.pro/@user/<status-id> [all]`, matching the final command table pattern `^.*ligma\.pro/@[^/]+/(\d+)\s?(.*)$`. The renderer fetches `https://ligma.pro/api/v1/statuses/<id>`, prints optional img2irc avatar rows merged with `display @acct Mon DD YYYY`, wrapped status text, and `💬/♻️/❤️` stats. A trailing `all` fetches `/api/v1/statuses/<id>/context` and renders descendant replies indented under the main post. `read_command ligma` resolves to reconstructed source; this matters because logs repeatedly used `ligma` as the formatting reference when repairing `nostr`.

### Nostr

`pyylmao/nostr.py` reconstructs the logged generated `nostr` command. It handles `nostr:<note|nevent|event-id|npub>`, parses NIP-19 references, fetches kind-1 notes from WebSocket relays, looks up profile metadata, optionally renders the avatar through img2irc, and formats output as `display @name Mon DD YYYY` plus wrapped post content. `run cmd_name=nostr` prefixes args as `nostr:<arg>`, and `read_command nostr` returns reconstructed source.

### ANSI / IRC Conversion

`pyylmao/ansi2irc.py` reconstructs the logged generated `ansi2irc`/`ansi2irc2` command surface from `irc.gangnet.#tclmafia.weechatlog`. It handles `!ansi2irc <url>` and `!irc2ansi <url>`, fetches URL bytes, detects CP437 vs UTF-8, strips trailing SAUCE records, renders a bounded ANSI CSI/SGR virtual terminal to mIRC color output, and includes reverse IRC-to-ANSI conversion for `!irc2ansi`. `read_command ansi2irc` and `read_command ansi2irc2` both resolve to this source, and `run cmd_name=ansi2irc` / `run cmd_name=ansi2irc2` prefix args as `!ansi2irc`.

### Poll / Vote

`pyylmao/poll.py` and `pyylmao/vote.py` reconstruct the heavily debugged generated `poll`/`vote` surface. The router handles `!poll ...`, `?poll`, bare single-label votes while a poll is active, and `!vote <label>`. It accepts labeled `A. ... B. ...`, numeric `1. ... 2. ...`, and the later flexible `question? yes/no/kind of` form. Poll state is channel-scoped in `state.data["polls"]`; votes are one per nickname and can be changed by voting again. `read_command poll`, `read_command vote`, `read_command votes`, and `read_command poll_vote` resolve to reconstructed source. This was added from log evidence around the repeated repair loops in `irc.supernets.#superbowl.weechatlog`, not as a speculative new command.

### Trivia

`pyylmao/trivia.py` reconstructs the high-frequency generated `trivia` command. The router handles `!trivia categories`, `!trivia category <name|any>`, `!trivia difficulty <easy|medium|hard>`, `!trivia threshold <0.0-1.0>`, `!trivia mode <dumb|smart>`, `!trivia rephrase`, bare `!trivia`, and free-text answers while a question is active. Wrong guesses are silent, A/B/C/D answers are ignored, Levenshtein matching runs before smart-mode semantic matching, correct answers auto-ask the next question, and question suffixes use the logged dark-grey IRC color wrapper around `(difficulty - Category)`.

Trivia state and stats live under the shared KV tree at `commands.trivia`, with channel keys such as `_not-gay`; logged probes like `!kv query .commands.trivia.state."_not-gay"|keys`, `!kv get commands.trivia.state._not-gay.correct_answer`, and `!kv get commands.trivia.state._not-gay.last_guesses` should see the reconstructed state shape. The command reads final local CSV categories from `assets/trivia/categories/*.csv` when present, matching the logs that removed OpenTDB API calls; a small fallback question set exists only so this repo still runs without the historical CSV assets. `read_command trivia` resolves to the reconstructed source.

### Phenoguessr

`pyylmao/phenoguessr.py` reconstructs the logged generated `phenoguessr` / `!pheno` command. The command table pattern is `^!pheno(?: (.*))?$`, and `read_command phenoguessr` plus `read_command pheno` resolve to reconstructed source. Bare `!pheno` starts a game and stores logged state fields under `commands.phenoguessr`, including `current_pheno`, `current_pheno_label`, `current_gender`, `last_guess_time`, `recent_phenos`, and `stats`. It reads `commands.phenoguessr.output_mode` and `commands.phenoguessr.img2irc_args` to render asset images through `img2irc`/`imghax`, passing only explicitly configured `img2irc_args` keys, matching the May 4 repair loop.

The repo and live VM currently do not include the historical `assets/phenoguessr/*` image corpus, so missing images are tolerated and the stateful game still runs. Logged output shapes are preserved for start, wrong guesses, `BULLSEYE`, `Technically correct!`, unresolved locations, and no active game. `run cmd_name=phenoguessr` and `run cmd_name=pheno` prefix args as `!pheno` for LLM debug sessions. Evidence came from `irc.gangnet.#tclmafia.weechatlog` around lines 11707-11835, 45508-45616, and 45670-47111, plus `irc.supernets.#superbowl.weechatlog` around lines 2377320-2377500.

### Vocoder

`pyylmao/vocoder.py` reconstructs the generated non-AI speech-synthesis command. The final observed command table pattern was `^!vocoder (.+)$`, and live use returned URLs such as `https://cte.pcp.ovh/2/<12hex>.wav`; the implementation writes a mono WAV under the served web directory and returns `<base>/2/<12hex>.wav`. The earlier generated surface `vocoder <filename.wav> <text>` is also supported and preserves the requested filename, matching the early `https://cte.pcp.ovh/huh.wav` outputs. `read_command vocoder` resolves to reconstructed source, and `run cmd_name=vocoder` dispatches through `!vocoder`.

The synthesizer intentionally uses dependency-free standard-library code with simple formant/noise/stop synthesis, matching the logged requirement to avoid external TTS engines such as espeak. It is not expected to sound good; historical logs repeatedly describe it as rough but usable.

### LiveBench

`!livebench` fetches real current public LiveBench data online from `livebench.ai`. Do not replace this with static fixture data except in tests.

### Radio and Anagram

Radio is on hold per user instruction. Current radio code mirrors help/queue/new surfaces but not full playback/search/queue backends.

Anagram can be added later per user instruction.

## Useful Log-Mining Commands

Find tool calls:

```sh
sudo -n incus exec diverse-deer -- sh -lc 'command -v rg >/dev/null 2>&1 || apk add ripgrep >/dev/null; rg -n "(read_command args|write_command args|revise_pattern args|run args|read_skill args|save_artifact args|read_artifact args|list_artifacts args|get_chat_history args)" /root/.local/share/weechat/logs/irc.*.weechatlog'
```

Count `read_command` names:

```sh
sudo -n incus exec diverse-deer -- sh -lc "command -v rg >/dev/null 2>&1 || apk add ripgrep >/dev/null; rg -o \"read_command args: \\\\{'name': '[^']+'\" /root/.local/share/weechat/logs/irc.*.weechatlog | sed \"s/.*'name': '//;s/'$//\" | sort | uniq -c | sort -nr | head -80"
```

Inspect `!kv` evidence:

```sh
sudo -n incus exec diverse-deer -- sh -lc 'command -v rg >/dev/null 2>&1 || apk add ripgrep >/dev/null; rg -n "\!kv (get|set|query|append|del|info|modes)" /root/.local/share/weechat/logs/irc.*.weechatlog'
```

## Priorities for Future Work

1. Continue improving `!kv` only from clear log evidence. Current implementation is broad; avoid speculative aliases.
2. Continue closing gaps in LLM/debug tools used for command creation:
   - logged argument shapes
   - singular/plural tool aliases
   - artifact path and output quirks
   - generated command import/runtime compatibility
3. Mine remaining high-frequency generated commands only after the core command-creation/debug surface is stable.
4. Keep verifying with Docker and keep `image-server`/Cloudflared running after changes.

## IRC Verification

The user said it is acceptable to connect to IRC and talk to the bot to verify behavior when necessary. Prefer log evidence and Docker tests first; use IRC for live behavior checks that cannot be established from logs or local tests.
