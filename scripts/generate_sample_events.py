"""Author the sample timeline dataset for examples/events.json.

Fully synthetic: a fictional EV company ("Voltera Motors") rolling out a major
over-the-air driver-assist software feature ("Drive Assist 3.0"). No real
people, companies, or files. This is a one-off authoring tool, not part of the
`arc` package; it just keeps the large sample compact to write and easy to vary.

Besides examples/events.json, it writes the demo's clickable assets directly
into docs/ (where GitHub Pages serves them, alongside docs/timeline.html):

* docs/evidence/<tab>/<NNN_slug>.txt  — one source email per event ("Open email")
* docs/files/<name>                   — a placeholder file per attachment chip

The source/attachment links in events.json are therefore relative to the docs/
directory (`evidence/...`, `files/...`), so they resolve both on Pages and when
docs/timeline.html is opened locally. Regenerate the page afterwards with
`arc timeline examples/events.json -o docs/timeline.html`.

Run:  python scripts/generate_sample_events.py
"""
import base64
import json
import os
import random
import re
from datetime import datetime, timedelta


def ev(date, title, summary, parties, imp=0, phase=None, quote=None, atts=None, sig=None, cat=None, src=None):
    d = {"date": date, "title": title, "summary": summary, "parties": parties, "importance": imp}
    if phase:
        d["phase"] = phase
    if quote:
        d["quote"] = quote
    if atts:
        d["attachments"] = atts
    if sig:
        d["significance"] = sig
    if cat:
        d["category"] = cat
    if src:
        d["source"] = src
    return d


def REF(label, name):
    """A source link to a document/file."""
    return {"type": "ref", "label": label, "href": "files/" + name}


def MANUAL(by, at):
    """Provenance for a manually-logged milestone."""
    return {"type": "manual", "by": by, "at": at}


def L(name):
    """A linked attachment chip."""
    return {"name": name, "href": "files/" + name}


CATEGORIES = [
    {"id": "research", "label": "UX Research", "color": "#8B5CF6"},
    {"id": "design", "label": "Product Design", "color": "#6366F1"},
    {"id": "product", "label": "Product Mgmt", "color": "#1E88E5"},
    {"id": "perception", "label": "Perception ML", "color": "#EF4444"},
    {"id": "vehiclesw", "label": "Vehicle Software", "color": "#0EA5E9"},
    {"id": "cloud", "label": "Cloud Platform", "color": "#14B8A6"},
    {"id": "mobile", "label": "Mobile App", "color": "#F59E0B"},
    {"id": "simulation", "label": "Simulation", "color": "#7C3AED"},
    {"id": "tracktest", "label": "Track Testing", "color": "#10B981"},
    {"id": "safety", "label": "Safety", "color": "#DC2626"},
    {"id": "regulatory", "label": "Regulatory", "color": "#A16207"},
    {"id": "internalfleet", "label": "Internal Fleet", "color": "#2563EB"},
    {"id": "earlyaccess", "label": "Early Access", "color": "#0284C7"},
    {"id": "expandedbeta", "label": "Expanded Beta", "color": "#16A34A"},
    {"id": "ota", "label": "Staged OTA", "color": "#0D9488"},
    {"id": "marketing", "label": "Marketing", "color": "#DB2777"},
    {"id": "support", "label": "Support", "color": "#D97706"},
    {"id": "pr", "label": "Comms / PR", "color": "#9333EA"},
    {"id": "telemetry", "label": "Telemetry", "color": "#059669"},
    {"id": "incidents", "label": "Incidents", "color": "#B91C1C"},
    {"id": "iteration", "label": "Iteration", "color": "#2563EB"},
]

