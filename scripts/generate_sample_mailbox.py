"""Author a realistic mailbox export into examples/mailbox/ as .txt thread files.

Fully synthetic: internal email threads for a fictional EV company ("Voltera")
rolling out a "Drive Assist 3.0" software feature. This produces the kind of
messy folder the toolkit is built for — many conversations, multiple
participants, attachments, and a few duplicate/partial exports of the same
thread so the dedup pass has something to collapse.

Run:  python scripts/generate_sample_mailbox.py
Then: PYTHONPATH=src python -m arc.cli timeline-threads examples/mailbox -o threads_timeline.html
"""
import os
import random
import re
from datetime import datetime, timedelta


def _shift_date(date_str, days):
    try:
        return (datetime.strptime(date_str, "%Y-%m-%d").date() + timedelta(days=days)).isoformat()
    except ValueError:
        return date_str

P = {
    "lena": "Lena Ortiz <lena.ortiz@voltera.example>",
    "raj": "Raj Patel <raj.patel@voltera.example>",
    "tomas": "Tomás Vidal <tomas.vidal@voltera.example>",
    "aisha": "Aisha Bello <aisha.bello@voltera.example>",
    "dev": "Dev Anand <dev.anand@voltera.example>",
    "sofia": "Sofia Marenko <sofia.marenko@voltera.example>",
    "kenji": "Kenji Watanabe <kenji.watanabe@voltera.example>",
    "elena": "Elena Cruz <elena.cruz@voltera.example>",
    "nora": "Nora Fischer <nora.fischer@voltera.example>",
    "marcus": "Marcus Hale <marcus.hale@voltera.example>",
    "priya": "Priya Iyer <priya.iyer@voltera.example>",
    "mia": "Mia Chen <mia.chen@voltera.example>",
    "sora": "Sora Kim <sora.kim@voltera.example>",
    "caleb": "Caleb Reed <caleb.reed@voltera.example>",
    "dana": "Dana Olsen <dana.olsen@voltera.example>",
    "legal": "Legal Team <legal@voltera.example>",
    "oncall": "On-Call <oncall@voltera.example>",
    "yuki": "Yuki Tanaka <yuki.tanaka@voltera.example>",
    "omar": "Omar Haddad <omar.haddad@voltera.example>",
    "grace": "Grace Lin <grace.lin@voltera.example>",
    "sam": "Sam Powell <sam.powell@voltera.example>",
}


def m(person, date, time, body, atts=None):
    return {"person": person, "date": date, "time": time, "body": body, "atts": atts or []}


def C(subject, msgs, partial=None):
    """A conversation. ``partial`` (int) also emits an older export missing the
    later replies, creating duplicates for the dedup pass to collapse."""
    return {"subject": subject, "msgs": msgs, "partial": partial}


