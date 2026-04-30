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

Both versions: 16:9, 1920×1080. No voice-over. Use instrumental music
plus short English subtitles only. The video must still make sense
when watched muted.

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
| A3b| hermes-story.art (live run)  | Click one frame, add director note, re-render frame  | 12s    |
| A4 | hermes-story.art             | Cold-vs-directed image, slow scroll across           | 14s    |
| A5 | hermes-story.art (live)      | **NEW** 2nd scene auto-applies saved memory          | 22s    |
| A6 | hermes-story.art             | Inspect drawer — Memory tab → Trace tab              | 16s    |
| A7 | hermes-story.art             | Kimi roles → Why Hermes → Grounded by design         | 12s    |
| A8 | iTerm2 / Warp                | **NEW** Real terminal — three install commands       | 12s    |
| A9 | `web/video/outtro.html`      | Reload, record from 0s to 13.5s                      | 13.5s  |

A3b is the missing product beat: click one frame, write a natural
language direction, and only that frame changes. A5 then proves the
same note became reusable director memory.

---

## Submission cut (~90s)

```
0:00 ─ INTRO (A1)                  ─ 0:05    5s
0:05 ─ HERO + AUTO-DEMO (A2)       ─ 0:13    8s
0:13 ─ MAIN GENERATION (A3 cut)    ─ 0:32   19s
0:32 ─ FRAME REVISION (A3b cut)    ─ 0:42   10s
0:42 ─ COLD-VS-DIRECTED (A4 cut)   ─ 0:50    8s
0:50 ─ INSPECT DRAWER (A6 cut)     ─ 0:58    8s
0:58 ─ KIMI ROLES (A7 cut)         ─ 1:05    7s
1:05 ─ TERMINAL LIVE (A8 cut)      ─ 1:11    6s
1:11 ─ OUTTRO outro half (A9)      ─ 1:18    7s
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
0:15 ─ MAIN GENERATION (A3)        ─ 0:45   30s
0:45 ─ FRAME REVISION (A3b)        ─ 1:00   15s
1:00 ─ COLD-VS-DIRECTED (A4)       ─ 1:12   12s
1:12 ─ MEMORY LOOP LIVE (A5)       ─ 1:32   20s
1:32 ─ INSPECT DRAWER (A6)         ─ 1:46   14s
1:46 ─ KIMI ROLES (A7)             ─ 1:56   10s
1:56 ─ TERMINAL LIVE (A8)          ─ 2:06   10s
2:06 ─ OUTTRO outro half (A9)      ─ 2:13    7s    ← skip install card
```

Total: **~2:13**, fits comfortably under any platform's preview cap.
Same A9-trim trick: terminal live (A8) already shows the commands,
so cut A9 to its outro half only.

---

## Beat-by-beat screen actions + subtitles

No narration. Use one English subtitle per beat. Keep each subtitle on
screen for at least 2.5 seconds.

### 0:00 - 0:05  ·  INTRO  (A1)

**Footage:** `intro.html` — countdown 3-2-1, black flash, title.

**Subtitle:** none.

---

### 0:05 - 0:13/0:15  ·  HERO + AUTO-DEMO  (A2)

**Action:** Open `https://hermes-story.art`, fullscreen. Hold the hero,
then show the auto-demo board drawing in the clapboard.

**Subtitle:**
> Type a scene. Hermes turns it into a six-shot film storyboard.

---

### 0:13/0:15 - 0:32/0:45  ·  MAIN GENERATION  (A3)

**Action:** Scroll to `Generate your own scene`. Click the `Noir alley`
or `The Rain Investigation` preset. Keep `Share to public gallery`
checked. Click `Generate Storyboard`. Hold while the board fills in.

**Subtitle 1:**
> Kimi K2.5 parses prose into Scene JSON: shots, lenses, movement, timing.

**Subtitle 2:**
> The local SVG renderer draws every frame stroke by stroke.

**Subtitle 3:**
> A deterministic quality gate prevents empty or repeated frames.

---

### 0:32/0:45 - 0:42/1:00  ·  FRAME REVISION  (A3b)

**Action:** After the first board is done, click a strong frame, ideally
`1F` or the frame marked as `HERO FRAME`. In the director note box,
type:

```text
more Hitchcock — low angle, harder shadow, killer as silhouette
```

Click the apply/revise button. Hold while only that frame re-renders.
If the inspect drawer opens, briefly show the updated frame and the
memory/trace feedback.

**Subtitle 1:**
> Click any frame and direct it with plain language.

**Subtitle 2:**
> Only that frame re-renders. The rest of the board stays stable.