# --------------------------------------------------------------------------- #
# Tab 1 — Product & Design
# --------------------------------------------------------------------------- #
tab_product = {
    "id": "product",
    "label": "1. Product & Design",
    "heading": "Product & design",
    "description": "Discovery, the product definition, and the design of Drive Assist 3.0.",
    "filters": True,
    "summary": "Drive Assist 3.0 starts as a discovery effort: UX research probes why drivers disengage today, product turns that into a definition and success metrics, and design works from early flows to a frozen spec. The signed PRD and the design freeze are the two gates everything downstream builds against.",
    "groups": [
        {"id": "research", "label": "UX Research", "category": "research", "events": [
            ev("2024-09-09", "Discovery kickoff", "Research scopes why drivers disengage from the current assist and where trust breaks down.", "Mia Chen", 1, "Discovery"),
            ev("2024-09-23", "Diary study launched", "30 owners log every disengagement for three weeks.", "Mia Chen → Panel", 1, "Discovery", atts=["study_protocol.pdf"]),
            ev("2024-10-14", "Disengagement themes", "Five recurring triggers identified; lane-change hesitation tops the list.", "Mia Chen", 2, "Discovery", quote="Drivers grab the wheel most often during unprotected lane changes.", atts=[L("research_readout.pdf")]),
            ev("2024-11-04", "Trust & handover model", "A model for how the car should ask for and return control.", "Mia Chen, Lena Ortiz", 2, "Synthesis"),
            ev("2024-12-12", "Concept testing round 1", "Three interaction concepts tested; the ambient-cue concept wins.", "Mia Chen", 1, "Synthesis", quote="Ambient cues felt 'calmer' than alerts; testers trusted them more."),
            ev("2025-01-29", "Accessibility research", "Findings on cues for low-vision and hard-of-hearing drivers.", "Mia Chen → Design", 1, "Synthesis", atts=["a11y_findings.pdf"]),
            ev("2025-04-22", "Beta interview program set up", "Recurring interview cadence stood up for the beta phase.", "Mia Chen", 0),
            ev("2025-08-19", "Pre-launch perception study", "Owners rate the near-final experience; trust scores up sharply.", "Mia Chen", 2, sig="Validates the handover model right before staged rollout.", quote="Net trust score moved from +12 to +41 versus today's assist."),
        ]},
        {"id": "design", "label": "Product Design", "category": "design", "events": [
            ev("2024-10-07", "Design exploration begins", "First flows for engagement, lane changes, and handover.", "Sora Kim", 0, "Explore"),
            ev("2024-10-28", "Cluster & HUD concepts", "Competing instrument-cluster treatments sketched.", "Sora Kim", 1, "Explore", atts=["cluster_concepts.fig"]),
            ev("2024-11-25", "Interaction spec v1", "First end-to-end interaction spec for review.", "Sora Kim → Eng", 2, "Define", atts=[L("interaction_spec.pdf")]),
            ev("2024-12-18", "Handover animation prototype", "Motion prototype for the control handover sequence.", "Sora Kim", 1, "Define", quote="The 1.5s ramp reads as 'the car is handing back', not 'the car gave up.'"),
            ev("2025-01-15", "Sound design pass", "Earcons designed for engage, warn, and handover.", "Sora Kim, Audio", 1, "Define"),
            ev("2025-02-05", "Design review with safety", "Safety flags two cues that could be missed in sunlight.", "Sora Kim, Aisha Bello", 2, "Define", quote="High-glare conditions wash out the amber cue; needs a redundant channel."),
            ev("2025-02-12", "Redundant cue added", "Haptic seat cue added as a backup to the visual handover.", "Sora Kim", 2, "Define"),
            ev("2025-02-24", "Design freeze", "Interaction and visual spec frozen for build.", "Sora Kim → Eng", 3, "Freeze", sig="The spec engineering builds to; later changes need a variance.", atts=[L("design_spec_final.pdf")]),
            ev("2025-06-30", "Localization handoff", "Strings and cues handed to localization for 14 markets.", "Sora Kim → Localization", 0, "Freeze", atts=["loc_kit.zip"]),
        ]},
        {"id": "product", "label": "Product Management", "category": "product", "events": [
            ev("2024-09-16", "Problem brief circulated", "One-pager framing the opportunity and bets.", "Lena Ortiz", 1, "Define"),
            ev("2024-10-21", "Success metrics defined", "Primary metric set to miles-per-disengagement; guardrails on comfort.", "Lena Ortiz", 2, "Define", quote="North star: 5x miles-per-disengagement without raising hard-brake events."),
            ev("2024-11-18", "PRD signed off", "Product requirements approved by engineering and safety leadership.", "Lena Ortiz, Dana Olsen", 3, "Define", sig="Authorizes the full build; scope is now contract.", atts=[L("prd_drive_assist_3.pdf")], src=REF("PRD doc", "prd_drive_assist_3.pdf")),
            ev("2024-12-09", "Scope cut: no auto lane-change at launch", "Auto lane-change deferred to a fast-follow to protect the date.", "Lena Ortiz", 2, "Plan", quote="We ship driver-confirmed lane changes first; full auto is a 3.1 item.", sig="De-risks the launch date by removing the hardest behavior."),
            ev("2025-01-13", "Roadmap & milestones locked", "Build, validation, beta, and launch milestones agreed.", "Lena Ortiz → Program", 1, "Plan", atts=["roadmap.xlsx"]),
            ev("2025-03-10", "Pricing & packaging decision", "Feature ships included on new trims, subscription for existing fleet.", "Lena Ortiz, Finance", 2, "Plan"),
            ev("2025-05-19", "Go/no-go criteria published", "The exact metrics that gate each rollout stage.", "Lena Ortiz, Aisha Bello", 2, "Plan", atts=[L("go_criteria.pdf")], src=MANUAL("Lena Ortiz", "2025-05-19 11:40")),
            ev("2025-09-02", "Launch readiness review #1", "First cross-functional readiness check; two ambers on support load.", "Lena Ortiz", 1),
            ev("2025-10-14", "Launch readiness review #2", "All gates green; recommends opening the staged OTA.", "Lena Ortiz, Dana Olsen", 3, sig="Formal authorization to begin the production rollout."),
        ]},
    ],
}