CONVERSATIONS = [
    # --- Discovery / Product ---
    C("Drive Assist 3.0 - discovery kickoff", [
        m("mia", "2024-09-09", "09:15", "Kicking off discovery on why drivers disengage today. I'll run a diary study with 30 owners over three weeks."),
        m("lena", "2024-09-09", "11:40", "Great. Tie the findings to a metric we can move so the PRD writes itself later."),
        m("mia", "2024-09-10", "08:25", "Will do — leaning toward miles-per-disengagement as the north star."),
    ]),
    C("Disengagement diary study - results", [
        m("mia", "2024-10-14", "16:05", "Study is in. Five recurring triggers; unprotected lane changes are by far the top one.", ["research_readout.pdf"]),
        m("raj", "2024-10-15", "09:30", "That matches our shadow-mode data. Lane-change hesitation is where trust breaks."),
        m("lena", "2024-10-15", "10:12", "Good. Let's make handover quality the headline of the spec."),
    ], partial=1),
    C("PRD review - Drive Assist 3.0", [
        m("lena", "2024-11-12", "09:15", "Draft PRD attached for review. Primary metric is miles-per-disengagement with comfort guardrails.", ["prd_drive_assist_3.pdf"]),
        m("raj", "2024-11-13", "14:02", "Engineering is good with scope. One flag: full auto lane-change is a stretch for the date."),
        m("aisha", "2024-11-13", "15:48", "Safety can support driver-confirmed lane change at launch; full auto needs more evidence."),
        m("lena", "2024-11-18", "10:00", "Agreed. PRD signed off with driver-confirmed only. Thanks all."),
    ], partial=2),
    C("Scope cut - defer auto lane-change to 3.1", [
        m("lena", "2024-12-09", "13:20", "Confirming we ship driver-confirmed lane changes first; full auto moves to 3.1 to protect the date."),
        m("raj", "2024-12-09", "16:45", "Works for us. It removes the hardest behavior from the critical path."),
    ]),
    C("Success metrics sign-off", [
        m("lena", "2024-10-21", "11:05", "North star: 5x miles-per-disengagement without raising hard-brake events. Objections?"),
        m("aisha", "2024-10-21", "13:30", "None — please add a comfort guardrail so we don't trade jerk for the metric."),
        m("lena", "2024-10-22", "08:50", "Added. Comfort guardrail on peak deceleration is in."),
    ]),

    # --- Design ---
    C("Interaction spec v1 for review", [
        m("sora", "2024-11-25", "10:30", "First end-to-end interaction spec attached. Engage, warn, and handover flows.", ["interaction_spec.pdf"]),
        m("raj", "2024-11-26", "09:10", "Clear. The 1.5s handover ramp is implementable on the current stack."),
    ]),
    C("Handover cue - glare problem", [
        m("aisha", "2025-02-05", "14:15", "Two cues could be missed in direct sunlight. High glare washes out the amber handover cue."),
        m("sora", "2025-02-06", "09:40", "Adding a haptic seat cue as a redundant channel so it survives glare."),
        m("aisha", "2025-02-07", "11:20", "That resolves the finding for me. Thanks."),
    ]),
    C("Design freeze - Drive Assist 3.0", [
        m("sora", "2025-02-24", "17:00", "Interaction and visual spec are frozen for build. Final spec attached.", ["design_spec_final.pdf"]),
        m("raj", "2025-02-25", "08:30", "Got it — building to this. Variances go through you."),
    ]),

    # --- Perception ---
    C("Perception 3.0 - benchmark results", [
        m("tomas", "2024-11-15", "15:20", "New backbone beats production by 7% mAP on the night/rain slice, latency within budget."),
        m("raj", "2024-11-15", "16:05", "Strong. Let's schedule the architecture review for the fusion design."),
    ]),
    C("Tunnel false positives in shadow mode", [
        m("tomas", "2025-01-20", "08:55", "Shadow mode is flagging phantom braking entering tunnels. Looks like an exposure shift."),
        m("sofia", "2025-01-20", "10:30", "Sim reproduces it. We'll need a targeted tunnel data campaign."),
        m("tomas", "2025-02-18", "13:10", "Retrained on the new tunnel data; false positives down 90%."),
    ], partial=1),
    C("Perception model rc1 freeze", [
        m("tomas", "2025-03-25", "12:00", "Candidate v3.0-rc1 is frozen and handed to validation. Model card attached.", ["model_card.pdf"]),
        m("sofia", "2025-03-25", "14:20", "Received. Kicking off the full sim campaign tonight."),
    ]),
    C("Perception sign-off rc3", [
        m("tomas", "2025-07-08", "11:30", "Validation accepts rc3. Perception is signed off for the beta program."),
        m("aisha", "2025-07-08", "12:15", "Confirmed from safety. Nice work closing the long tail."),
    ]),

    # --- Vehicle software / Cloud ---
    C("Compute budget overrun", [
        m("raj", "2025-01-08", "09:00", "The new stack is at 118% of the SoC compute budget at peak. We need to prune or offload."),
        m("dev", "2025-01-08", "10:45", "I can move the fusion pre-proc to the accelerator. Should buy headroom."),
        m("raj", "2025-02-03", "16:30", "Operator fusion plus quantization brings peak to 86%. Older HW3 cars stay in scope."),
    ]),
    C("Release candidate build cut", [
        m("raj", "2025-08-11", "18:10", "rc build is assembled with frozen perception and planner. Notes and manifest attached.", ["release_notes.md", "ota_manifest.json"]),
        m("dev", "2025-08-11", "18:40", "Pulled it into the staging channel. Shadow telemetry is flowing."),
        m("aisha", "2025-08-12", "09:15", "This is the build validation and beta run against. Locking it."),
    ], partial=2),
    C("OTA pipeline design review", [
        m("dev", "2024-11-06", "10:20", "Design for staged, reversible OTA attached. Percentage targeting with instant rollback.", ["ota_design.pdf"]),
        m("raj", "2024-11-07", "09:05", "Looks solid. The rollback path is the part safety will care about most."),
    ]),
    C("Rollback drill results", [
        m("dev", "2025-05-06", "15:40", "Game-day done. Full-fleet rollback completed in 22 minutes end to end."),
        m("aisha", "2025-05-06", "16:25", "That's the safety net we needed to greenlight a staged production rollout."),
    ]),
    C("Canary auto-halt criteria", [
        m("dev", "2025-10-28", "11:00", "Proposing the OTA auto-pauses if canary safety metrics regress beyond the beta baseline."),
        m("aisha", "2025-10-28", "13:35", "Approve. The rollout being able to stop itself without a human is the point."),
    ]),

    # --- Validation / Safety / Regulatory ---
    C("Sim run - unprotected lefts", [
        m("sofia", "2025-02-20", "08:00", "2.1M sim miles overnight. One failure cluster: gap acceptance on unprotected left turns."),
        m("raj", "2025-03-24", "17:30", "Planner fix is in. It now rejects gaps a cautious human would reject."),
        m("sofia", "2025-04-30", "09:45", "Regression suite is green across the expanded set."),
    ], partial=1),
    C("Track week - unprotected left cleared", [
        m("caleb", "2025-04-15", "16:50", "Reproduced the gap-acceptance issue on track with the foam vehicle. Matches sim exactly."),
        m("caleb", "2025-06-20", "15:10", "After the fix: 200/200 clean runs. Clearing the headline issue for beta."),
        m("aisha", "2025-06-20", "16:00", "Logged against the safety case. Thanks Caleb."),
    ]),
    C("Safety case - audit findings", [
        m("aisha", "2025-06-13", "14:30", "Independent auditor returned two findings; both on the degraded-sensor evidence."),
        m("aisha", "2025-07-15", "10:20", "Both findings closed with added evidence. Audit is satisfied."),
    ]),
    C("Safety case approved", [
        m("aisha", "2025-09-19", "11:15", "Safety leadership has approved the case for staged rollout. Final attached.", ["safety_case_final.pdf"]),
        m("lena", "2025-09-19", "12:00", "This is the gate we needed. Ticketing of the rollout can proceed."),
        m("dana", "2025-09-19", "13:30", "Excellent. Well run, everyone."),
    ], partial=2),
    C("Lead-market regulatory filing", [
        m("kenji", "2025-07-02", "09:50", "Type-approval dossier filed in the lead market. Copy attached for the record.", ["reg_filing.pdf"]),
        m("legal", "2025-07-02", "11:10", "Acknowledged. We'll track their clarification requests centrally."),
    ]),
    C("Regulator clarification - DMS data", [
        m("kenji", "2025-08-13", "10:05", "Authority wants the attention-monitoring false-negative rate before they clear us."),
        m("aisha", "2025-08-14", "09:20", "Pulling that from the human-factors study now."),
        m("kenji", "2025-09-24", "16:40", "Lead-market clearance is in. First geography is open for staged OTA."),
    ]),

    # --- Beta ---
    C("Internal fleet - cold start handover bug", [
        m("elena", "2025-05-22", "13:25", "Dogfood is seeing the seat haptic fire a beat early on cold start."),
        m("raj", "2025-05-23", "09:00", "Repro'd. Timing assumes a warm cache; fixing the first-minute path."),
        m("elena", "2025-06-05", "14:10", "Fix confirmed across the fleet. Caught before any customer saw it."),
    ]),
    C("Early access cohort selection", [
        m("elena", "2025-07-24", "10:30", "500 owners selected across climates and road types. Criteria attached.", ["cohort_criteria.pdf"]),
        m("mia", "2025-07-24", "11:45", "Can we add a cold-climate sub-cohort? I want winter data."),
        m("elena", "2025-08-28", "09:15", "Added a snow-market sub-cohort this week."),
    ]),
    C("Expanded beta - freeway merge complaints", [
        m("elena", "2025-10-23", "15:00", "Cluster of reports: merges feel timid. It waits for huge gaps on busy freeways."),
        m("raj", "2025-10-30", "17:20", "Calibrated a more natural merge gap-acceptance. Pushing to beta."),
        m("elena", "2025-11-06", "10:35", "Merge complaints down 80% week over week. The fix held."),
    ], partial=1),
    C("Beta safety metrics report", [
        m("aisha", "2025-11-20", "16:15", "Beta is at 4.6x miles-per-disengagement with hard-braking flat. Within launch criteria.", ["beta_metrics.pdf"]),
        m("lena", "2025-11-20", "17:00", "That's the number. Taking it to the go/no-go."),
    ]),

    # --- Rollout / Launch ---
    C("Canary go/no-go", [
        m("lena", "2025-11-24", "09:00", "Are we go for the 1% canary next week? I need perception rc3 and the safety case both signed off."),
        m("raj", "2025-11-24", "15:30", "Perception rc3 is signed off and the rc build is cut. Safety case landed Friday. Engineering is go."),
        m("lena", "2025-11-25", "10:10", "Great. I'll need the rollout runbook and the auto-halt criteria for the leadership review."),
        m("raj", "2025-11-26", "16:45", "Runbook attached. Auto-halt trips if the canary disengagement rate regresses beyond the beta baseline.", ["rollout_runbook.pdf"]),
    ], partial=2),
    C("Auto-halt at 10%", [
        m("dev", "2025-12-06", "08:40", "The 10% ring tripped the auto-halt overnight. Disengagement-rate spike in one region."),
        m("tomas", "2025-12-06", "09:25", "Looks weather-driven — heavy fog, not the build. Pulling the data to confirm."),
        m("dev", "2025-12-08", "11:00", "Confirmed fog. Build is clean. Resuming the rollout."),
    ]),
    C("Launch comms - embargo plan", [
        m("marcus", "2025-11-19", "13:00", "Embargo lifts with the canary on Dec 1. Briefings and Q&A are prepped.", ["press_strategy.pdf"]),
        m("legal", "2025-11-20", "10:30", "Approved, provided every claim keeps the driver-supervised framing."),
        m("marcus", "2025-12-06", "14:50", "One outlet framed the auto-halt as a stumble. Publishing the engineering explainer."),
    ]),
    C("Support readiness for rollout", [
        m("priya", "2025-10-15", "11:30", "Staffing for +50% contacts on day one. Agents trained on the handover model.", ["support_plan.xlsx"]),
        m("priya", "2025-12-07", "09:10", "Top issue is handover confusion — people ask why the car handed back in fog."),
        m("nora", "2025-12-12", "15:20", "Shipping an in-app explainer for that. Should cut repeat contacts."),
    ]),

    # --- Post-launch ---
    C("Phantom braking incident - overpass", [
        m("oncall", "2025-12-14", "07:35", "Localized hard-brake spike near one overpass design. Geofencing it now."),
        m("tomas", "2025-12-14", "09:00", "Shadow-mode patch staged. Overpass data campaign queued for 3.1."),
        m("aisha", "2025-12-21", "10:40", "Blameless post-mortem done. Contained without a recall.", ["postmortem_overpass.pdf"]),
    ], partial=2),
    C("100% availability", [
        m("dev", "2025-12-19", "12:00", "Drive Assist 3.0 is available to the full eligible fleet. Rollout complete."),
        m("lena", "2025-12-19", "12:30", "Huge milestone. Thank you all — fifteen months of work shipped."),
        m("dana", "2025-12-19", "13:15", "Congratulations to the whole team."),
    ]),
    C("3.1 kickoff", [
        m("lena", "2026-02-24", "10:00", "3.1 formally kicks off. Headline is the auto lane-change we cut from launch."),
        m("raj", "2026-02-24", "11:20", "Engineering is ready. Sim gauntlet for the new behavior is already standing up."),
    ]),
    # Long-running thread that spans the whole program and interleaves with everything.
    C("Weekly program sync - rolling notes", [
        m("lena", "2024-10-08", "09:00", "Kicking off the weekly Drive Assist sync. I'll keep rolling notes in this thread."),
        m("caleb", "2024-12-11", "09:05", "Mid-build check: perception and planner on track; compute risk flagged."),
        m("lena", "2025-03-12", "09:00", "Validation is the critical path now; beta prep starting in parallel."),
        m("caleb", "2025-06-18", "09:05", "Beta is live to early access; rollout planning underway."),
        m("lena", "2025-09-24", "09:00", "Permit cleared. Locking the launch window."),
        m("caleb", "2025-12-18", "09:05", "Rollout at 100% tomorrow. Great work, everyone."),
    ]),
    # A side-question that opens early and only gets resolved much later.
    C("Question on older-hardware support", [
        m("nora", "2024-11-19", "15:30", "Are we committing to HW3 cars for Drive Assist 3.0, or is this HW4-only?"),
        m("raj", "2025-02-04", "10:10", "After the compute optimization, HW3 stays in scope. Confirmed."),
        m("nora", "2025-08-26", "11:00", "Following up — any HW3 caveats for the launch notes?"),
        m("raj", "2025-09-02", "09:40", "Slightly reduced night range on HW3; we'll footnote it."),
    ]),
]

