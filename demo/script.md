# Demo video script

You film **one set of clips** and edit them into **two versions**:

| Version | Length | Use it for |
|---|---|---|
| **Submission cut** | 90s | Nous Discord submission, Twitter post |
| **Director's cut** | ~2:15 | Linked from Discord, pinned tweet reply, README "demo" link |

The director's cut adds two beats the 90s version doesn't fit:
the **live install in a real terminal** and **director memory loop captured
in action** (not just a static before/after image). Builders watching on
Discord care about those most.

Both versions: 16:9, 1920×1080. Same music, same subtitles —
only the timeline differs.

Three voice tracks possible:
- **A.** Russian narration + English subtitles (recommended)
- **B.** English narration + no subtitles
- **C.** No narration, music + on-screen text only

Below is **track A**. Background music: instrumental, no lyrics, low.
~25% volume under narration.

---

## Tools

1. **OBS Studio** (or QuickTime + Chrome) — for screen-recording.
2. **DaVinci Resolve** (free) — cutting, subs, music.
3. **Browser at 1920×1080**, F11 fullscreen.
4. The deployed site: `https://hermes-story.art`
5. **iTerm2** or **Warp** for the live terminal beat.

---

## Asset list — record once, edit twice

| #  | Source                       | What to capture                                      | Length |
|----|------------------------------|------------------------------------------------------|--------|
| A1 | `web/video/intro.html`       | Reload, record from 0s to 5.0s                       | 5s     |
| A2 | hermes-story.art             | Hero scroll + auto-demo clapboard                    | 10s    |
| A3 | hermes-story.art (live run)  | Type prose, click generate, watch board fill in      | 35s    |
| A4 | hermes-story.art             | Cold-vs-directed image, slow scroll across           | 14s    |
| A5 | hermes-story.art (live)      | **NEW** 2nd scene auto-applies saved memory          | 22s    |
| A6 | hermes-story.art             | Inspect drawer — Memory tab → Trace tab              | 16s    |
| A7 | hermes-story.art             | Kimi roles → Why Hermes → Grounded by design         | 12s    |
| A8 | iTerm2 / Warp                | **NEW** Real terminal — three install commands       | 12s    |
| A9 | `web/video/outtro.html`      | Reload, record from 0s to 13.5s                      | 13.5s  |

The two NEW captures (A5, A8) are what make the director's cut
worth watching. **Do them.** They take 5 minutes each.

---

## Submission cut (~90s)

```
0:00 ─ INTRO (A1)                  ─ 0:05    5s
0:05 ─ HERO + AUTO-DEMO (A2)       ─ 0:13    8s
0:13 ─ MAIN GENERATION (A3 cut)    ─ 0:33   20s
0:33 ─ COLD-VS-DIRECTED (A4 cut)   ─ 0:43   10s
0:43 ─ INSPECT DRAWER (A6 cut)     ─ 0:54   11s
0:54 ─ KIMI ROLES (A7 cut)         ─ 1:02    8s
1:02 ─ TERMINAL LIVE (A8 cut)      ─ 1:08    6s
1:08 ─ OUTTRO install+outro (A9)   ─ 1:21   13.5s   ← see note
```

**Note on A9 in 90s cut:** the outtro file is 13.5s long because it
includes both an install card AND the final outro slogan. For the 90s
cut, you have two options:

- **Option 1 (recommended):** use **only the outro half** — start
  recording at 7.4s into A9 (right after the cross-fade) so you skip
  the install card (which is already covered by A8 terminal live).
  That trims A9 down to ~6s and the total becomes 1:14.
- **Option 2:** use the full A9 (13.5s). A8 + install card in A9
  becomes intentional repetition — first you see real terminal,
  then you see the same commands as a stylised graphic. Total: 1:21.

Pick whichever feels right after editing. Both fit under 90s.

---

## Director's cut (~2:15)