# --------------------------------------------------------------------------- #
# Tab 2 — Engineering
# --------------------------------------------------------------------------- #
tab_eng = {
    "id": "engineering",
    "label": "2. Engineering",
    "heading": "Engineering",
    "description": "Perception ML, vehicle software, cloud platform, and the mobile app.",
    "filters": True,
    "summary": "Four engineering tracks build in parallel for the better part of a year. Perception ML retrains the night/rain stack and recovers from a tunnel false-positive regression; vehicle software integrates the planner and the new handover; cloud builds the OTA pipeline and shadow-mode telemetry; and the mobile app adds trip review and the consent flow. Perception sign-off and the release-candidate build are the milestones the rest gate on.",
    "groups": [
        {"id": "perception", "label": "Perception ML", "category": "perception", "events": [
            ev("2024-10-02", "Perception 3.0 research kickoff", "Scope the next-gen stack targeting night and rain performance.", "Tomás Vidal", 1, "Research"),
            ev("2024-10-21", "Dataset expansion plan", "Plan to triple the labeled night-driving set; new labeling vendor engaged.", "Tomás Vidal → Data Ops", 1, "Research", atts=["dataset_plan.xlsx"]),
            ev("2024-11-15", "Baseline model benchmarked", "New backbone beats production on the internal benchmark.", "Perception ML", 2, "Research", quote="+7% mAP on the night/rain slice; latency within budget."),
            ev("2024-12-10", "Architecture review", "Cross-team review approves multi-camera fusion.", "Tomás Vidal, Raj Patel", 2, "Build", atts=[L("perception_arch.pdf")]),
            ev("2025-01-20", "Regression: tunnel false positives", "Shadow-mode flags phantom braking entering tunnels.", "Perception ML", 2, "Build", quote="Tunnel entrances trigger false positives; the exposure shift is the cause.", sig="Triggers a data campaign and a two-week slip."),
            ev("2025-02-18", "Tunnel dataset + retrain", "Targeted data collected; false positives down 90%.", "Perception ML", 1, "Build"),
            ev("2025-03-25", "Model frozen for validation (rc1)", "Candidate v3.0-rc1 handed to validation.", "Tomás Vidal → Validation", 3, "Hardening", sig="The model build the whole validation campaign runs against.", atts=[L("model_card.pdf")]),
            ev("2025-05-12", "Edge-case hardening (rc2)", "Long-tail cases — debris, animals — addressed.", "Perception ML", 1, "Hardening"),
            ev("2025-04-15", "Quantization accuracy check", "Quantized model verified within tolerance of float.", "Perception ML", 1, "Hardening", quote="INT8 within 0.4% of float on the validation slice."),
            ev("2025-06-18", "Shadow A/B vs production", "rc2 shadow-driven against the shipping model for two weeks.", "Perception ML", 2, "Hardening", sig="Real-road evidence the new model is safe to let drive."),
            ev("2025-06-30", "Per-batch camera calibration", "Calibration across camera batches removes a model bias.", "Perception ML", 1, "Hardening"),
            ev("2025-07-08", "Perception sign-off (rc3)", "Validation accepts rc3 for the beta program.", "Tomás Vidal, Aisha Bello", 3, "Hardening", sig="Unblocks beta for the perception stack."),
        ]},
        {"id": "vehiclesw", "label": "Vehicle Software", "category": "vehiclesw", "events": [
            ev("2024-10-16", "Planner integration branch opened", "New behavior planner wired into the vehicle stack behind a flag.", "Raj Patel", 0, "Integrate"),
            ev("2024-11-20", "Handover state machine", "Implements the design's engage/warn/handover transitions.", "Raj Patel → Sora Kim", 2, "Integrate", atts=["handover_fsm.pdf"]),
            ev("2025-01-08", "Compute budget exceeded", "New stack overruns the SoC compute budget at peak.", "Raj Patel", 2, "Integrate", quote="Peak load is 118% of budget; we need to prune or offload.", sig="Risks a hardware floor that would exclude older cars."),
            ev("2025-02-03", "Optimization recovers headroom", "Operator fusion and quantization bring peak under budget.", "Raj Patel", 2, "Integrate", quote="Back to 86% peak; older HW3 cars stay in scope."),
            ev("2025-03-19", "Driver-confirmed lane change", "Ships the launch-scope lane-change behavior.", "Vehicle Software", 1, "Build"),
            ev("2025-04-28", "Fail-safe & fallback paths", "Graceful degradation when a sensor drops out.", "Raj Patel, Aisha Bello", 2, "Build", atts=[L("failsafe_design.pdf")]),
            ev("2025-06-16", "Feature-flagged for beta", "Behavior gated behind the staged-rollout flag service.", "Raj Patel → Cloud", 1, "Build"),
            ev("2025-08-11", "Release candidate cut", "rc build assembled with frozen perception and planner.", "Raj Patel", 3, "Stabilize", sig="The exact build beta and validation run against.", atts=["release_notes.md", L("ota_manifest.json")]),
        ]},
        {"id": "cloud", "label": "Cloud Platform", "category": "cloud", "events": [
            ev("2024-11-06", "OTA pipeline design", "Design for staged, reversible over-the-air delivery.", "Dev Anand", 1, "Design", atts=[L("ota_design.pdf")]),
            ev("2024-12-04", "Shadow-mode telemetry", "Pipeline to log model decisions without acting on them.", "Dev Anand → Perception", 2, "Build", quote="Shadow mode lets us measure a build on real roads before it drives."),
            ev("2025-01-27", "Staged-rollout flag service", "Percentage-based targeting with instant rollback.", "Dev Anand", 2, "Build"),
            ev("2025-03-11", "Load test: 1M vehicles", "Simulated fleet check-in storm; one bottleneck found and fixed.", "Cloud Platform", 1, "Build", quote="Check-in p99 held under 400ms at 1M simulated cars."),
            ev("2025-05-06", "Rollback drill", "Game-day proves a bad build can be pulled fleet-wide fast.", "Dev Anand", 2, "Harden", quote="Full-fleet rollback completed in 22 minutes end to end.", sig="The safety net that makes a staged production rollout acceptable."),
            ev("2025-06-24", "Region failover", "Multi-region failover for the update service.", "Dev Anand", 1, "Harden"),
            ev("2025-09-09", "Capacity reserved for launch", "Headroom provisioned for the rollout window.", "Dev Anand", 0),
            ev("2025-10-28", "Canary metrics auto-halt", "Auto-pause if canary safety metrics regress.", "Dev Anand, Aisha Bello", 2, "Harden", sig="Lets the OTA stop itself without a human in the loop."),
        ]},
        {"id": "mobile", "label": "Mobile App", "category": "mobile", "events": [
            ev("2024-12-02", "Consent & enrollment flow", "In-app flow to opt into the beta and accept terms.", "Nora Fischer → Legal", 1, "Build"),
            ev("2025-01-21", "Trip review screen", "Post-drive view of where assist helped or handed back.", "Nora Fischer", 2, "Build", atts=["trip_review.fig"]),
            ev("2025-02-26", "Feedback capture", "One-tap 'that felt wrong' tied to a trip timestamp.", "Nora Fischer", 1, "Build", quote="Owners can flag a moment; it lands on the engineer's dashboard."),
            ev("2025-04-09", "Push: update available", "Notifies eligible cars an update is ready.", "Mobile App", 0, "Build"),
            ev("2025-05-21", "App store review friction", "Reviewer questions the driving-feature screenshots.", "Nora Fischer → Comms", 1, "Ship", quote="Store reviewer asked us to clarify it's driver-supervised."),
            ev("2025-06-11", "Beta build approved", "App update with beta features clears review.", "Nora Fischer", 2, "Ship"),
            ev("2025-08-27", "Localized release", "App shipped in 14 markets ahead of rollout.", "Nora Fischer", 1, "Ship"),
            ev("2025-10-20", "Launch app live", "Public app update with Drive Assist 3.0 surfaces.", "Nora Fischer", 2, "Ship", sig="Front door for owners on launch day."),
        ]},
    ],
}