# --- Project: Battery Management 2.0 ---
BATTERY = [
    C("BMS 2.0 - thermal model kickoff", [
        m("yuki", "2025-01-13", "09:30", "Kicking off the new thermal model for BMS 2.0. Goal is tighter pack temperature control under fast charge."),
        m("dev", "2025-01-13", "11:00", "I'll wire the telemetry so we can validate against real pack data."),
    ]),
    C("Fast-charge curve calibration", [
        m("yuki", "2025-02-10", "10:15", "First fast-charge curve is calibrated. 10-80% is down to 28 minutes on the test pack.", ["charge_curve.csv"]),
        m("raj", "2025-02-10", "13:40", "Nice. Make sure it degrades gracefully when the pack is cold."),
        m("yuki", "2025-02-24", "09:05", "Added a cold-pack taper. It holds the cell temperature ceiling."),
    ], partial=1),
    C("Cold-weather range regression", [
        m("yuki", "2025-03-18", "14:20", "Seeing a range regression below freezing. Preconditioning isn't kicking in early enough."),
        m("dev", "2025-03-19", "09:50", "I can trigger preconditioning off the nav destination. Should recover most of it."),
        m("yuki", "2025-04-02", "11:10", "That recovered 6% winter range. Good enough to ship."),
    ]),
    C("Cell-balancing algorithm review", [
        m("yuki", "2025-03-05", "15:00", "New passive-balancing logic attached for review.", ["balancing_spec.pdf"]),
        m("raj", "2025-03-06", "10:25", "Looks right. Confirm it doesn't fight the thermal controller."),
    ]),
    C("BMS firmware rc1", [
        m("yuki", "2025-05-12", "16:30", "BMS firmware rc1 is cut and on the test fleet.", ["bms_rc1_notes.md"]),
        m("dev", "2025-05-13", "09:15", "Telemetry looks clean. No thermal events overnight."),
    ]),
    C("Range estimation accuracy", [
        m("yuki", "2025-06-20", "11:45", "Range estimator is within 3% on the mixed-driving loop now."),
        m("lena", "2025-06-20", "12:30", "That's a real customer-trust win. Great work."),
    ]),
    C("BMS 2.0 sign-off", [
        m("yuki", "2025-08-08", "10:00", "BMS 2.0 passed validation. Recommending it for the next OTA train.", ["bms_validation.pdf"]),
        m("aisha", "2025-08-08", "11:20", "Safety concurs. No open items on the pack side."),
        m("dana", "2025-08-08", "14:00", "Approved. Bundle it with the Drive Assist release."),
    ], partial=2),
    C("BMS 2.0 - rolling status", [
        m("yuki", "2025-01-20", "09:00", "Rolling status for BMS 2.0. Thermal model and fast-charge work starting."),
        m("yuki", "2025-04-10", "09:00", "Range and cold-weather issues addressed; firmware next."),
        m("yuki", "2025-07-15", "09:00", "Validation in progress; targeting the next OTA train."),
        m("yuki", "2025-10-30", "09:00", "Shipped with the rollout. Watching field telemetry for thermal margins."),
    ]),
]