```
0:00 ─ INTRO (A1)                  ─ 0:05    5s
0:05 ─ HERO + AUTO-DEMO (A2)       ─ 0:15   10s
0:15 ─ MAIN GENERATION (A3 full)   ─ 0:50   35s
0:50 ─ COLD-VS-DIRECTED (A4 full)  ─ 1:04   14s
1:04 ─ MEMORY LOOP LIVE (A5)       ─ 1:26   22s
1:26 ─ INSPECT DRAWER (A6 full)    ─ 1:42   16s
1:42 ─ KIMI ROLES (A7 full)        ─ 1:54   12s
1:54 ─ TERMINAL LIVE (A8 full)     ─ 2:06   12s
2:06 ─ OUTTRO outro half (A9)      ─ 2:13    7s    ← skip install card
```

Total: **~2:13**, fits comfortably under any platform's preview cap.
Same A9-trim trick: terminal live (A8) already shows the commands,
so cut A9 to its outro half only.

---

## Beat-by-beat narration

### 0:00 — 0:05  ·  INTRO  (A1)

**Footage:** `intro.html` — film academy leader counts down 3-2-1
with sweep rings, then black flash, then title fades up.

No narration. Music starts low. Let the countdown speak for itself.

**EN sub (none — visual is self-explanatory).**

---

### 0:05 — 0:13/0:15  ·  HERO + AUTO-DEMO  (A2)

**Footage:** scroll from top of hermes-story.art. Hero with auto-demo
clapboard rendering 6 noir frames.

**RU:**
> «Я строю Hermes-скилл, который превращает прозу в раскадровку.»

**EN sub:**
> *I'm building a Hermes skill that turns prose into a film storyboard.*

---

### 0:13/0:15 — 0:33/0:50  ·  MAIN GENERATION  (A3)

**Footage:** scroll to Try section. Click "The Rain Investigation" demo
preset. Live drawing — 6 frames stroke-by-stroke. Progress dots
top-right tick from `○○○○○○` to `●●●●●●`.

**RU (90s, condensed):**
> «Вы пишете сцену — Kimi K2.5 разбирает её на шесть кадров с
> линзами, движениями камеры и линией взгляда. Локальный SVG-рендерер
> рисует доску штрих за штрихом, прямо в браузере.»

**EN sub:**
> *You write a scene. Kimi K2.5 parses it into six shots with lenses,
> camera moves, and eye-line. The local SVG renderer draws the board
> stroke-by-stroke, in the browser.*