# --------------------------------------------------------------------------- #
# Tab 3 — Validation & Safety
# --------------------------------------------------------------------------- #
tab_validation = {
    "id": "validation",
    "label": "3. Validation & Safety",
    "heading": "Validation & safety",
    "description": "Simulation, closed-track testing, the safety case, and regulatory filings.",
    "filters": True,
    "summary": "Validation is the long pole. Simulation runs millions of scenario miles and surfaces an unprotected-left weakness; track testing reproduces and clears it; the safety case assembles the argument and evidence; and regulatory files in the launch markets. The safety case approval and the first market clearance are the gates that release the production rollout.",
    "groups": [
        {"id": "simulation", "label": "Simulation", "category": "simulation", "events": [
            ev("2025-01-14", "Scenario library v3", "Expanded library covering the new behaviors.", "Sofia Marenko", 1, "Build", atts=["scenario_list.xlsx"]),
            ev("2025-02-20", "First full-stack sim run", "rc1 driven through 2M scenario miles overnight.", "Simulation", 2, "Run", quote="2.1M sim miles; one cluster of failures at unprotected lefts."),
            ev("2025-03-24", "Unprotected-left weakness", "Sim isolates a gap-acceptance bug on unprotected left turns.", "Sofia Marenko → Vehicle SW", 2, "Run", sig="Becomes the headline issue track testing must clear.", quote="The planner accepts gaps a cautious human would reject."),
            ev("2025-04-30", "Regression suite green", "Fix verified across the expanded suite.", "Simulation", 1, "Run"),
            ev("2025-06-09", "Fault-injection campaign", "Sensor dropouts and degraded compute injected at scale.", "Sofia Marenko", 2, "Run", atts=[L("fault_injection.pdf")]),
            ev("2025-07-21", "Coverage report", "Scenario coverage mapped to the safety case claims.", "Simulation → Safety", 1, "Report", atts=["coverage_report.pdf"]),
            ev("2025-05-20", "Rare-event resampling", "Suite reweighted toward the long tail.", "Sofia Marenko", 0, "Run"),
            ev("2025-08-12", "Replay of beta disengagements", "Real beta disengagements replayed in sim to confirm fixes.", "Simulation", 2, "Run", quote="Every reported beta disengagement now passes in sim."),
            ev("2025-08-26", "Sim-to-track correlation", "Sim outcomes correlated against the track results.", "Simulation, Track Testing", 1, "Report", atts=["sim_track_correlation.pdf"]),
            ev("2025-09-15", "Final sim sign-off", "rc3 passes the full campaign with no open criticals.", "Sofia Marenko", 3, "Report", sig="Simulation's release recommendation."),
        ]},
        {"id": "tracktest", "label": "Track Testing", "category": "tracktest", "events": [
            ev("2025-02-11", "Test plan approved", "Closed-track plan for the new behaviors and edge cases.", "Caleb Reed, Aisha Bello", 1, "Plan", atts=[L("track_test_plan.pdf")]),
            ev("2025-03-18", "First track week", "Baseline runs on the proving ground.", "Track Testing", 1, "Execute"),
            ev("2025-04-15", "Unprotected-left reproduced", "Track reproduces the sim's gap-acceptance issue with a soft target.", "Caleb Reed", 2, "Execute", quote="Confirmed on track with the foam vehicle; matches sim exactly."),
            ev("2025-05-27", "Wet & low-sun sessions", "Adverse-condition runs for handover cues.", "Track Testing", 1, "Execute"),
            ev("2025-06-20", "Unprotected-left cleared", "Fix passes the track battery with margin.", "Caleb Reed → Safety", 2, "Execute", sig="Clears the headline safety issue for beta.", quote="200/200 clean runs after the planner fix."),
            ev("2025-08-05", "Night cut-in testing", "Aggressive cut-ins at night with the new perception.", "Track Testing", 1, "Execute"),
            ev("2025-09-10", "Track sign-off", "Closed-course program complete; no open criticals.", "Caleb Reed", 3, "Execute", sig="Track testing's go for on-road beta expansion."),
        ]},
        {"id": "safety", "label": "Safety", "category": "safety", "events": [
            ev("2025-01-31", "Safety case outline", "Top-level claims-and-evidence structure agreed.", "Aisha Bello", 1, "Argue", atts=["safety_case_outline.pdf"]),
            ev("2025-03-07", "Hazard analysis updated", "HARA refreshed for the new behaviors.", "Aisha Bello", 2, "Argue", atts=[L("hara.pdf")]),
            ev("2025-04-18", "Threat & misuse review", "Foreseeable-misuse analysis for the handover.", "Aisha Bello, Security", 1, "Argue"),
            ev("2025-06-13", "Independent safety audit", "Third-party reviewer probes the argument; two findings.", "External Auditor", 2, "Review", quote="Auditor: strengthen the evidence for the degraded-sensor claim.", sig="External findings must close before approval."),
            ev("2025-07-15", "Findings closed", "Both audit findings addressed with added evidence.", "Aisha Bello", 1, "Review"),
            ev("2025-08-22", "Driver-monitoring threshold set", "Attention thresholds tuned with human-factors data.", "Aisha Bello, Mia Chen", 2, "Review"),
            ev("2025-05-08", "Operational design domain locked", "The exact conditions the feature may engage in.", "Aisha Bello", 2, "Argue", atts=[L("odd_definition.pdf")], sig="Bounds where the feature operates — central to the case."),
            ev("2025-06-30", "Human-factors study readout", "Attention and reaction data feed the driver-monitoring thresholds.", "Aisha Bello, Mia Chen", 1, "Review", atts=["hf_study.pdf"]),
            ev("2025-08-05", "Recall-risk assessment", "Worst-case mitigation paths reviewed with legal.", "Aisha Bello, Legal", 1, "Review"),
            ev("2025-09-19", "Safety case approved", "Safety leadership approves the case for staged rollout.", "Aisha Bello, Dana Olsen", 3, "Approve", sig="The central gate: production rollout cannot start without it.", atts=[L("safety_case_final.pdf")], src=REF("Safety case", "safety_case_final.pdf")),
        ]},
        {"id": "regulatory", "label": "Regulatory", "category": "regulatory", "events": [
            ev("2025-02-25", "Market applicability matrix", "Which behaviors are allowed in which launch markets.", "Kenji Watanabe", 1, "Prepare", atts=["reg_matrix.xlsx"]),
            ev("2025-04-08", "Pre-submission meeting", "Early alignment with the lead-market regulator.", "Kenji Watanabe", 2, "Prepare", quote="Regulator open to driver-confirmed lane change; wants DMS data."),
            ev("2025-05-29", "Type-approval dossier drafted", "Technical dossier assembled for the lead market.", "Kenji Watanabe → Legal", 1, "File"),
            ev("2025-07-02", "Dossier filed (lead market)", "Formal submission lodged.", "Kenji Watanabe", 2, "File", atts=[L("reg_filing.pdf")]),
            ev("2025-08-13", "Regulator clarification round", "Authority requests added human-factors evidence.", "Kenji Watanabe", 1, "File", quote="They want the attention-monitoring false-negative rate."),
            ev("2025-09-24", "Lead-market clearance", "First market approves Drive Assist 3.0 for public release.", "Kenji Watanabe", 3, "Clear", sig="Opens the first geography for staged OTA."),
            ev("2025-11-12", "Second-wave market filings", "Filings lodged for the next four markets.", "Kenji Watanabe", 1, "Clear"),
        ]},
    ],
}