# --- Project: Charging Network Expansion ---
CHARGING = [
    C("Charging network - Phase 1 site selection", [
        m("omar", "2025-02-05", "09:40", "Phase 1 shortlist is 40 sites across three metros. Map attached.", ["site_shortlist.pdf"]),
        m("grace", "2025-02-06", "10:15", "I'll start the permitting pre-checks on the downtown ones."),
    ]),
    C("Charger hardware vendor quote", [
        m("omar", "2025-02-20", "14:05", "Vendor quote for the 350kW units is in. Lead time is the long pole at 12 weeks.", ["charger_quote.xlsx"]),
        m("lena", "2025-02-21", "09:30", "Lock the price now; we can stage delivery to match permits."),
    ], partial=1),
    C("Permitting for downtown sites", [
        m("grace", "2025-03-12", "11:20", "Two downtown sites need a variance for the transformer pads."),
        m("grace", "2025-04-15", "15:40", "Variances granted. Both downtown sites are clear to build."),
    ]),
    C("Network software integration", [
        m("dev", "2025-03-25", "10:00", "Integrating the chargers with the app's find-and-pay flow."),
        m("nora", "2025-03-26", "13:15", "I'll surface live availability in the app once the API is stable."),
        m("dev", "2025-04-30", "09:45", "Availability API is live. Sub-second updates."),
    ]),
    C("Pilot site go-live", [
        m("omar", "2025-06-10", "08:50", "First pilot site is energized and passing commissioning."),
        m("grace", "2025-06-10", "09:30", "Inspection signed off. We can open it to customers."),
        m("lena", "2025-06-11", "10:00", "Open it. Let's watch reliability closely the first week."),
    ]),
    C("Charging reliability targets", [
        m("omar", "2025-07-22", "16:10", "Setting a 99% uptime target per site. Monitoring plan attached.", ["uptime_plan.pdf"]),
        m("dev", "2025-07-23", "09:25", "Wired alerts so a down stall pages within five minutes."),
    ]),
    C("Charging expansion - status", [
        m("omar", "2025-02-08", "09:00", "Status thread for the charging build-out. Site selection underway."),
        m("omar", "2025-05-02", "09:00", "Permits clearing; hardware on order."),
        m("omar", "2025-08-01", "09:00", "First pilot live; reliability monitoring in place."),
        m("grace", "2025-11-14", "09:00", "Phase 2 sites entering permitting now."),
    ]),
]

