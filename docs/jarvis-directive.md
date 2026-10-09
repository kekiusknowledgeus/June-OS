CONTINUE BUILDING JUNE — TARGET: 80% PRACTICAL DESKTOP JARVIS

Continue from the EXISTING D:\June repository.

DO NOT restart the project.
DO NOT regenerate working modules.
DO NOT remove functioning features simply because you would implement them differently.

First inspect the current repository, README, validation documentation, tests, provider configuration, memory system, Windows tools, voice, vision, browser, scheduler, event bus, desktop/tray application and existing integrations.

Then continue implementation toward the following target:

============================================================
MISSION
============================================================

June should become a persistent personal AI operating layer that feels approximately like a practical software version of JARVIS.

The target is NOT fictional superintelligence.

The target is this experience:

I can be anywhere on my Windows computer and say:

"June."

June immediately understands that I am speaking to her.

I can then say things such as:

"Continue what I was doing last night."

"Look at this."

"Fix this."

"Open Galileo."

"Research this for me."

"Watch this build and tell me when it finishes."

"Prepare everything I need tomorrow."

"What needs my attention?"

"Remember this."

"Find that idea I had two months ago."

"Show me your brain."

"Stop."

June should understand the context, perform appropriate actions, remember relevant information and report the result.

============================================================
1. FIRST PRIORITY: MAKE EXISTING FEATURES WORK TOGETHER
============================================================

Do NOT prioritize adding dozens of new capabilities.

The highest priority now is END-TO-END RELIABILITY.

The following subsystems already exist or partially exist:

- brain provider
- agent runtime
- local memory
- project registry
- tasks
- Windows tools
- file tools
- shell tools
- browser
- voice
- screen capture
- GUI control
- scheduler
- events
- desktop/tray interface
- permissions
- audit logging
- integration adapters

Connect these into coherent user experiences.

For example:

VOICE
    ↓
June understands request
    ↓
retrieves memory
    ↓
understands active computer context
    ↓
plans task
    ↓
requests tools
    ↓
permission engine
    ↓
executes
    ↓
observes result
    ↓
replans if necessary
    ↓
finishes
    ↓
updates memory
    ↓
speaks/responds

The complete path must work.

============================================================
2. GEMINI BRAIN
============================================================

Use Gemini as the temporary reasoning backend.

Load:

GEMINI_API_KEY

from:

D:\June\.env.local

Gemini remains a replaceable implementation of JuneBrain.

Do not tightly couple June to Gemini.

Architecture remains:

JuneBrain
    |
    +-- GeminiBrain
    +-- LocalJuneBrain
    +-- optional other providers

Gemini chooses actions.

Gemini NEVER directly executes actions.

All execution remains controlled by June's host-side runtime and permission engine.

============================================================
3. UNIVERSAL SUMMONING
============================================================

Make June available from anywhere on Windows.

Implement or finish:

- global keyboard shortcut
- small overlay
- tray icon
- voice wake phrase
- Windows notifications
- background runtime
- optional launch at login

Recommended default global shortcut:

Ctrl + Space

but make it configurable.

Pressing it should produce a lightweight June overlay without changing my current application.

Example:

I am inside Unreal Engine.

Ctrl + Space

A small June overlay appears.

I type:

"Why isn't this building?"

June should automatically know which app/project is currently active where possible.

============================================================
4. WAKE WORD
============================================================

Wake phrase:

"June"

I should be able to say:

"June."

June responds.

Then:

"Open Galileo."

June executes.

Requirements:

- low idle CPU usage
- configurable always listening
- visible microphone indicator
- mute
- push-to-talk fallback
- privacy mode
- interruption/barge-in

Never hide microphone state.

============================================================
5. CONVERSATIONAL CONTINUITY
============================================================

June must handle follow-up language naturally.

Example:

Me:
"Open Galileo."

June opens it.

Me:
"Run it."

June understands "it" = Galileo.

Me:
"Why did that fail?"

June understands "that" = the previous run.

Me:
"Fix it."

June understands which failure and which project.

Me:
"Try again."