# --------------------------------------------------------------------------- #
# Tab 4 — Beta Program
# --------------------------------------------------------------------------- #
tab_beta = {
    "id": "beta",
    "label": "4. Beta Program",
    "heading": "Beta program",
    "description": "Internal fleet dogfood, an invite-only early access, and the expanded public beta.",
    "filters": True,
    "summary": "Confidence is built in widening circles. The internal fleet dogfoods first and catches a cold-start bug; an invite-only early-access group of owners drives real roads under heavy telemetry; and the expanded beta scales to thousands, surfacing a freeway-merge complaint that drives a tuning fix. The expanded-beta safety review feeds directly into the launch decision.",
    "groups": [
        {"id": "internalfleet", "label": "Internal Fleet", "category": "internalfleet", "events": [
            ev("2025-04-21", "Employee fleet enrolled", "300 employee vehicles opted into dogfood.", "Elena Cruz", 1, "Dogfood"),
            ev("2025-05-08", "First dogfood build", "rc1 pushed to the internal fleet.", "Elena Cruz → Cloud", 1, "Dogfood"),
            ev("2025-05-22", "Cold-start handover bug", "Handover cue misfires in the first minute after wake.", "Internal Fleet", 2, "Dogfood", quote="On cold start the seat haptic fires a beat early.", sig="Caught internally before any customer saw it."),
            ev("2025-06-05", "Cold-start fix verified", "Fix confirmed across the fleet.", "Elena Cruz", 1, "Dogfood"),
            ev("2025-06-26", "Dogfood survey", "Employees rate trust and comfort weekly.", "Elena Cruz", 0, "Dogfood", atts=["dogfood_survey.csv"]),
            ev("2025-07-17", "Internal go for early access", "Fleet metrics clear the bar to invite customers.", "Elena Cruz, Lena Ortiz", 2, "Dogfood", sig="Opens the door to the first external drivers."),
        ]},
        {"id": "earlyaccess", "label": "Early Access", "category": "earlyaccess", "events": [
            ev("2025-07-24", "Early-access cohort selected", "500 owners chosen across climates and road types.", "Elena Cruz", 1, "Invite", atts=["cohort_criteria.pdf"]),
            ev("2025-07-31", "Consent & onboarding", "Cohort completes the in-app consent and tutorial.", "Early Access → Mobile", 1, "Invite"),
            ev("2025-08-07", "First customer miles", "Drive Assist 3.0 on public roads with real owners.", "Early Access", 2, "Drive", sig="First non-employee exposure on real roads."),
            ev("2025-08-21", "Weekly telemetry review", "Disengagements triaged with engineering each week.", "Elena Cruz, Tomás Vidal", 1, "Drive"),
            ev("2025-09-04", "Construction-zone reports", "Owners report hesitancy in long construction zones.", "Early Access", 1, "Drive", quote="Cones with no lane lines make it over-cautious."),
            ev("2025-09-18", "Construction tuning shipped", "Targeted update improves cone-zone behavior.", "Vehicle Software", 2, "Drive"),
            ev("2025-09-30", "Trust scores trending up", "Cohort trust metric climbs week over week.", "Mia Chen", 1, "Drive", quote="Week-6 trust up 18 points versus week 1."),
            ev("2025-08-14", "Telematics consent refresh", "Cohort re-consents to expanded data capture.", "Early Access → Legal", 0, "Drive"),
            ev("2025-08-28", "Cold-climate sub-cohort", "Snow-market owners added to stress winter conditions.", "Elena Cruz", 1, "Drive"),
            ev("2025-09-25", "Roundabout edge cases", "Owners report odd lane choice at multi-lane roundabouts.", "Early Access", 1, "Drive", quote="Multi-lane roundabouts confuse lane choice on exit."),
            ev("2025-10-09", "Early-access exit review", "Cohort metrics support expanding the beta.", "Elena Cruz, Aisha Bello", 2, "Review", sig="Greenlights the jump to thousands of cars."),
        ]},
        {"id": "expandedbeta", "label": "Expanded Beta", "category": "expandedbeta", "events": [
            ev("2025-10-13", "Expanded beta opens", "Beta scales from 500 to 8,000 vehicles.", "Elena Cruz", 2, "Scale", sig="Largest pre-launch exposure of the feature."),
            ev("2025-10-16", "Onboarding load spike", "Surge of enrollments stresses the consent service.", "Cloud Platform", 1, "Scale", quote="Consent service hit 6x normal; autoscaled cleanly."),
            ev("2025-10-23", "Freeway-merge complaints", "A cluster of reports about timid freeway merges.", "Expanded Beta", 2, "Scale", quote="It waits for huge gaps on busy merges; feels unnatural.", sig="The top issue to resolve before public launch."),
            ev("2025-10-30", "Merge-aggressiveness tuning", "Calibrated a more natural merge gap-acceptance.", "Vehicle Software", 2, "Scale"),
            ev("2025-11-06", "Merge fix validated in beta", "Complaint rate drops sharply after the update.", "Elena Cruz", 1, "Scale", quote="Merge complaints down 80% week over week."),
            ev("2025-11-13", "A/B on cue timing", "Two handover-timing variants tested in the field.", "Mia Chen, Vehicle SW", 1, "Scale"),
            ev("2025-11-20", "Beta safety metrics report", "Miles-per-disengagement up 4.6x with stable hard-braking.", "Aisha Bello", 2, "Review", atts=[L("beta_metrics.pdf")], quote="4.6x MPD, hard-brake events flat — within launch criteria."),
            ev("2025-11-03", "Referral waitlist opens", "Beta owners can refer others; the waitlist swells.", "Marketing, Beta", 0, "Scale"),
            ev("2025-11-10", "Night-merge follow-up", "Targeted check that the merge fix held at night.", "Expanded Beta", 1, "Scale"),
            ev("2025-11-24", "Comfort survey wave", "Large survey on ride comfort and trust.", "Mia Chen", 1, "Review", atts=["comfort_survey.csv"]),
            ev("2025-11-27", "Expanded-beta sign-off", "Beta meets every go criterion for staged rollout.", "Elena Cruz, Lena Ortiz", 3, "Review", sig="Feeds straight into the launch go/no-go."),
        ]},
    ],
}