**RU (director's cut, +12s extension after the condensed version):**
> «Каждый кадр — это рамка с метаданными плюс рисованный примитив.
> Дождь, неон, силуэт, фокусное кольцо, eye-line маркер — всё
> определено схемой Scene JSON. Никакой диффузии, никаких артефактов.
> Финальная доска редактируется как вектор.»

**EN sub (extension):**
> *Every frame is metadata plus a rendered primitive. Rain, neon,
> silhouette, focus ring, eye-line marker — all defined by the Scene
> JSON schema. No diffusion, no artifacts. The final board stays
> editable as vector.*

---

### 0:33/0:50 — 0:43/1:04  ·  COLD-VS-DIRECTED  (A4) — KEY BEAT

**Footage:** Learning Loop section, focus on `cold-vs-directed.png`.
BEFORE / AFTER both visible. Slow horizontal pan if your editor
allows, otherwise hold static.

**RU:**
> «Я правлю один кадр заметкой "more Hitchcock — низкий ракурс,
> резкая тень, силуэт". Hermes извлекает обобщённое правило режиссуры
> и сохраняет его. Следующая сцена с тем же тегом снята уже
> в этом ключе. Без повторного промпта.»

**EN sub:**
> *I revise one frame — "more Hitchcock, low angle, hard shadow,
> silhouette". Hermes extracts a generalised director rule and saves
> it. The next matching scene is already shot that way. No
> re-prompting.*

> **Strongest beat. Slow down. Let the AFTER panel breathe at least
> 4 seconds before cutting.**

---

### 1:04 — 1:26  ·  MEMORY LOOP LIVE  (A5) — DIRECTOR'S CUT ONLY

**Footage:** live, on hermes-story.art. After scene 1 generated and
revised, scroll to top, paste the **second scene prompt** (e.g.
"She enters the stairwell. Listens. A shape on the landing above."),
hit Generate. Watch — *without any user revision* — Hermes apply the
saved Hitchcock rule from scene 1: low angle, threat halo, silhouette.

Then click `★ MEMORY` tab in the inspect drawer to confirm the rule
loaded. Text "memory: active" appears in the board footer.

**RU:**
> «Вот вторая сцена. Тот же стиль никто не запрашивал — но Hermes
> сам применяет правило, потому что теги совпали. Низкий ракурс. Тень.
> Силуэт на лестничной площадке. Память живёт между сценами.»

**EN sub:**
> *Here's a second scene. Nobody requested the same style — but
> Hermes applies the rule on its own, because the tags matched.
> Low angle. Shadow. Silhouette on the landing. Memory persists
> across scenes.*

> **The beat that proves "Hermes learns how you direct."
> Don't skip it in the director's cut.**

---

### 0:43/1:26 — 0:54/1:42  ·  INSPECT DRAWER  (A6)

**Footage:** scroll back to Try output. Click `★ MEMORY` tab — show
saved rule JSON. Then `→ TRACE` tab — 5 stages, 2 of them Kimi K2.5
in red, latencies in green.

**RU (90s, condensed):**
> «Каждый артефакт инспектируем. Правило, трейс агента, валидация
> патчей детерминированная. Не чёрный ящик.»

**EN sub:**
> *Every artifact is inspectable. Rule, agent trace, deterministic
> patch validation. Not a black box.*

**RU (director's cut, +5s extension):**
> «Hermes пишет эти же файлы на диск, когда скилл запущен локально.
> Scene JSON, critique patches, character bible, director memory.
> Всё в одной папке.»

**EN sub (extension):**
> *Hermes writes these same files to disk when the skill runs locally.
> Scene JSON, critique patches, character bible, director memory.
> All in one folder.*

---

### 0:54/1:42 — 1:02/1:54  ·  KIMI ROLES + GROUNDED  (A7)

**Footage:** scroll to "Kimi K2.5 — three roles in one skill" band.
Hold 3s. Then into Why Hermes black section, show "Grounded by
design" checklist.

**RU:**
> «Kimi K2.5 здесь не лейбл. Она работает в трёх ролях:
> парсит прозу, критикует доску, извлекает память режиссёра.
> И всё это grounded — никаких галлюцинаций сюжета не попадёт
> в финальный артефакт.»

**EN sub:**
> *Kimi K2.5 is not a label — it has three roles. Parses the prose.
> Critiques the rendered board. Extracts director memory. And it
> stays grounded — no plot hallucinations reach the final artifact.*

---

### 1:02/1:54 — 1:08/2:06  ·  TERMINAL LIVE  (A8)

**Footage:** real terminal in iTerm2 / Warp at 1920×1080. Run the same
three commands you'll show as graphics, but **for real**:

```bash
git clone git@github.com:Zhekinmaksim/storyboard.git
cp -r storyboard ~/.hermes/skills/creative/storyboard
hermes chat "draft a noir storyboard for a detective in the rain"
```

Show Hermes loading the skill, response starting to come back.
Cut before it finishes — 6s for 90s cut, full 12s for director's cut.

> **Pre-record this in a clean iTerm session.** Use a tilde-prompt
> theme that matches the Dry Ink palette (cream bg, warm ink fg, mono
> font) so it visually flows from the previous beats.

**RU:**
> «Это не SaaS. Это локальный Hermes-скилл — три команды, и он у тебя.»

**EN sub:**
> *Not SaaS. It's a local Hermes skill — three commands and it's yours.*

---

### 1:08/2:06 — 1:14/2:13  ·  OUTTRO  (A9, outro half)

**Footage:** `outtro.html` recording. **Skip the install half** —
start your edit at the 7.4s mark of the recording (right after the
cross-fade from install to outro). You get ~6 seconds of slogan +
URLs + credit.

If you used Option 2 of the 90s cut and kept the full outtro,
this is the beat where the install card replays as graphic + then
fades to outro. Either works.

**RU (final beat, slow, lower volume):**
> «Hermes не просто рисует сцену. Он учится тому, как вы её снимаете.»

**EN sub:**
> *Hermes doesn't just draw the scene. It learns how you direct the
> next one.*

Music fades on the last 1.5s. Hold the final frame (URLs + credit
visible) for at least 2 seconds before cutting to black.

---

## How to assemble in DaVinci Resolve

1. **Import** all 9 clips (A1–A9) into a media bin.
2. **Two timelines** — "Submission cut" and "Director's cut". Same
   media, different edit.
3. **For 90s cut:** trim A3 to 20s (keep most visual moments — frames
   1, 3, 5, 6 typically). Trim A9 to outro half (6s starting at 7.4s).
4. **For director's cut:** use full A3 (35s), add A5 (22s) between A4
   and A6, full A8 (12s), trim A9 to outro half.
5. **Subtitles** — single text layer per beat, English only.
   - Style: white text 32–36px, 80% opacity black bar behind
   - Bottom-third placement
   - Each sub on screen ≥2.5s
   - Font: Inter / Helvetica / SF Pro Text
6. **Audio:**
   - Track 1: voice-over (record on phone in quiet room → Audacity
     → light noise reduction → −3dB compression)
   - Track 2: instrumental music at 15–25% gain, ducked under voice
7. **Final encode:**
   - 1920×1080 H.264, 30fps, 8–12 Mbps for both versions
   - Sub 80 MB so it uploads anywhere
8. **Watch each version muted once.** If you can't tell what the
   project does without sound, re-cut.

---

## Recording tips

- **Don't record voice + screen in one take.** Screen first, voice
  second, sync in the edit.
- **Read the Russian script out loud once.** Some words
  (`детерминированная`, `обобщённое`) are tongue-twisters.
- **Re-record stumbled takes**, don't patch with editing.
- **The strongest beat is COLD-VS-DIRECTED.** Slow down there.
  Director's cut adds the live-memory beat immediately after which
  doubles the impact.
- **Submit the 90s cut. Link the 2:13 cut.** That way both attention
  spans get served.

---

## Where to submit

**Nous Research Discord** — `discord.gg/nousresearch`. The Hermes
Creative Hackathon submission window is in their Discord, in a
hackathon-specific channel (look for the pinned announcement).
Submission usually means: post your demo video + GitHub repo link
in the dedicated submissions thread, before the **May 3 2026**
deadline (UTC).

**This hackathon is not on lablab.ai or Devpost.** Don't waste time
trying to upload there.

Best posting time: weekday afternoon UTC. If you have a Twitter
following already, post there at the same time and link both ways
(Discord post → Twitter, Twitter → Discord).

---

## Pre-submit checklist

- [ ] Both video versions render end-to-end without audio glitches
- [ ] All English subs are on-screen ≥2.5s
- [ ] `hermes-story.art` is live and the rate limit isn't tripped
- [ ] Repo is public at `github.com/Zhekinmaksim/storyboard`
- [ ] README's "Hallucination control" section is published
- [ ] Gallery has ≥3 seeded boards (you clicked demo presets with
      "Share to gallery" checked)
- [ ] Your Discord username matches the hackathon entry
- [ ] Tweet drafted with the GIF attached
- [ ] Director's cut uploaded somewhere stable (YouTube unlisted /
      Twitter / Discord file) and linked in your submission post