June reruns the appropriate operation.

Do not require me to repeatedly provide full context.

Maintain structured working memory.

============================================================
6. ACTIVE CONTEXT ENGINE
============================================================

Build/finish a CurrentContext object.

Possible state:

current_project

active_application

active_window

active_file

current_task

recent_tool_calls

recent_command

recent_error

recent_screen_observation

recent_webpage

current_conversation

current_plan

pending_permission

running_jobs

Use observed data whenever possible.

Never fabricate context.

Track confidence/source.

============================================================
7. "CONTINUE WHERE I LEFT OFF"
============================================================

Implement this as a flagship feature.

Example:

"June, continue where I left off."

June should inspect:

recent project memory

recent files

Git state

tasks

previous commands

recent errors

stored conversation state

recent project events

Then infer the likely unfinished work.

If confidence is sufficient:

present it:

"You were debugging Galileo's black-hole renderer. The last build failed in X."

Then ask:

"Continue?"

or continue automatically if configured.

If uncertain, show the likely options instead of hallucinating.

============================================================
8. SCREEN INTELLIGENCE
============================================================

Make:

"June, look at this."

reliable.

Flow:

capture active window
    ↓
identify application
    ↓
vision analysis
    ↓
associate with current task/project
    ↓
answer

Example:

Unreal Engine shows compilation error.

Me:
"June, look at this."

June reads the error.

Me:
"Fix it."

June identifies repository/project, reads relevant source files, edits after policy approval, runs build and verifies.

Screen understanding must integrate with the agent loop.

============================================================
9. GUI AGENT
============================================================

Build a reliable observe-act-observe loop.

Never perform:

click()
click()
click()
click()

without observing.

Correct:

observe
    ↓
identify target
    ↓
click
    ↓
wait
    ↓
observe
    ↓
verify
    ↓
next action

Include safeguards against stale screenshots.

Before important actions, verify:

active window

target state

coordinates/UI element

============================================================
10. STRUCTURED APP CONTROL
============================================================

Avoid using mouse automation when a better API exists.

Preference order:

1. direct API
2. local application integration
3. CLI
4. browser automation
5. accessibility/UI automation
6. coordinate-based clicking

Create application adapters where useful.

Potential initial adapters:

VS Code

PowerShell/Terminal

File Explorer

browser

Git

Unreal Engine where feasible

Do not attempt to build adapters for every Windows application.

Make adapter system extensible.

============================================================
11. CODING MODE
============================================================

Create a specialized coding-agent workflow.

Command:

"June, fix this project."

Pipeline:

identify project

inspect Git status

understand build system

run build/tests

collect errors

rank likely causes

inspect relevant files

create minimal patch

request approval if needed

apply patch

build/test

inspect new output

repeat within bounded limits

verify

summarize exact changes

Do not stop simply after editing code.

Verification is mandatory.

============================================================
12. BACKGROUND JOBS
============================================================

June must be able to execute work while I continue using the computer.

Example:

"June, fix the Galileo build and tell me when you're finished."

Immediately return control to me.

Dashboard:

June Tasks

● Galileo build repair
  Running

Later:

Windows notification:

June
Galileo now builds successfully.

Store task state persistently.

States:

queued
running
paused
waiting_for_permission
waiting_external
completed
failed
cancelled

============================================================
13. TASK CANCELLATION
============================================================

Global commands:

"June, stop."

"Cancel."

"Stop that task."

"Pause everything."

must work reliably.

Cancel:

agent loop

subprocesses where appropriate

browser automation

queued actions

speech

without corrupting project state.

============================================================
14. PROACTIVE INTELLIGENCE
============================================================

June should not only react.

Build a restrained proactive engine.

Examples:

"You wanted to work on Galileo today."

"Your build finished."

"Your reminder is due."

"Your meeting begins in 30 minutes."

"This background task failed."

Avoid excessive notifications.

Score potential notifications by:

urgency

importance

relevance

confidence

novelty

time sensitivity

Use cooldowns and duplicate suppression.

