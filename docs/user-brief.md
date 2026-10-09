# JUNE — FULL PERSONAL AI OPERATING SYSTEM

You are the lead engineer building **June**, my personal AI operating system.

Do NOT build only a minimal assistant.

Do NOT stop after creating a terminal chatbot.

Do NOT treat voice, vision, computer control, memory, automation, proactivity, browser control, integrations, or agentic behavior as distant roadmap items.

The goal is to build the **full software-level version of June now**.

June should be designed to feel as close as practically possible to JARVIS using currently available software and hardware.

---

# CORE OBJECTIVE

June should become a persistent AI system that:

- talks to me naturally
- hears me continuously when enabled
- responds when I say "June"
- understands what is happening on my computer
- sees my screen
- remembers my life, projects, ideas and decisions
- controls my Windows computer
- opens and operates applications
- works with files
- runs terminal commands
- writes and modifies code
- understands codebases
- uses browsers
- researches the internet
- manages projects
- uses connected services
- maintains tasks and reminders
- understands context across sessions
- performs multi-step tasks
- recovers from failures
- can work proactively
- can trigger actions from events
- can notify me when something important happens
- eventually interfaces with physical devices, sensors and robots

This is not a chatbot project.

June is a **personal AI operating layer**.

---

# SYSTEM ROOT

Use:

D:\June

Keep June's project files, databases, logs, caches, models, indexes, voice assets and runtime data on D: wherever possible.

Do not unnecessarily consume C:.

Use:

D:\June\.venv

for the Python environment.

---

# HIGH-LEVEL ARCHITECTURE

Build June approximately around this architecture:

                          MAYANK
                             |
          +------------------+------------------+
          |                  |                  |
        VOICE               TEXT              VISION
          |                  |                  |
          +------------------+------------------+
                             |
                             v
                    JUNE INTERFACE LAYER
                             |
                             v
                    JUNE AGENT RUNTIME
                             |
            +----------------+----------------+
            |                |                |
            v                v                v
         BRAIN             MEMORY        WORLD MODEL
            |                |                |
            +----------------+----------------+
                             |
                             v
                      PLANNING SYSTEM
                             |
                             v
                   PERMISSION / POLICY
                             |
                             v
                       TOOL EXECUTION
                             |
      +-----------+----------+----------+-----------+
      |           |          |          |           |
    WINDOWS     BROWSER     CODE       WEB      SERVICES
      |           |          |          |           |
      +-----------+----------+----------+-----------+
                             |
                             v
                       EVENT SYSTEM
                             |
                             v
                     PROACTIVE JUNE

Every major subsystem must have a clean interface.

---

# CRITICAL ARCHITECTURAL RULE

OpenAI is TEMPORARY.

OpenAI must not define June's identity or core architecture.

Create an abstract intelligence interface such as:

JuneBrain

with capabilities such as:

respond()
reason()
plan()
choose_tools()
interpret_observation()
extract_memory()
summarize()
analyze_image()
process_audio()

Initially:

OpenAIBrain implements JuneBrain.

Eventually:

LocalJuneBrain implements JuneBrain.

Everything else should remain functional when OpenAI is replaced.

The final goal is to remove external AI providers entirely.

---

# 1. JUNE CORE

Create a central runtime responsible for:

- session lifecycle
- identity
- context
- memory retrieval
- model interaction
- tool selection
- tool execution
- permission checks
- observation
- replanning
- memory writing
- event handling
- proactive behavior
- notifications
- subsystem coordination

Do NOT spread orchestration logic randomly across modules.

Create a clear June runtime.

---

# 2. AGENTIC EXECUTION LOOP

June must operate using a real agent loop.

Conceptually:

USER / EVENT
      |
      v
UNDERSTAND
      |
      v
RETRIEVE CONTEXT
      |
      v
FORM CURRENT WORLD STATE
      |
      v
PLAN
      |
      v
SELECT ACTION
      |
      v
CHECK PERMISSION
      |
      v
EXECUTE
      |
      v
OBSERVE RESULT
      |
      v
IS GOAL COMPLETE?
      |
   NO +----> REPLAN
      |
     YES
      |
      v
RESPOND / ACT
      |
      v
UPDATE MEMORY

Support many tool calls during one task.

Support bounded autonomous loops.

Prevent infinite loops.

---

# 3. VOICE

Voice is a core feature, not an optional future feature.

Build a voice interface capable of:

- microphone input
- speech detection
- wake word
- wake phrase: "June"
- speech-to-text or realtime audio reasoning
- natural spoken responses
- interruptions
- stopping June while she is speaking
- hands-free operation
- configurable always-listening mode
- push-to-talk fallback
- microphone mute
- visible microphone status

Example:

Mayank:
"June."

June:
"Yeah?"

Mayank:
"Open Galileo and tell me where I stopped."

June should retrieve project context, open it and answer.

Voice must be modular so speech components can later be replaced with our own local speech models.

---

# 4. SCREEN VISION

June should be able to understand my screen.

Implement a screen-perception subsystem capable of:

- screenshots
- selecting active monitor
- capturing active window
- detecting active application
- analyzing screenshots
- providing visual observations to June
- allowing commands such as:

"What's wrong here?"

"What does this error mean?"

"Click the button on the right."

"Look at this."

"Why isn't this working?"

Vision must not continuously upload screenshots without deliberate configuration.

Provide privacy controls.

---

# 5. COMPUTER CONTROL

June should be able to control Windows.

Capabilities should include, where technically reasonable:

- open applications
- close applications
- focus windows
- open paths
- navigate folders
- manipulate files
- use clipboard
- type text
- use keyboard shortcuts
- mouse movement
- clicking
- scrolling
- screenshots
- terminal commands
- PowerShell
- inspect running processes
- start processes
- monitor processes

Prefer structured APIs and direct tools over fragile GUI automation whenever possible.

GUI control should be a fallback when a proper API/tool does not exist.

---

# 6. COMPUTER-USE LOOP

For GUI actions implement:

observe screen
    ↓
understand UI
    ↓
choose action
    ↓
permission check
    ↓
perform action
    ↓
capture screen
    ↓
verify outcome
    ↓
continue

Never assume a click succeeded.

Observe afterwards.

---

# 7. BROWSER

June needs browser capabilities.

Support:

- opening URLs
- searching
- navigating pages
- reading page content
- tabs
- forms
- scrolling
- interacting with websites
- downloading permitted files
- extracting useful information
- research workflows
- browser screenshots where needed

Use browser automation such as Playwright where appropriate.

Keep browser actions auditable.

Do not allow arbitrary external submissions without permission policies.

---

# 8. WEB RESEARCH

June should be able to conduct multi-step research.

Example:

"June, research the latest approaches to humanoid robot flight and make me a summary."

Possible loop:

search
→ open sources
→ inspect information
→ compare sources
→ collect evidence
→ summarize
→ store useful project context

Separate:

web research

from

browser interaction.

---

# 9. FILE SYSTEM

Build robust file tools.

At minimum:

list_directory()

read_file()

write_file()

append_file()

create_file()

create_directory()

move_file()

rename_file()

copy_file()

search_files()

find_text()

get_metadata()

delete_file()

Deleting should have stricter permissions.

Support common text/code formats.

Binary handling should fail safely.

---

# 10. PROJECT AWARENESS

Projects are first-class objects.

Maintain a project registry.

Fields should include:

id

name

aliases

description

root_path

status

technologies

repositories

current_goal

next_actions

recent_activity

important_files

commands

created_at

updated_at

Examples:

Galileo

June

Intelligence Layer

other future projects

Commands should work naturally:

"Open Galileo."

"What's unfinished?"

"Where did I stop?"

"Run it."

"Fix the current error."

"Show me what changed yesterday."

"Continue working."

"Remember this as the next task."

---

# 11. CODING AGENT

June should be capable of helping build software.

Capabilities:

- inspect repositories
- understand project structure
- read source code
- search symbols/text
- inspect Git status
- inspect diffs
- edit code
- create code
- run builds
- run tests
- inspect failures
- debug
- retry
- explain results
- preserve working code
- avoid rewriting entire projects unnecessarily

Agent flow:

understand requested change
→ inspect repo
→ identify relevant files
→ plan
→ modify minimal code
→ run tests/build
→ inspect failures
→ fix
→ verify
→ report

Git support should include:

git status

git diff

git log

branch information

Do not automatically perform destructive Git operations.

---

# 12. TERMINAL

Provide a shell tool with:

command

working directory

timeout

environment

stdout

stderr

return code

duration

June must inspect command results before proceeding.

Never give the model unrestricted administrator access.

Block or request approval for dangerous commands.

---

# 13. LONG-TERM MEMORY