**Subtitle 3:**
> The note becomes a reusable director-memory rule.

---

### 0:42/1:00 - 0:50/1:12  ·  COLD-VS-DIRECTED  (A4)

**Action:** Scroll to the Learning Loop section. Show the
`cold-vs-directed.png` image with BEFORE and AFTER visible. Hold the
AFTER side long enough to read.

**Subtitle 1:**
> Revise one frame once. Hermes saves the director rule.

**Subtitle 2:**
> The next matching scene inherits the style automatically.

---

### 1:12 - 1:32  ·  MEMORY LOOP LIVE  (A5, director's cut only)

**Action:** Go back to Try section. Clear the textarea and paste:

```text
She enters the stairwell. Listens. A shape on the landing above.
```

Click `Generate Storyboard`. Let the board render. Then open `★ MEMORY`
in the inspect drawer and show the saved rule JSON. If visible, hold the
board footer where `memory: active` appears.

**Subtitle 1:**
> Nobody asks for Hitchcock again. Hermes applies the saved rule by tag.

**Subtitle 2:**
> Low angle. Hard shadow. Silhouette reveal. Memory persists across scenes.

---

### 0:50/1:32 - 0:58/1:46  ·  INSPECT DRAWER  (A6)

**Action:** Open `★ MEMORY`, then `→ TRACE`. Show memory JSON, pipeline
stages, Kimi steps, and local SVG/render/export stages.

**Subtitle 1:**
> Every artifact is inspectable: memory, trace, patches, JSON.

**Subtitle 2:**
> Kimi proposes. Storyboard verifies.

---

### 0:58/1:46 - 1:05/1:56  ·  KIMI ROLES + GROUNDED  (A7)

**Action:** Scroll to `Kimi K2.5 — three roles in one skill`. Then scroll
to `Grounded by design` / hallucination-control section.

**Subtitle 1:**
> Kimi K2.5 parses, critiques, and extracts director memory.

**Subtitle 2:**
> Hallucinations do not reach the final artifact.

---

### 1:05/1:56 - 1:11/2:06  ·  TERMINAL LIVE  (A8)

**Action:** Show a real terminal. Type the commands slowly:

```bash
git clone git@github.com:Zhekinmaksim/storyboard.git
cp -r storyboard ~/.hermes/skills/creative/storyboard
hermes chat "draft a noir storyboard for a detective in the rain"
```

Cut after Hermes starts responding.

**Subtitle:**
> Runs locally as a Hermes skill. Outputs editable SVG, JSON, memory, and a production packet.

---

### 1:11/2:06 - 1:18/2:13  ·  OUTTRO  (A9, outro half)

**Action:** Use `outtro.html`, but cut from the outro half around 7.4s,
after the install card cross-fade. Hold the final URLs for at least two
seconds.

**Subtitle 1:**
> Prose in. Cinematic storyboard out.

**Subtitle 2:**
> Live: hermes-story.art · Repo: github.com/Zhekinmaksim/storyboard

---

## How to assemble in DaVinci Resolve

1. **Import** all clips (A1–A9 plus A3b) into a media bin.
2. **Two timelines** — "Submission cut" and "Director's cut". Same
   media, different edit.
3. **For 90s cut:** trim A3 to 19s, A3b to 10s, A4 to 8s, A6 to 8s.
   Trim A9 to outro half (7s starting around 7.4s).
4. **For director's cut:** use A3 for ~30s, A3b for 15s, A5 for 20s,
   A6 for 14s, A8 for 10s, and A9 outro half.
5. **Subtitles** — single text layer per beat, English only.
   - Style: white text 32–36px, 80% opacity black bar behind
   - Bottom-third placement
   - Each sub on screen ≥2.5s
   - Font: Inter / Helvetica / SF Pro Text
6. **Audio:**
   - Track 1: instrumental music, no vocals, 15–25% gain
   - No voice-over track
7. **Final encode:**
   - 1920×1080 H.264, 30fps, 8–12 Mbps for both versions
   - Sub 80 MB so it uploads anywhere
8. **Watch each version once with subtitles only.** If you can't tell
   what the project does without narration, re-cut.

---

## Recording tips

- **Record clips separately.** Do 2-3 takes of A3 and A3b; choose the
  cleanest one in edit.
- **The strongest beats are FRAME REVISION and COLD-VS-DIRECTED.**
  Slow down there. The viewer needs to see one frame change, then see
  the same direction become memory.
- **Keep subtitles short.** One idea per subtitle. If it needs more
  than two lines, split it into two beats.
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