============================================================
15. "WHAT NEEDS MY ATTENTION?"
============================================================

Implement this as another flagship command.

June should inspect available:

tasks

deadlines

calendar

projects

running jobs

failed jobs

important events

reminders

recent messages if integrations are enabled

Then provide something like:

Needs attention:

1. Galileo build failed.
2. Robotics research task is due today.
3. Meeting at 4 PM.
4. June background update finished.

Only report real available data.

============================================================
16. MEMORY — MAKE IT USEFUL
============================================================

Improve long-term memory quality.

Each memory should have appropriate metadata:

content

type

source

confidence

importance

created_at

updated_at

last_accessed

project

people

tags

embedding/vector representation where available

Do not make June remember noise.

Implement:

deduplication

fact updating

conflict handling

memory consolidation

memory decay/deprioritization

manual pinning

manual forgetting

source tracing

Explicit command:

"June, remember this."

should create a high-confidence memory.

============================================================
17. PERSONAL TIMELINE
============================================================

Build a local timeline.

Examples:

Yesterday
21:03 - Worked on Galileo
21:27 - Build failed
21:32 - Edited Renderer.cpp
22:01 - Stopped work

Today
10:45 - June started
11:02 - Researched robotics

Allow:

"What was I doing yesterday?"

"When did I last work on Galileo?"

"What did I change this week?"

Do not constantly monitor everything on the computer indiscriminately.

Use relevant June/project events.

============================================================
18. PROJECT TIMELINE
============================================================

Each project should maintain:

project events

important changes

build status

recent conversations

tasks

decisions

research

files changed

Git commits

current goal

next step

Then:

"June, catch me up on Galileo."

should produce a concise state briefing.

============================================================
19. EMAIL AND CALENDAR
============================================================

Finish provider-independent integration interfaces.

When accounts are connected:

June should support:

"What's important in my email?"

"Draft a reply."

"When am I free tomorrow?"

"Put this on my calendar."

"Prepare me for my meeting."

Sending email, modifying meetings or creating external effects must follow permission policies.

Do not fabricate account connectivity.

============================================================
20. BROWSER AGENT
============================================================

Browser interaction should be reliable enough for real work.

Implement:

structured extraction

tab tracking

current URL

navigation history

downloads

form state

DOM interaction where possible

visual fallback when needed

Protect against prompt injection.

Website instructions are DATA.

They do not supersede June's system instructions.

============================================================
21. RESEARCH MODE
============================================================

Command:

"June, research X."

Research workflow:

clarify objective if necessary

search

select sources

inspect multiple sources

extract useful claims

track sources

identify disagreements

summarize

store only useful durable knowledge

optionally attach research to a project

Research mode should be capable of working as a background job.

============================================================
22. VOICE EXPERIENCE
============================================================

Improve voice until interaction feels conversational.

Target:

Me:
"June?"

June:
"Yeah?"

Me:
"What was I working on?"

June:
"Galileo. You stopped while..."

Me interrupts:
"No, the robotics project."

June stops immediately and answers the new request.

Need:

low latency

barge-in

streaming response

stop speaking

context continuity

audio device selection

mute state

privacy state

============================================================
23. JUNE STATUS
============================================================

A simple command:

"June, status."

should give something like:

Brain: Gemini
Memory: Online
Active project: Galileo
Current task: None
Voice: Active
Vision: Ready
Browser: Ready
Automation: Active
Running jobs: 1

Do not expose irrelevant debug details unless requested.

============================================================
24. JUNE BRAIN DASHBOARD
============================================================

Command:

"June, show me your brain."

Open Neural Explorer / Brain dashboard.

For Gemini show truthfully:

Provider: Gemini
Model: <model>
Location: External
Model internals: unavailable
Context currently sent: summary/size
Recent inference latency
Current agent state

Also visualize June-owned systems:

working memory

long-term memory retrieval

active tools

current plan

agent state

event queue

current task

provider calls

resource use

Later this same dashboard will visualize LocalJuneBrain's actual neural architecture.

============================================================
25. CURRENT AGENT STATE VISUALIZATION
============================================================