June should have sophisticated persistent memory.

Store locally.

Initial implementation may use:

SQLite

plus appropriate indexes.

Design for later migration to stronger databases if required.

Memory categories:

## Identity

Who I am and high-level stable information.

## Preferences

How I like things done.

## People

People in my life and relevant context.

## Projects

My ongoing work.

## Goals

Long-term and short-term goals.

## Tasks

Things I need to do.

## Decisions

Important choices and why they were made.

## Events

Things that happened.

## Ideas

Things I have thought about.

## Knowledge

Useful learned context.

## Conversations

Historical discussions.

## Routines

Repeated behaviors or schedules.

## Environment

Important information about my machines and setup.

---

# 14. MEMORY QUALITY

Do not dump every conversation into long-term memory.

Implement:

memory candidate extraction

importance estimation

deduplication

merging

updating

forgetting/deprioritization

retrieval

source tracking

timestamps

confidence

June should distinguish:

something I explicitly told June to remember

from

something inferred tentatively.

Explicit memories should have stronger persistence.

---

# 15. SEMANTIC MEMORY

Add semantic retrieval.

June should be able to answer:

"What was that wireless-power thing I discussed?"

"What was my idea for the flying humanoid?"

"What did I decide about Galileo?"

"What was I working on last week?"

Use embedding/vector retrieval or another replaceable semantic indexing layer.

The semantic-memory provider should also be modular so we can eventually replace any external embedding dependency.

---

# 16. WORKING MEMORY

June should maintain a short-term working context separate from long-term memory.

Track:

current conversation

current task

current project

active applications

recent tool outputs

temporary observations

current plan

unresolved questions

This state should prevent June from repeatedly rediscovering the same information.

---

# 17. WORLD MODEL / STATE

Create a structured representation of June's current understanding of my environment.

Possible fields:

active_project

active_window

running_apps

current_task

recent_files

recent_commands

pending_jobs

scheduled_events

recent_notifications

known_device_state

Do not claim state that has not actually been observed.

---

# 18. TASK SYSTEM

Create a persistent task manager.

Tasks should have:

title

description

status

priority

project

deadline

dependencies

created_at

updated_at

source

June should understand:

"Remind me to work on Galileo tomorrow."

"What's unfinished?"

"Mark that as done."

"What's most urgent?"

---

# 19. SCHEDULER

June should support scheduled actions.

Examples:

"Remind me at 6 PM."

"Run this check tomorrow."

"Tell me every morning what I need to do."

"At 8 PM remind me to stop working."

Use a reliable scheduler.

Persist scheduled jobs across application restarts.

---

# 20. EVENT SYSTEM

June must not depend exclusively on user prompts.

Create an event bus.

Possible events:

app_started

app_closed

file_changed

project_changed

git_change

task_due

timer

calendar_event

email_event

download_finished

build_finished

test_failed

system_warning

user_activity

sensor_event

The architecture should allow new event producers.

---

# 21. PROACTIVE JUNE

Create a proactive engine.

June should be able to notice events and determine whether I need to know.

Example:

Build completes.

Instead of doing nothing:

June:
"Your Galileo build finished. Three tests failed."

Another example:

A task is due.

June:
"You planned to work on the black-hole renderer today."

Do NOT turn this into constant notifications.

Implement:

relevance threshold

urgency

importance

cooldowns

notification suppression

quiet mode

---

# 22. NOTIFICATION SYSTEM

Support at minimum:

desktop notification

terminal notification

spoken notification when voice mode is enabled

Keep notification delivery modular.

---

# 23. EMAIL

Create an email integration interface.

Eventually support:

read inbox

search

summarize threads

draft replies

send email

identify important emails

extract tasks/events

Sending messages must follow external-action permission policies.

Provider-specific implementations must remain separate from June core.

---

# 24. CALENDAR

Calendar integration should support:

view schedule

understand upcoming meetings

create events

modify events

reminders

meeting preparation

Example:

"What's happening tomorrow?"

or:

"Prepare me for my 3 PM meeting."

---

# 25. GITHUB

Support GitHub integration where available.

Possible capabilities:

repositories

issues

pull requests

commits

notifications

project context

Again, provider implementation must remain modular.

---

# 26. EXTERNAL SERVICES

Create an integration framework rather than hardcoding every service.

Concept:

Integration

connect()

disconnect()

capabilities()

execute()

health()

credentials should never be exposed directly to the model.

---