# --------------------------------------------------------------------------- #
# Tab 5 — Rollout & Launch
# --------------------------------------------------------------------------- #
tab_rollout = {
    "id": "rollout",
    "label": "5. Rollout & Launch",
    "heading": "Rollout & launch",
    "description": "The staged production OTA, marketing, support readiness, and external comms.",
    "filters": True,
    "summary": "The production rollout goes out in widening rings — 1% → 10% → 50% → 100% — each gated on live safety telemetry, with a brief pause at 10% to chase a metric blip. Marketing builds the story and reveals on launch day, support staffs and trains for the wave, and comms manages press and a measured response to early scrutiny. Reaching 100% availability is the finish line of the program.",
    "groups": [
        {"id": "ota", "label": "Staged OTA", "category": "ota", "events": [
            ev("2025-11-28", "Rollout runbook finalized", "Step-by-step plan with halt criteria per ring.", "Dev Anand, Aisha Bello", 1, "Prep", atts=[L("rollout_runbook.pdf")]),
            ev("2025-12-01", "1% canary live", "First production ring receives Drive Assist 3.0.", "Staged OTA", 3, "1%", sig="The feature is now in customers' hands in production.", quote="Canary safety metrics matched beta within noise."),
            ev("2025-12-04", "10% ring", "Rollout widens to 10% of eligible vehicles.", "Staged OTA", 2, "10%"),
            ev("2025-12-06", "Auto-halt at 10%", "A disengagement-rate blip trips the auto-halt.", "Cloud Platform", 2, "10%", quote="A regional weather event spiked disengagements; auto-halt worked.", sig="First real test of the self-stopping rollout."),
            ev("2025-12-08", "Resumed after analysis", "Blip traced to fog, not the build; rollout resumes.", "Dev Anand, Tomás Vidal", 1, "10%"),
            ev("2025-12-11", "50% ring", "Half the eligible fleet now updated.", "Staged OTA", 2, "50%"),
            ev("2025-12-15", "Hold for holiday traffic", "Brief planned hold over peak travel days.", "Staged OTA", 0, "50%"),
            ev("2025-12-19", "100% availability", "Drive Assist 3.0 available to the full eligible fleet.", "Staged OTA", 3, "100%", sig="Rollout complete — the program's finish line.", src=MANUAL("Dev Anand", "2025-12-19 12:05")),
        ]},
        {"id": "marketing", "label": "Marketing", "category": "marketing", "events": [
            ev("2025-09-08", "Positioning & narrative", "Story centers on 'calmer, more trustworthy assist'.", "Marcus Hale", 1, "Build"),
            ev("2025-10-06", "Demo film shoot", "Hero film capturing the handover experience.", "Marketing", 1, "Build", atts=["film_brief.pdf"]),
            ev("2025-10-27", "Site & release assets", "Launch page and creative locked.", "Marketing", 1, "Build", atts=[L("press_kit.zip")]),
            ev("2025-11-17", "Owner email sequence", "Staged email plan matched to the OTA rings.", "Marketing → CRM", 0, "Build"),
            ev("2025-12-01", "Launch-day reveal", "Feature announced as the canary goes live.", "Marcus Hale", 3, "Launch", sig="Public unveiling of Drive Assist 3.0.", quote="Reveal drove record traffic to the configurator."),
            ev("2025-12-09", "Owner explainer push", "How-it-works content to the updated fleet.", "Marketing", 1, "Launch"),
            ev("2025-12-22", "Availability moment", "Full-availability announcement to all owners.", "Marcus Hale", 2, "Launch"),
        ]},
        {"id": "support", "label": "Support", "category": "support", "events": [
            ev("2025-10-15", "Support readiness plan", "Staffing and tooling plan for the rollout wave.", "Priya Iyer", 1, "Ready", atts=["support_plan.xlsx"]),
            ev("2025-11-10", "Agent training", "Agents trained on the feature and handover model.", "Priya Iyer", 1, "Ready"),
            ev("2025-11-24", "Knowledge base published", "Owner-facing articles and an internal runbook live.", "Priya Iyer → Web", 1, "Ready", atts=[L("kb_runbook.pdf")]),
            ev("2025-12-02", "Day-1 contact spike", "Questions surge as the canary lands; within forecast.", "Support", 2, "Live", quote="Contacts +35% day one, staffed for +50%; no backlog."),
            ev("2025-12-07", "Top issue: handover confusion", "Most contacts are about why the car handed back.", "Priya Iyer → Product", 2, "Live", quote="People want to know why it handed control back in fog.", sig="Drives an in-app explainer and a KB update."),
            ev("2025-12-12", "In-app explainer shipped", "Contextual explanation reduces repeat contacts.", "Mobile App", 1, "Live"),
            ev("2025-12-20", "Support load normalizes", "Contact rate settles to baseline post-100%.", "Priya Iyer", 1, "Live"),
        ]},
        {"id": "pr", "label": "Comms / PR", "category": "pr", "events": [
            ev("2025-11-19", "Press strategy locked", "Embargoed briefings and Q&A prepared.", "Marcus Hale, Legal", 1, "Prep", atts=["press_strategy.pdf"]),
            ev("2025-11-26", "Analyst pre-briefs", "Background sessions with industry analysts.", "Comms", 0, "Prep"),
            ev("2025-12-01", "Embargo lifts", "Coverage goes live alongside the canary.", "Marcus Hale", 2, "Launch", quote="Largely positive; several outlets praised the calmer handover."),
            ev("2025-12-05", "Scrutiny on auto-halt", "A report questions the 10% pause.", "Comms", 2, "Manage", quote="Outlet framed the auto-halt as a 'stumble'.", sig="Tests the comms response to rollout transparency."),
            ev("2025-12-06", "Transparency post", "Engineering blog explains the auto-halt as designed.", "Marcus Hale, Dev Anand", 2, "Manage", quote="We framed the halt as the safety net working, not failing.", atts=[L("eng_blog_autohalt.pdf")]),
            ev("2025-12-10", "Narrative recovers", "Follow-up coverage adopts the 'safety net' framing.", "Comms", 1, "Manage"),
            ev("2025-12-19", "Availability press note", "Short note marks full availability.", "Comms", 1, "Manage"),
        ]},
    ],
}