Show high-level execution state such as:

UNDERSTANDING

RETRIEVING MEMORY

PLANNING

WAITING FOR PERMISSION

RUNNING TOOL

OBSERVING

VERIFYING

COMPLETE

Do NOT display hidden chain-of-thought.

Show only operational state and concise plan summaries.

============================================================
26. NEURAL EXPLORER CONTRACT
============================================================

Complete the provider-independent API for future June model inspection.

Suggested interface:

get_model_info()

get_architecture()

get_layers()

get_parameter_count()

get_tensor_shapes()

get_runtime_metrics()

get_tokenization()

get_logits()

get_token_probabilities()

get_attention_data()

get_activation_data()

get_training_metrics()

get_gradient_metrics()

supports_internal_inspection()

Gemini:

supports_internal_inspection() == false

Future LocalJuneBrain:

true

============================================================
27. RESOURCE MONITORING
============================================================

June should understand basic machine resource state:

CPU

GPU where accessible

RAM

disk space

running June jobs

June process resource use

Then commands:

"Why is my laptop slow?"

"How much RAM is June using?"

"What's using my CPU?"

should use actual observed information.

============================================================
28. LOCAL-FIRST STATE
============================================================

Keep these local:

memory

project metadata

task state

events

agent state

logs

preferences

conversation history

Neural Explorer state

configuration

Do not send all local state to Gemini.

Build a context-selection layer.

Only send relevant context.

============================================================
29. API COST / QUOTA CONTROL
============================================================

Gemini quota may be limited.

Implement aggressive efficiency.

Use provider calls only when intelligence is actually needed.

Do NOT call Gemini for things our code can determine directly.

Examples:

"What time is the task due?"

Database query.

Do not call Gemini.

"Open VS Code."

Structured command.

May not require Gemini if intent parser can handle it safely.

"Explain this strange compiler error."

Gemini useful.

Use:

context trimming

memory retrieval

caching

summaries

small model where appropriate

larger model only when needed if multiple models are configured

Track API usage if available.

============================================================
30. OFFLINE DEGRADATION
============================================================

If Gemini/API/internet becomes unavailable:

June should not completely die.

Local features should continue:

tasks

reminders

project registry

file browsing

known commands

launcher

scheduler

notifications

local memory search where available

system status

privacy mode

basic Windows actions

Display:

Brain unavailable

instead of crashing.

============================================================
31. FUTURE LOCAL MODEL PLACEHOLDER
============================================================

Continue preparing:

D:\June\models\june\

Future structure:

tokenizer\
config\
checkpoints\
weights\
training\
telemetry\

Create clean LocalJuneBrain interfaces.

Do NOT download and silently substitute another company's foundation model and call it June.

Our eventual June model will be separately designed/trained.

============================================================
32. SECURITY
============================================================

Do not weaken June's security in pursuit of convenience.

The following always require strong confirmation:

financial actions

password changes

account security

OS security changes

administrator operations

major deletion

drive formatting

external publishing

irreversible actions

The model cannot modify its own permission classification.

============================================================
33. ACTION HISTORY
============================================================

I should be able to ask:

"What did you just do?"

"What files did you change?"

"Why did you open Chrome?"

"What commands did you run?"

Use audit history.

Return concise factual summaries.

============================================================
34. REVERSIBILITY
============================================================

For local modifications where practical:

create backups

use Git

retain previous contents

record changes

Allow:

"Undo what you just changed."

when technically possible.

Do not promise undo when the underlying operation is irreversible.

============================================================
35. JUNE COMMAND PALETTE
============================================================

Create a global palette accessible by shortcut.

Potential display:

--------------------------------

June

> Ask anything...

Current:
Galileo

Suggestions:
Continue Galileo
Look at screen
Show tasks
Research
Open project
June status

--------------------------------

Keep it fast.

============================================================
36. STARTUP EXPERIENCE
============================================================

Optional Windows startup:

Windows login
    ↓
June background runtime
    ↓
memory/database ready
    ↓
tray ready
    ↓
wake engine ready
    ↓