# --- Project: Mobile App Redesign ---
MOBILE = [
    C("App redesign - research findings", [
        m("mia", "2025-01-20", "10:30", "Research is in. The current app buries charging and trip history.", ["app_research.pdf"]),
        m("sam", "2025-01-21", "09:15", "Then those are the two things the new home screen should lead with."),
    ]),
    C("New navigation IA", [
        m("sora", "2025-02-12", "14:00", "New information architecture: four tabs instead of the current seven.", ["app_ia.fig"]),
        m("sam", "2025-02-13", "10:40", "Cleaner. Let's user-test the tab labels before we commit."),
        m("mia", "2025-02-27", "11:05", "Tested well. 'Charge' and 'Trips' beat the old labels handily."),
    ], partial=1),
    C("Design system update", [
        m("sora", "2025-03-10", "15:30", "Refreshed the design system — new type scale and color tokens.", ["design_system.pdf"]),
        m("nora", "2025-03-11", "09:50", "I'll start migrating the high-traffic screens first."),
    ]),
    C("Redesign beta build feedback", [
        m("nora", "2025-04-22", "13:20", "Redesign beta is out to staff. Early feedback is positive on the new home screen."),
        m("sam", "2025-04-23", "10:10", "One complaint: people miss the old quick-controls. Adding them back as a shortcut."),
    ]),
    C("App store submission", [
        m("nora", "2025-05-21", "16:00", "Submitted the redesign to the app stores."),
        m("nora", "2025-06-11", "09:30", "Both stores approved. Ready to phase the rollout."),
    ]),
    C("App redesign launch", [
        m("sam", "2025-06-25", "10:00", "Redesign is live to 100% of users. Crash rate is flat and engagement is up."),
        m("lena", "2025-06-25", "11:15", "Beautiful. Big step up in how the product feels."),
    ]),
    C("App redesign - status", [
        m("sam", "2025-01-25", "09:00", "Redesign status thread. Research done; IA next."),
        m("sam", "2025-04-05", "09:00", "Design system updated; beta soon."),
        m("sam", "2025-06-20", "09:00", "Shipping to 100% this week."),
        m("nora", "2025-09-12", "09:00", "Post-launch: adding the charging availability surface from the network team."),
    ]),
]

