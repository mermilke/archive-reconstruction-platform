/*!
 * sample-threads.js — synthetic demo data for the in-browser dedup tool.
 *
 * A verbatim copy of examples/threads/ (the six fictional "Voltera / Drive
 * Assist 3.0" thread exports) so the live page has a one-click "Load sample
 * data" button — a visitor with no email exports on hand can still see the
 * branch-aware dedup work. All content is fully synthetic.
 *
 * If examples/threads/ changes, regenerate this file to match.
 *
 * Exposes window.SAMPLE_THREADS (browser) / module.exports (Node) as an array
 * of {name, content} records — the same shape the file picker produces.
 */
(function (global) {
  "use strict";

  var SAMPLE_THREADS = [
    {
      name: "thread_forward_attachment.txt",
      content:
"From: Raj Patel <raj.patel@voltera.example>\n" +
"Sent: 2025-11-25 14:20\n" +
"To: Lena Ortiz <lena.ortiz@voltera.example>\n" +
"Subject: FW: Drive Assist 3.0 - safety sign-off\n" +
"Attachments: safety_case_final.pdf\n" +
"\n" +
"Lena, forwarding the signed safety case for the record before the canary. Let me know if leadership needs the full evidence pack. Raj\n" +
"\n" +
"From: Raj Patel <raj.patel@voltera.example>\n" +
"Sent: 2025-11-24 15:30\n" +
"To: Lena Ortiz <lena.ortiz@voltera.example>\n" +
"Subject: RE: Drive Assist 3.0 - canary go/no-go\n" +
"\n" +
"Lena, perception rc3 is signed off and the release candidate build is cut. The safety case approval landed Friday. From engineering we are go for the canary. Raj\n" +
"\n" +
"From: Lena Ortiz <lena.ortiz@voltera.example>\n" +
"Sent: 2025-11-24 09:00\n" +
"To: Raj Patel <raj.patel@voltera.example>\n" +
"Subject: Drive Assist 3.0 - canary go/no-go\n" +
"\n" +
"Raj, are we go for the 1% canary next week? I need confirmation that perception rc3 and the safety case are both signed off before I brief leadership. Lena\n"
    },
    {
      name: "thread_forward_noattach.txt",
      content:
"From: Raj Patel <raj.patel@voltera.example>\n" +
"Sent: 2025-11-25 14:20\n" +
"To: Lena Ortiz <lena.ortiz@voltera.example>\n" +
"Subject: FW: Drive Assist 3.0 - safety sign-off\n" +
"\n" +
"Lena, forwarding the signed safety case for the record before the canary. Let me know if leadership needs the full evidence pack. Raj\n" +
"\n" +
"From: Raj Patel <raj.patel@voltera.example>\n" +
"Sent: 2025-11-24 15:30\n" +
"To: Lena Ortiz <lena.ortiz@voltera.example>\n" +
"Subject: RE: Drive Assist 3.0 - canary go/no-go\n" +
"\n" +
"Lena, perception rc3 is signed off and the release candidate build is cut. The safety case approval landed Friday. From engineering we are go for the canary. Raj\n" +
"\n" +
"From: Lena Ortiz <lena.ortiz@voltera.example>\n" +
"Sent: 2025-11-24 09:00\n" +
"To: Raj Patel <raj.patel@voltera.example>\n" +
"Subject: Drive Assist 3.0 - canary go/no-go\n" +
"\n" +
"Raj, are we go for the 1% canary next week? I need confirmation that perception rc3 and the safety case are both signed off before I brief leadership. Lena\n"
    },
    {
      name: "thread_main_full.txt",
      content:
"From: Raj Patel <raj.patel@voltera.example>\n" +
"Sent: 2025-11-26 16:45\n" +
"To: Lena Ortiz <lena.ortiz@voltera.example>\n" +
"Subject: RE: Drive Assist 3.0 - canary go/no-go\n" +
"Attachments: rollout_runbook.pdf\n" +
"\n" +
"Runbook attached. The auto-halt trips if the canary disengagement rate regresses beyond the beta baseline. Raj\n" +
"\n" +
"From: Lena Ortiz <lena.ortiz@voltera.example>\n" +
"Sent: 2025-11-25 10:10\n" +
"To: Raj Patel <raj.patel@voltera.example>\n" +
"Subject: RE: Drive Assist 3.0 - canary go/no-go\n" +
"\n" +
"Great. For the leadership review I will need the rollout runbook and the auto-halt criteria attached. Can you send those over? Lena\n" +
"\n" +
"From: Raj Patel <raj.patel@voltera.example>\n" +
"Sent: 2025-11-24 15:30\n" +
"To: Lena Ortiz <lena.ortiz@voltera.example>\n" +
"Subject: RE: Drive Assist 3.0 - canary go/no-go\n" +
"\n" +
"Lena, perception rc3 is signed off and the release candidate build is cut. The safety case approval landed Friday. From engineering we are go for the canary. Raj\n" +
"\n" +
"From: Lena Ortiz <lena.ortiz@voltera.example>\n" +
"Sent: 2025-11-24 09:00\n" +
"To: Raj Patel <raj.patel@voltera.example>\n" +
"Subject: Drive Assist 3.0 - canary go/no-go\n" +
"\n" +
"Raj, are we go for the 1% canary next week? I need confirmation that perception rc3 and the safety case are both signed off before I brief leadership. Lena\n"
    },
    {
      name: "thread_partial_early.txt",
      content:
"From: Raj Patel <raj.patel@voltera.example>\n" +
"Date: 2025-11-24 20:30\n" +
"To: Lena Ortiz <lena.ortiz@voltera.example>\n" +
"Subject: RE: Drive Assist 3.0 - canary go/no-go\n" +
"\n" +
"Lena, perception rc3 is signed off and the release candidate build is cut. The safety case approval landed Friday. From engineering we are go for the canary. Raj\n" +
"\n" +
"From: Lena Ortiz <lena.ortiz@voltera.example>\n" +
"Date: 2025-11-24 14:00\n" +
"To: Raj Patel <raj.patel@voltera.example>\n" +
"Subject: Drive Assist 3.0 - canary go/no-go\n" +
"\n" +
"Raj, are we go for the 1% canary next week? I need confirmation that perception rc3 and the safety case are both signed off before I brief leadership. Lena\n"
    },
    {
      name: "thread_partial_mid.txt",
      content:
"From: Lena Ortiz <lena.ortiz@voltera.example>\n" +
"Sent: 2025-11-25 10:10\n" +
"To: Raj Patel <raj.patel@voltera.example>\n" +
"Subject: RE: Drive Assist 3.0 - canary go/no-go\n" +
"\n" +
"Great. For the leadership review I will need the rollout runbook and the auto-halt criteria attached. Can you send those over? Lena\n" +
"\n" +
"From: Raj Patel <raj.patel@voltera.example>\n" +
"Sent: 2025-11-24 15:30\n" +
"To: Lena Ortiz <lena.ortiz@voltera.example>\n" +
"Subject: RE: Drive Assist 3.0 - canary go/no-go\n" +
"\n" +
"Lena, perception rc3 is signed off and the release candidate build is cut. The safety case approval landed Friday. From engineering we are go for the canary. Raj\n" +
"\n" +
"From: Lena Ortiz <lena.ortiz@voltera.example>\n" +
"Sent: 2025-11-24 09:00\n" +
"To: Raj Patel <raj.patel@voltera.example>\n" +
"Subject: Drive Assist 3.0 - canary go/no-go\n" +
"\n" +
"Raj, are we go for the 1% canary next week? I need confirmation that perception rc3 and the safety case are both signed off before I brief leadership. Lena\n"
    },
    {
      name: "thread_single_open.txt",
      content:
"From: Lena Ortiz <lena.ortiz@voltera.example>\n" +
"Sent: 2025-11-24 09:00\n" +
"To: Raj Patel <raj.patel@voltera.example>\n" +
"Subject: Drive Assist 3.0 - canary go/no-go\n" +
"\n" +
"Raj, are we go for the 1% canary next week? I need confirmation that perception rc3 and the safety case are both signed off before I brief leadership. Lena\n"
    }
  ];

  if (typeof module !== "undefined" && module.exports) {
    module.exports = SAMPLE_THREADS;
  } else {
    global.SAMPLE_THREADS = SAMPLE_THREADS;
  }
})(typeof self !== "undefined" ? self : this);
