# Deal Desk

**Sales asks, agents check, and only the finance lead can sign, all in team chat, built on [Switch](https://github.com/sandbox-quantum/switch).**

A sales rep needs a deal signed today: 35% off, unlimited liability, and cancel-any-time with a refund. Deal Desk puts the pricing and legal checks in the chat the rep already uses, hands the full case to finance in a private room, and lets only the finance lead issue the order form.

Built for the Flip the Switch hackathon, Track 01 (Best Business Workflow). Lumen Analytics, its prices, its customers and its people are fictional.

[Demo video](https://youtu.be/9iczSCaXYvM) · Built and tested on Switch Console 0.40.1, server 0.31.0, Windows, Mattermost

```
 #deal-desk-sales  (public)                    #deal-desk-finance  (private)
 ┌──────────────────────────────────┐          ┌──────────────────────────────────┐
 │ Tom (rep)                         │          │ Alice (finance lead, owner)      │
 │ @deal-desk   takes the deal  ─────┼─ handoff ┼─▶ @deal-desk  full numbers        │
 │ @pricing     verdict only         │          │                                  │
 │ @legal       clause review        │          │ @order-desk  issues order form   │
 │ @order-desk  refuses Tom ✗        │ ◀─ approved terms (no internal numbers) ─  │
 └──────────────────────────────────┘          └──────────────────────────────────┘
```

## What enforces what

This is the part that matters, so here it is first.

| Rule | Enforced by | How |
|---|---|---|
| Only the finance lead can instruct Order Desk | **Switch** | `lumen-order-desk` is set to **Only me**. Tom's request is refused before the model runs. |
| The rep can't read the finance room | **Switch and Mattermost** | `#deal-desk-finance` is a private channel. Room membership decides what a person or agent can read. |
| Pricing and Legal can't see finance discussions | **Switch** | They aren't members of `#deal-desk-finance`, so they can't read it. |
| Prices come from the price list, not the model | **Our code** | `tools/pricing.py` does every calculation; agents run it and quote it. |
| Nobody can sign below the margin floor, and a rep can't approve finance-level terms | **Our code** | `tools/order_form.py` reruns the pricing check on the approved terms and refuses if the approver's role is too low or a hard rule breaks. |
| Margins, costs and the floor stay out of the sales room | **Agent instructions only** | Deal Desk is in both rooms so context can cross. Keeping finance numbers out of sales depends on it following its brief. Pricing only ever runs `--verdict-only` in sales. |

### What breaks without Switch

| Switch feature | Without it |
|---|---|
| Per-agent "who can talk to your agent" | Anyone in the chat could tell the agent to issue a contract. |
| Rooms with membership | Every agent would see every conversation, including finance's. |
| One agent in two rooms | Finance would need the rep to retell the deal, or someone to copy and paste it. |
| Separate agents with separate briefs and folders | One bot with clashing goals (close the deal vs protect margin vs limit risk). |
| Room aliases (`@pricing`, `@legal`) | People address agents by their internal names. |

## We tried to break it

| Attempt | Result | What stopped it |
|---|---|---|
| Rep tells Order Desk to approve his own deal | Refused | Switch addressing (Only me) |
| Another of our agents tells Order Desk to issue a form | Refused | Switch addressing (Only me) |
| An agent outside a room is asked what was said in it | "I'm not a member, so I can't read it" | Switch room membership |
| Rep opens the finance channel's URL | No access | Private Mattermost channel |
| Finance lead approves 35%, below the floor | REFUSED by the script | `tools/order_form.py` |
| Rep asks for the lowest possible discount | Declined | Agent instructions only |

## How a deal flows

1. **Tom** posts the deal to `@deal-desk` in `#deal-desk-sales`.
2. **Deal Desk** restates it as JSON and asks `@pricing` and `@legal`.
3. **Pricing** runs `tools/pricing.py --verdict-only`: accept, reject or counter, with no internal numbers.
4. **Legal** checks each clause against `data/legal_playbook.md`: Standard, Fallback or Never.
5. **Deal Desk** sums up for Tom and posts a handoff in `#deal-desk-finance` with the deal JSON, the full pricing output (margin, floor, maximum discount) and legal's findings.
6. **Alice** approves specific terms to `@lumen-order-desk`.
7. **Order Desk** writes an approval record, runs `tools/order_form.py` and posts the order form, or the reason it refused.
8. **Deal Desk** tells Tom the approved terms, without internal numbers.

## Setup (about 30 minutes)

You need Switch Console with a local server, Docker, Python 3.9+, git, and Claude Code (Codex or OpenCode should also work, untested).

1. **Start Switch.** In Switch Console: Get started → On this computer → Start. Mattermost comes with it.
2. **Get the project for each agent.**
   ```
   git clone https://github.com/oscarosk/deal-desk lumen-deal-desk
   git clone https://github.com/oscarosk/deal-desk lumen-pricing
   git clone https://github.com/oscarosk/deal-desk lumen-legal
   git clone https://github.com/oscarosk/deal-desk lumen-order-desk
   ```
3. **Create the four agents** in Your Agents. Paste each one's instructions from `agents/<name>.md`, and set its directory to its clone.

   | Agent | Who can talk to your agent |
   |---|---|
   | `lumen-deal-desk` | Anyone |
   | `lumen-pricing` | Anyone |
   | `lumen-legal` | Anyone |
   | `lumen-order-desk` | **Only me** |

4. **Create the sales room** in Your Rooms: Mattermost, `deal-desk-sales`, all four agents.
5. **Create the finance room in Mattermost** as a **private** channel named `deal-desk-finance`, then add `lumen-deal-desk` and `lumen-order-desk` to it. This makes it a Switch room. (Rooms created from Console were public, and Mattermost wouldn't let us change their type.)
6. **Add short names** in each room, for example `!set-alias @lumen-pricing @pricing`.
7. **Add a rep.** Create a second Mattermost account (we used `tom`) from the team invite link and join `#deal-desk-sales`. It doesn't need a Switch account.
8. **Run the demo deal** in `docs/demo-script.md`.

`switch/deal-desk.template.yaml` describes the same setup as a Switch template. See Known limits before using it.

## Run the tests

```
python -m unittest discover -s tests
```

14 tests cover the pricing rules, the verdict-only mode (no internal numbers leak), and the order form's refusals. `python tools/reset_demo.py` clears generated deals, approvals and order forms between runs.

## Project layout

```
agents/      each agent's instructions
data/        price list, legal playbook, sample deal (all fictional)
tools/       pricing.py, order_form.py, reset_demo.py
tests/       unit tests for the tools
switch/      the Switch template for the whole setup
docs/        demo script
```

## Known limits

- **The information barrier relies on instructions.** Deal Desk reads both rooms. Switch doesn't stop it from repeating finance numbers in sales; its brief does. In testing, an agent in two rooms declined to repeat a secret across them, but that's the model's judgment, not a guarantee.
- **One owner.** On a Console-run local server only the person running it can own agents, so Alice owns all four. Tom is a separate chat account with no Switch account. Separate owners would need a team-hosted Switch server.
- **The template didn't run on Windows.** Console 0.40.1 on Windows reported "Not supported here" for every provider in the template form, though Claude Code was installed, signed in and running agents created by hand. We built the setup manually; the template is included but untested.
- **Agent wording varies between runs.** The decisions come from scripts, so they're stable; the phrasing isn't.
- **The order form is Markdown,** written to `out/<deal_id>.md` and posted in the room. It's not a signed PDF or a CRM record.
- **Fictional data.** The prices, margin floor and playbook are made up to be realistic, not taken from any real company.
- **No prompt-injection protection.** Switch Rooms doesn't provide it. What limits damage here is who each agent accepts instructions from and which rooms it can read.

## How AI was used

Claude helped plan the idea, research Switch's docs, and draft the scripts, tests, agent instructions and this README. I set up and configured Switch, ran every test in the rooms, chose the design changes from what those tests showed, and reviewed the code and outputs. The four agents in the demo run on Claude Code.

The demo voiceover was generated with ElevenLabs from my script.