# 27. CREDENTIAL VAULT

Build a safe credential-handling layer.

Requirements:

- secrets outside source code
- secrets outside model prompts whenever possible
- encrypted local storage or OS credential facilities
- redaction
- least privilege
- token expiration handling
- revocation

Never log secrets.

---

# 28. PERMISSION SYSTEM

This is mandatory.

Use explicit risk levels.

LEVEL 0 — OBSERVE

Examples:

read file

view calendar

inspect repository

capture screen

LEVEL 1 — SAFE LOCAL ACTION

open folder

open application

run known safe command

LEVEL 2 — LOCAL MODIFICATION

edit file

create file

modify project

LEVEL 3 — EXTERNAL ACTION

send email

post online

submit form

message somebody

LEVEL 4 — SENSITIVE ACTION

financial activity

password/authentication changes

security configuration

system administrator changes

destructive operations

LEVEL 5 — CRITICAL

actions that could cause major irreversible harm

Require explicit user authorization.

Permission decisions must happen outside the model's unrestricted control.

---

# 29. ACTION PREVIEW

For sensitive operations June should provide a concise preview.

Example:

"You're about to permanently delete 312 files from D:\Projects\OldProject. Continue?"

Then require explicit confirmation.

---

# 30. AUDIT SYSTEM

Record meaningful actions.

Store locally.

Each audit entry may include:

timestamp

trigger

request

current project

action

tool

sanitized parameters

permission level

result

success/failure

duration

Never store secrets in logs.

---

# 31. PERSONALITY

June should feel intelligent and natural.

Personality:

calm

concise

capable

direct

curious when appropriate

not corporate

not excessively enthusiastic

not constantly apologizing

not robotic

not fake-emotional

not sycophantic

June should understand:

"I am June, Mayank's personal AI system."

But personality must be configurable data rather than deeply embedded application logic.

---

# 32. INTERFACE

Create a central June application.

At minimum include:

## Terminal interface

For debugging and direct operation.

## Desktop interface

A lightweight always-available UI.

Useful elements may include:

June status

microphone status

current task

notifications

conversation

active project

permissions awaiting approval

recent actions

settings

Do not spend excessive time on flashy UI before functionality works.

---

# 33. JUNE TRAY APPLICATION

Consider running June from the Windows system tray.

Possible actions:

Talk to June

Mute microphone

Pause automation

Open June

Current task

Privacy mode

Exit

---

# 34. PRIVACY MODE

Provide an immediate way to disable:

microphone

screen capture

camera

external connections

proactive activity

Ideally one command:

"June, privacy mode."

June should visibly confirm the state.

---

# 35. CAMERA / PHYSICAL VISION

Architect a camera input system.

Do not assume a camera is always active.

When enabled, allow visual analysis of explicitly available camera input.

Camera permissions must be transparent and controllable.

---

# 36. SMART HOME / DEVICES

Create a generic device-control layer.

Possible future devices:

lights

speakers

AC

displays

cameras

sensors

microcontrollers

robots

Do not hardwire June to one specific ecosystem.

Create abstractions such as:

Device

Sensor

Actuator

Command

State

---

# 37. ROBOTICS INTERFACE

Architect but do not fake hardware functionality.

Possible future robot API:

robot.status()

robot.move()

robot.stop()

robot.look_at()

robot.navigate()

robot.inspect()

robot.return_home()

Safety-critical physical actions will require dedicated hardware safety systems outside the language model.

---

# 38. BACKGROUND SERVICES

June should have a reliable way to remain active even when the main UI is closed.

Design a background runtime/service where appropriate.

Responsibilities may include:

scheduled tasks

event listeners

notifications

memory maintenance

integration polling

local API

voice wake system

Do not consume excessive CPU when idle.

---

# 39. LOCAL API

Create a local-only June API so components can communicate cleanly.

Bind locally by default.

Do not expose June publicly to the internet.

Require authentication if network exposure is ever enabled.

---

# 40. MODULE COMMUNICATION

Avoid giant tightly coupled modules.

Use clear contracts between:

brain

memory

agent

tools

events

voice

vision

integrations

UI

permissions

notifications

automation

---

# 41. OBSERVABILITY

Implement internal health monitoring.

Track:

system status

model availability

database

tool failures

event queue

background jobs

voice state

integration state

resource usage

Provide useful logs without leaking secrets.

---

# 42. ERROR RECOVERY

June should gracefully recover from:

model timeout

tool failure

file missing

application missing

browser crash

network failure

invalid command

database issue

microphone failure

voice failure

screen capture failure

integration disconnect

Do not crash the entire June runtime because one subsystem failed.

---

# 43. AUTONOMOUS TASKS

Support tasks that require multiple minutes and many steps.

Example:

"Inspect Galileo and fix the current build problem."

June should be capable of:

inspecting project

running build

reading error

locating code

editing

building again

running tests

checking result

reporting completion

Use reasonable maximum step budgets.

---

# 44. TASK CANCELLATION

I must be able to say:

"June, stop."

"Cancel that."

"Don't do that."

The currently executing autonomous task should stop safely.

---

# 45. INTERRUPTIBILITY

Voice and agent tasks should be interruptible.

If June is speaking and I start talking, allow interruption where supported.

If June is performing a long action, I should be able to override it.

---

# 46. CONCURRENCY

June may eventually perform several background jobs.

Build a task execution system that can track:

queued

running

waiting_for_permission

completed

failed

cancelled

Avoid uncontrolled parallel execution.

---

# 47. LOCAL DATA OWNERSHIP

June's own data belongs to me.

Store locally wherever practical:

memory

projects

logs

preferences

agent state

task state

conversation history

indexes

configuration

provider-independent identity

---

# 48. OPENAI DATA SEPARATION

Because this prototype temporarily uses OpenAI:

make it possible to understand which data is:

local only

sent to the model

sent to another external integration

Provide centralized context assembly.

Do not automatically send my entire memory database to the model.

Retrieve only what is relevant.

---

# 49. PROVIDER ABSTRACTION

Create interfaces for:

BrainProvider

SpeechProvider

VisionProvider

EmbeddingProvider

SearchProvider

BrowserProvider if needed

The initial implementations may depend on external systems.

But June should ultimately be able to replace all of them.

---

# 50. FINAL INDEPENDENCE GOAL

Eventually the following should all be ours:

June language model

June reasoning model

June embeddings

June speech recognition

June speech generation

June visual understanding

June memory

June agent runtime

June tools

June interfaces

June device layer

At that point:

NO OpenAI inference dependency

NO Anthropic inference dependency

NO Google inference dependency

NO other external AI provider required for June's intelligence.

Internet access becomes something June MAY USE.

Internet access must not be something June REQUIRES TO EXIST.

---

# 51. DEVELOPMENT STRATEGY

Although the FULL architecture is the target now, still implement it incrementally.

This means:

build

run

test

continue

Do not write the entire repository without executing anything.

Do not stop after the first milestone either.

Continue through the complete software-level architecture requested here.

If one subsystem depends on unavailable credentials or hardware:

create the real interface

implement everything that can be implemented

document exactly what external configuration is missing

continue building the rest of June

Do not use missing integrations as a reason to stop the project.

---

# 52. PRIORITY ORDER

Build in this engineering order:

CORE RUNTIME

↓

BRAIN ABSTRACTION

↓

MEMORY

↓

TOOLS

↓

PERMISSIONS

↓

AGENT LOOP

↓

WINDOWS CONTROL

↓

PROJECT + CODING SYSTEM

↓

SCREEN VISION

↓

VOICE

↓

BROWSER + WEB

↓

TASKS + SCHEDULER

↓

EVENT BUS

↓

PROACTIVITY

↓

DESKTOP/TRAY UI

↓

INTEGRATIONS

↓

DEVICE ABSTRACTION

↓

HARDENING + TESTING

But continue through the list.

Do not stop because an earlier subsystem is merely "good enough for V0.1."

---

# 53. REAL FUNCTIONAL TEST

The end system should support an interaction approximately like this:

Mayank:

"June."

June:

"Yeah?"

Mayank:

"What was I doing with Galileo?"

June checks memory and responds.

Mayank:

"Open it."

June opens the project.

Mayank:

"See why it isn't running."

June:

- examines project state
- runs the project/build
- examines errors
- looks at relevant files

June explains the issue.

Mayank:

"Fix it."

June:

- requests permission if needed
- modifies code
- runs build/tests
- observes results
- fixes remaining errors
- reports outcome

Mayank:

"Remember that tomorrow I want to work on the black-hole simulation."

June stores the memory and creates the task if appropriate.

Tomorrow:

June can proactively surface that information.

---

# 54. SECOND FUNCTIONAL TEST

I should be able to say:

"June, look at my screen."

June captures the current screen.

Then:

"What is this error?"

June analyzes what is actually visible.

Then:

"Fix it."

June determines whether it should:

use terminal

edit code

use GUI

use browser

or ask for permission.

---

# 55. THIRD FUNCTIONAL TEST

I should be able to say:

"June, research flying humanoid robots and store anything useful under my robotics project."

June should:

search

research multiple sources

summarize

associate the result with the project

store useful knowledge

tell me what it found.

---

# 56. FOURTH FUNCTIONAL TEST

I should be able to say:

"June, what needs my attention?"

June should inspect available:

tasks

projects

deadlines

calendar

events

background jobs

notifications

and return a concise prioritized situational briefing.

Do not invent unavailable information.

---

# 57. FIFTH FUNCTIONAL TEST

June should survive application restarts.

After restarting the computer or June:

June should still know:

registered projects

persistent memories

tasks

preferences

events

scheduled jobs

configuration

conversation history where appropriate.

---

# 58. SECURITY TESTING

Test against:

destructive shell commands

path traversal

prompt injection inside files

malicious web content

secret leakage

unauthorized external actions

accidental recursive deletion

uncontrolled agent loops

very large files

command injection

unexpected GUI states

---

# 59. TEST SUITE

Build real tests for:

brain interfaces

memory

retrieval

memory deduplication

projects

tool registry

permissions

file operations

shell

Windows tools

screen capture

agent loop

tool retries

task cancellation

scheduler

event bus

notifications

audit logs

configuration

secret redaction

integration interfaces

failure recovery

---

# 60. README + ARCHITECTURE DOCUMENTATION

Maintain:

README.md

docs\architecture.md

docs\security.md

docs\memory.md

docs\tools.md

docs\voice.md

docs\vision.md

docs\automation.md

docs\integrations.md

docs\local-model-migration.md

Keep documentation synchronized with working code.

---

# 61. DO NOT FAKE CAPABILITIES

Never produce UI that pretends a capability works when no real backend exists.

If something is unavailable:

show:

Unavailable / Not configured

not:

Done.

June must distinguish:

success

failure

unknown

permission denied

not configured.

---

# 62. DO NOT STOP AT SCAFFOLDING

A directory tree is not completion.

Interfaces with `pass` are not completion.

TODO comments are not completion.

Mock buttons are not completion.

Implement working capabilities wherever the machine/environment allows.

Run them.

Test them.

Fix them.

---

# 63. USE EXISTING REPOSITORY STATE

If D:\June already contains work:

inspect it first.

Do NOT regenerate the whole project.

Preserve working components.

Refactor only when necessary.

Continue from the current state.

---

# 64. ENGINEERING AUTHORITY

You have authority to:

create project files

install normal development dependencies in D:\June\.venv

write code

run development commands

run tests

debug failures

create local databases

create documentation

refactor June's code

Do NOT make sensitive system-level/security/financial/external actions without explicit permission.

---

# 65. COMPLETION DEFINITION

The project is not considered complete merely because June can chat.

The full prototype is considered substantially complete when June has working implementations for:

[ ] natural text interaction

[ ] voice interaction

[ ] wake phrase

[ ] persistent local memory

[ ] semantic memory

[ ] project awareness

[ ] tasks

[ ] Windows tools

[ ] file tools

[ ] terminal tools

[ ] coding workflows

[ ] screen capture

[ ] screen understanding

[ ] computer interaction

[ ] browser automation

[ ] web research

[ ] scheduling

[ ] event architecture

[ ] proactive notifications

[ ] background runtime

[ ] permission system

[ ] audit logging

[ ] cancellation

[ ] provider abstraction

[ ] desktop/tray experience

[ ] integration framework

[ ] device abstraction

[ ] comprehensive tests

[ ] documentation

Actual service integrations requiring my credentials can be marked "ready for connection" rather than fabricated.

Actual physical robots/devices can be represented through real integration interfaces until hardware exists.

---

# 66. START NOW

Inspect:

D:\June

Determine what already exists.

Then begin implementation.

Your job is not to tell me how to build June.

Your job is to **build June**.

Continue through the complete architecture described above.

Run and test each subsystem as you go.

Fix problems instead of restarting.

The result should be the closest software-level approximation of JARVIS that can reasonably operate on this Windows machine today, while remaining architecturally ready for the future replacement of all external AI intelligence with our own June models.