PROJECTS = [
    ("01_drive_assist_3.0", CONVERSATIONS),
    ("02_battery_management_2.0", BATTERY),
    ("03_charging_network", CHARGING),
    ("04_mobile_app_redesign", MOBILE),
]

_PREFIX = re.compile(r"^\s*(re|fw|fwd)\s*:\s*", re.IGNORECASE)


def base(subject):
    s = subject
    prev = None
    while s != prev:
        prev = s
        s = _PREFIX.sub("", s)
    return s.strip()


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def render_thread(subject, msgs):
    """Render messages (chronological) as a newest-first export block."""
    b = base(subject)
    blocks = []
    for i, msg in enumerate(msgs):
        subj = b if i == 0 else "RE: " + b
        lines = [
            "From: %s" % P[msg["person"]],
            "Sent: %s %s" % (msg["date"], msg["time"]),
            "Subject: %s" % subj,
        ]
        if msg["atts"]:
            lines.append("Attachments: %s" % ", ".join(msg["atts"]))
        lines.append("")
        lines.append(msg["body"])
        blocks.append("\n".join(lines))
    blocks.reverse()  # newest-first
    return "\n\n".join(blocks) + "\n"


def _write_project(project_dir, convs):
    os.makedirs(project_dir, exist_ok=True)
    files = 0
    for i, conv in enumerate(convs, 1):
        slug = _slug(base(conv["subject"]))[:48]
        full = render_thread(conv["subject"], conv["msgs"])
        with open(os.path.join(project_dir, "%02d_%s.txt" % (i, slug)), "w", encoding="utf-8") as fh:
            fh.write(full)
        files += 1
        # Optional older/partial export of the same thread -> duplicates to collapse.
        if conv.get("partial"):
            k = conv["partial"]
            partial = render_thread(conv["subject"], conv["msgs"][:k])
            with open(os.path.join(project_dir, "%02d_%s_earlier.txt" % (i, slug)), "w", encoding="utf-8") as fh:
                fh.write(partial)
            files += 1
    return files


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.normpath(os.path.join(here, "..", "examples", "mailbox"))
    os.makedirs(out_dir, exist_ok=True)
    # Clear any previously generated files (flat or nested).
    for root, _dirs, names in os.walk(out_dir):
        for name in names:
            if name.endswith(".txt"):
                os.remove(os.path.join(root, name))

    # Dispersion pass: shift each thread by an irregular offset and widen the gaps
    # between its messages (sometimes by weeks), so events scatter and interleave
    # instead of marching in tidy per-topic blocks. Deterministic (seeded).
    rng = random.Random(7)
    for _folder, project_convs in PROJECTS:
        for conv in project_convs:
            base = rng.choice([-16, -11, -7, -4, -1, 2, 6, 10, 15, 21, 28])
            cum = 0
            for msg in conv["msgs"]:
                cum += rng.choice([0, 0, 1, 2, 3, 5, 9, 16, 30, 45])  # mostly small, sometimes a long gap
                msg["date"] = _shift_date(msg["date"], base + cum)

    files = 0
    convs = 0
    msgs = 0
    for folder, project_convs in PROJECTS:
        files += _write_project(os.path.join(out_dir, folder), project_convs)
        convs += len(project_convs)
        msgs += sum(len(c["msgs"]) for c in project_convs)

    print("Wrote %d thread file(s) across %d project folder(s) "
          "(%d conversations, %d unique messages) to %s"
          % (files, len(PROJECTS), convs, msgs, out_dir))


if __name__ == "__main__":
    main()