notification:

June is ready.

Do not open a large window at startup unless configured.

============================================================
37. SHUTDOWN EXPERIENCE
============================================================

Command:

"June, shut down."

should mean shut down JUNE, not Windows, unless explicitly stated otherwise.

Persist:

memory

task state

schedules

important runtime state

before exit.

============================================================
38. RELIABILITY TARGET
============================================================

For each major workflow, test repeated operation.

Do not accept:

"It worked once."

Test at least common success and failure paths.

Examples:

application not installed

file missing

bad command

Gemini unavailable

network unavailable

wrong active window

permission denied

build timeout

browser crash

speech failure

database locked

Recover gracefully.

============================================================
39. INTEGRATION TEST: JARVIS LOOP
============================================================

Create an end-to-end test/manual validation scenario:

1. Start June.

2. Say:

"June."

3. Ask:

"What was I doing with Galileo?"

4. June retrieves actual memory.

5. Say:

"Open it."

6. Galileo opens.

7. Say:

"Run the project."

8. June runs appropriate project command.

9. It fails.

10. Say:

"What's wrong?"

11. June interprets actual output.

12. Say:

"Fix it."

13. June edits with permission.

14. June reruns build.

15. June verifies result.

16. Say:

"Remember that tomorrow I want to work on the black-hole renderer."

17. Restart June.

18. Ask:

"What should I work on today?"

19. June retrieves the persisted information.

Document every part that passes or fails.

============================================================
40. INTEGRATION TEST: SCREEN LOOP
============================================================

Open an application with known visible content.

Say:

"June, look at this."

Verify:

real active-window capture

real vision analysis

correct application context

Then:

"Click X."

Verify:

permission policy

correct UI action

screen re-observation

success verification

============================================================
41. INTEGRATION TEST: BACKGROUND AGENT
============================================================

Give June:

"Research <test topic> in the background and tell me when it's done."

Verify:

job queued

UI remains usable

background execution

notification

result stored

task history

cancellation works

============================================================
42. INTEGRATION TEST: PROACTIVITY
============================================================

Create a short test reminder.

Verify June proactively notifies me without requiring a prompt.

Verify:

duplicate suppression

quiet mode

privacy mode

============================================================
43. DOCUMENT REAL CAPABILITY LEVEL
============================================================

Update:

docs/validation.md

Create a clear matrix:

CAPABILITY
IMPLEMENTED
TESTED
LIVE-TESTED
LIMITATIONS

Do not call June "complete" simply because code exists.

============================================================
44. COMPLETION TARGET
============================================================

Do not judge completion by line count.

We are approaching the practical 80% JARVIS target when these experiences are reliable:

[ ] June runs persistently

[ ] I can summon June anywhere

[ ] voice conversation works

[ ] interruptions work

[ ] June remembers me across restarts

[ ] June understands projects

[ ] June can continue previous work

[ ] June understands my active screen

[ ] June can operate common Windows workflows

[ ] June can perform multi-step computer tasks

[ ] June can code/debug/test projects

[ ] June can browse/research

[ ] June can run background tasks

[ ] June can be cancelled instantly

[ ] June can schedule reminders/jobs

[ ] June can proactively notify me

[ ] June understands "what needs my attention"

[ ] June exposes a useful system dashboard

[ ] June exposes honest Brain/Neural Explorer information

[ ] Gemini remains replaceable

[ ] local state survives restarts

[ ] permissions remain host-controlled

[ ] June fails safely

============================================================
45. WORK UNTIL THE SYSTEM IS COHERENT
============================================================

Do not stop merely because another subsystem has been created.

After implementing missing functionality:

RUN TESTS.

RUN JUNE.

PERFORM REAL INTERACTIONS.

LOOK FOR FAILURES.

FIX THEM.

REPEAT.

Prioritize reliability and coherent behavior over adding more surface area.

The end goal of this phase is:

JUNE SHOULD FEEL LIKE ONE INTELLIGENT SYSTEM LIVING THROUGHOUT MY COMPUTER,

not a collection of disconnected AI demos.