# --------------------------------------------------------------------------- #
# Tab 6 — Post-Launch
# --------------------------------------------------------------------------- #
tab_post = {
    "id": "postlaunch",
    "label": "6. Post-Launch",
    "heading": "Post-launch",
    "description": "Fleet telemetry, incident response, and the first iteration cycle.",
    "filters": True,
    "summary": "After 100%, the work shifts to watching and improving. Telemetry confirms the headline metric holds at fleet scale; an incident track handles a localized phantom-braking cluster and a CDN-related update stall with published post-mortems; and iteration kicks off 3.1, including the auto lane-change that was cut from launch. The 3.1 kickoff closes the loop back to product.",
    "groups": [
        {"id": "telemetry", "label": "Telemetry", "category": "telemetry", "events": [
            ev("2025-12-02", "Live safety dashboard", "Real-time MPD and hard-brake metrics per ring.", "Sofia Marenko", 1, "Watch", atts=["metrics_dashboard.png"]),
            ev("2025-12-12", "Fleet metric holds", "Miles-per-disengagement at 100% matches beta.", "Telemetry", 2, "Watch", quote="Fleet MPD 4.5x — beta held at scale.", sig="Confirms the core bet survived going wide."),
            ev("2025-12-28", "Weather-correlation study", "Disengagements correlate with heavy precipitation, as expected.", "Telemetry", 1, "Watch"),
            ev("2026-01-09", "Long-tail intersection report", "Rare multi-way-stop hesitations flagged for iteration.", "Telemetry → Iteration", 1, "Watch", atts=[L("longtail_report.pdf")]),
            ev("2026-01-23", "Monthly safety report", "First full month at full availability summarized.", "Aisha Bello", 2, "Report", atts=[L("monthly_safety.pdf")]),
            ev("2026-02-06", "Comfort-metric regression watch", "New tuning watched for comfort side effects.", "Telemetry", 0, "Watch"),
            ev("2026-01-02", "New-year traffic baseline", "Metrics re-baselined after holiday traffic patterns.", "Telemetry", 0, "Watch"),
            ev("2026-01-16", "Per-market metric split", "Safety metrics broken out by market for regulators.", "Telemetry → Regulatory", 1, "Report"),
            ev("2026-02-13", "Disengagement taxonomy v2", "Refined labels for why drivers take over.", "Sofia Marenko", 1, "Report", atts=[L("disengagement_taxonomy.pdf")]),
            ev("2026-02-20", "Quarter retro metrics", "Quarter-over-quarter trends compiled for leadership.", "Sofia Marenko", 1, "Report"),
        ]},
        {"id": "incidents", "label": "Incidents", "category": "incidents", "events": [
            ev("2025-12-14", "Phantom-braking cluster", "A localized spike near one overpass design.", "On-call", 2, "Respond", quote="Repeated hard-brakes at one overpass; geofenced within hours.", sig="First post-launch incident; contained without a recall."),
            ev("2025-12-16", "Overpass mitigation", "Geofence plus a perception patch in shadow mode.", "Perception ML", 1, "Respond"),
            ev("2025-12-21", "Phantom-braking post-mortem", "Blameless review; data campaign queued for 3.1.", "Aisha Bello", 2, "Review", atts=[L("postmortem_overpass.pdf")]),
            ev("2026-01-05", "Update-stall incident", "A CDN edge fault stalls updates in one region.", "Cloud Platform", 2, "Respond", quote="3% of a region stuck mid-update; rolled forward cleanly.", sig="No driving impact, but a delivery-reliability gap."),
            ev("2026-01-07", "Stall mitigation", "Failover to a second CDN; stuck cars recovered.", "Dev Anand", 1, "Respond"),
            ev("2026-01-12", "Update-stall post-mortem", "Adds multi-CDN as a launch-blocker for future OTAs.", "Dev Anand", 1, "Review", atts=["postmortem_cdn.pdf"]),
            ev("2026-02-02", "Incident trend review", "Two incidents in two months, both contained; trend flat.", "Aisha Bello", 1, "Review"),
        ]},
        {"id": "iteration", "label": "Iteration", "category": "iteration", "events": [
            ev("2025-12-30", "3.1 backlog groomed", "Beta and incident learnings sorted into the next cycle.", "Lena Ortiz", 1, "Plan"),
            ev("2026-01-08", "Auto lane-change resumes", "The launch-cut behavior re-enters active development.", "Vehicle Software", 2, "Build", sig="Brings back the feature deferred to protect the launch date.", quote="Full auto lane-change is the headline of 3.1."),
            ev("2026-01-15", "Overpass data campaign", "Targeted collection from the post-mortem ships to labeling.", "Perception ML", 1, "Build"),
            ev("2026-01-22", "Comfort tuning experiment", "Field experiment on smoother deceleration profiles.", "Vehicle SW, Mia Chen", 1, "Build"),
            ev("2026-01-29", "Intersection-handling spike", "Engineering spike on the long-tail intersection cases.", "Vehicle Software", 1, "Build"),
            ev("2026-02-10", "3.1 scope review", "Cross-functional review sets the 3.1 commitment.", "Lena Ortiz, Raj Patel", 2, "Plan"),
            ev("2026-02-03", "Auto lane-change sim gauntlet", "The 3.1 behavior enters the simulation suite.", "Simulation, Vehicle SW", 1, "Build"),
            ev("2026-02-17", "3.1 design spike", "Design explores the auto lane-change cues.", "Sora Kim", 1, "Plan"),
            ev("2026-02-26", "3.1 safety pre-read", "Early safety framing for the 3.1 behaviors.", "Aisha Bello", 1, "Plan"),
            ev("2026-02-24", "3.1 kickoff", "Next release formally kicks off; cycle begins again.", "Lena Ortiz", 3, "Plan", sig="Closes the loop from launch learnings back into product."),
        ]},
    ],
}

DATA = {
    "title": "Voltera Drive Assist 3.0 — Rollout Timeline",
    "subtitle": "Fully synthetic sample data for a fictional EV software rollout. No real people, companies, or files.",
    "categories": CATEGORIES,
    "tabs": [tab_product, tab_eng, tab_validation, tab_beta, tab_rollout, tab_post],
}


def _shift(date_str, days):
    try:
        return (datetime.strptime(date_str, "%Y-%m-%d").date() + timedelta(days=days)).isoformat()
    except ValueError:
        return date_str


def _disperse(data, seed=11):
    """Loosen the tidy phase-by-phase cadence: shift each workstream by an
    irregular offset and stretch the gaps between its events (sometimes by
    weeks), so the timeline reads like real project documentation — overlapping,
    revisited, logged at uneven times — rather than a clean march. Order within
    each group is preserved, so phases stay in sequence. Deterministic (seeded).
    """
    rng = random.Random(seed)
    for tab in data["tabs"]:
        for g in tab["groups"]:
            evs = sorted(g["events"], key=lambda e: e["date"])
            base = rng.choice([-12, -8, -4, -1, 3, 7, 12, 18])
            cum = 0
            for e in evs:
                cum += rng.choice([0, 0, 1, 2, 4, 7, 12, 22, 40])  # mostly small, sometimes a long pause
                e["date"] = _shift(e["date"], base + cum)
            g["events"] = evs


def _slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-") or "x"


def _pdf_escape(s):
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _minimal_pdf(name):
    """Return the bytes of a tiny, valid one-page PDF labelled with ``name``.

    The timeline links attachment chips to real files so the published demo is
    clickable; since the attachments are fictional, each is a small placeholder
    PDF that says so. Hand-built (zero dependencies) with a correct xref table so
    browsers' built-in PDF viewers accept it.
    """
    title = _pdf_escape(name)
    note = _pdf_escape("Synthetic sample attachment - Archive Reconstruction Platform demo.")
    stream = ("BT /F1 18 Tf 72 720 Td (%s) Tj /F1 11 Tf 0 -28 Td (%s) Tj ET"
              % (title, note)).encode("latin-1", "replace")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref_pos = len(out)
    n = len(objs) + 1
    out += b"xref\n0 %d\n" % n
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (n, xref_pos)
    return bytes(out)


# A canonical 1x1 transparent PNG (valid bytes) for image attachments.
_PNG_1x1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)

_TEXT_EXTS = {"csv", "json", "md", "txt", "log", "xml", "yaml", "yml", "html"}

# Extensions a browser opens inline (rather than downloading) when served by a
# static host like GitHub Pages, which sets Content-Type purely by extension.
_INLINE_EXTS = {"pdf", "png"} | _TEXT_EXTS


def _attachment_ext(name):
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def _href_filename(name):
    """The on-disk/href filename for a placeholder. Inline-friendly types keep
    their own extension; office/archive/binary types (.xlsx, .zip, .fig, ...)
    get a ``.pdf`` appended so the link opens inline in the browser instead of
    downloading a file that won't open in its native app. The chip still shows
    the real name (e.g. ``roadmap.xlsx``)."""
    safe = _safe_file(name)
    return safe if _attachment_ext(name) in _INLINE_EXTS else safe + ".pdf"


def _placeholder_bytes(name):
    """Bytes for a placeholder attachment that opens inline, chosen by
    extension: a 1x1 PNG, readable text/CSV/JSON, or a real one-page PDF for
    ``*.pdf`` and for every office/archive/binary type (served from a ``.pdf``
    href). Never a file whose content contradicts how it's served (which is what
    made the published links fail to open)."""
    ext = _attachment_ext(name)
    if ext == "png":
        return _PNG_1x1
    if ext == "csv":
        return ("file,note\r\n%s,synthetic placeholder\r\n" % name).encode("utf-8")
    if ext == "json":
        return json.dumps({"file": name, "note": "Synthetic sample attachment (demo placeholder)"},
                          indent=2).encode("utf-8")
    if ext in _TEXT_EXTS:
        return ("Synthetic sample attachment: %s\n"
                "Archive Reconstruction Platform demo - placeholder content.\n" % name).encode("utf-8")
    # pdf and every office/archive/binary type -> a real one-page PDF
    return _minimal_pdf(name)


_SAFE_FILE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_file(name):
    return _SAFE_FILE_RE.sub("_", name)


def _materialize_attachments(data, docs_root):
    """Make every attachment a real, openable file under ``docs/files/``.

    Normalizes each event's ``attachments`` to ``{name, href}`` objects (so the
    timeline renders them all as links, not just some) and writes a placeholder
    file for each unique name — a tiny PDF for ``*.pdf``, a text stub otherwise.
    Returns the number of files written.
    """
    files_dir = os.path.join(docs_root, "files")
    if os.path.isdir(files_dir):
        for f in os.listdir(files_dir):
            if f != "README.md":
                try:
                    os.remove(os.path.join(files_dir, f))
                except OSError:
                    pass
    os.makedirs(files_dir, exist_ok=True)

    names = set()
    for tab in data["tabs"]:
        for g in tab["groups"]:
            for e in g["events"]:
                atts = e.get("attachments")
                if not atts:
                    continue
                norm = []
                for a in atts:
                    nm = a["name"] if isinstance(a, dict) else a
                    norm.append({"name": nm, "href": "files/" + _href_filename(nm)})
                    names.add(nm)
                e["attachments"] = norm

    for nm in sorted(names):
        with open(os.path.join(files_dir, _href_filename(nm)), "wb") as fh:
            fh.write(_placeholder_bytes(nm))
    return len(names)


def _attach_sources(data, docs_root):
    """Give every event a source email: write a synthetic evidence email per
    event and link the card to it, so each row has a '📧 Open email' link (like
    the reference timeline). Preserves any 'added/edited by' attribution.

    Emails are written under docs/evidence/ and linked with docs-relative hrefs
    (evidence/...), so they resolve next to docs/timeline.html — both on GitHub
    Pages and when the page is opened locally.
    """
    ev_root = os.path.normpath(os.path.join(docs_root, "evidence"))
    if os.path.isdir(ev_root):
        for root, _dirs, files in os.walk(ev_root):
            for f in files:
                if f.endswith(".txt"):
                    os.remove(os.path.join(root, f))

    count = 0
    for tab in data["tabs"]:
        tabid = tab["id"]
        tdir = os.path.join(ev_root, tabid)
        os.makedirs(tdir, exist_ok=True)
        n = 0
        for g in tab["groups"]:
            for e in g["events"]:
                n += 1
                fname = "%03d_%s.txt" % (n, _slugify(e["title"])[:40])
                lines = [
                    "From: %s" % (e.get("parties") or "Voltera Team"),
                    "Sent: %s" % e["date"],
                    "Subject: %s" % e["title"],
                ]
                atts = e.get("attachments") or []
                if atts:
                    names = [a["name"] if isinstance(a, dict) else a for a in atts]
                    lines.append("Attachments: %s" % ", ".join(names))
                body = e.get("summary", "") or e["title"]
                if e.get("quote"):
                    body += "\n\n\"%s\"" % e["quote"]
                if e.get("significance"):
                    body += "\n\nSignificance: %s" % e["significance"]
                lines += ["", body]
                with open(os.path.join(tdir, fname), "w", encoding="utf-8") as fh:
                    fh.write("\n".join(lines) + "\n")

                prev = e.get("source") or {}
                src = {"type": "email", "label": "Open email",
                       "href": "evidence/%s/%s" % (tabid, fname)}
                if prev.get("by"):
                    src["by"] = prev["by"]
                if prev.get("at"):
                    src["at"] = prev["at"]
                e["source"] = src
                count += 1
    return count


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "..", "examples", "events.json")
    out = os.path.normpath(out)
    docs_root = os.path.normpath(os.path.join(here, "..", "docs"))
    _disperse(DATA)
    n_files = _materialize_attachments(DATA, docs_root)
    n_evidence = _attach_sources(DATA, docs_root)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(DATA, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    total = sum(len(g["events"]) for tab in DATA["tabs"] for g in tab["groups"])
    print("Wrote %d events across %d tabs to %s" % (total, len(DATA["tabs"]), out))
    print("Wrote %d evidence email(s) to docs/evidence/" % n_evidence)
    print("Wrote %d attachment placeholder(s) to docs/files/" % n_files)


if __name__ == "__main__":
    main()
