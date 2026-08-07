# Email draft: Prof. Hao Wang

*Draft for review. Replace the bracketed items and delete this header before sending.*

---

**To:** Prof. Hao Wang
**Subject:** DRIFT paper ready for submission: proposed venues (TMLR and NAACL 2027)

---

Dear Prof. Wang,

The DRIFT work is complete and I would like to discuss submitting it. A one-page summary of the thesis, the hypothesis, the novelty and the results is attached; the full report, code and all artifacts are at [repository link].

Briefly: DRIFT is a controlled framework for comparing forgetting policies in LLM agent memory. It holds the substrate, extraction, retrieval, answer model and judge constant and varies only the forgetting rule across seven settings. Across two public benchmarks we find that bitemporal contradiction invalidation is statistically equivalent to append-only memory on accuracy, with the paired difference bounded within 2.5 points, while spending 12 percent fewer tokens; that novelty-gated writing raises staleness by a factor of 4.5 with p < 0.001, because a correction is textually near-identical to the fact it corrects and is rejected as a duplicate; and that a structure-aware but time-blind ablation is significantly worse than the bitemporal policy on both accuracy and staleness, which attributes the advantage to bitemporal semantics rather than to graph structure in general.

I propose two submission targets and would value your view on both, and on the ordering.

**Transactions on Machine Learning Research (TMLR)** <https://jmlr.org/tmlr/index.html>

TMLR is an archival journal published under the JMLR umbrella, indexed with a DOI, and using rolling submissions with no deadline. Reviews are returned within roughly four weeks and decisions within roughly two months. Its acceptance criteria are whether the claims are supported by convincing evidence and whether some individuals in the community would be interested in the findings; it deliberately does not gate on novelty or state-of-the-art results. Given that our contribution is a controlled study with bootstrap intervals, paired significance tests, a replication across two benchmarks and an explicit threats-to-validity section, this appears to be the closest match. TMLR also participates in the Journal-to-Conference track with NeurIPS, ICML and ICLR, so an accepted paper can be presented at one of those conferences without a second review.

**NAACL 2027** <https://2027.naacl.org/>

NAACL 2027 will be held in San Francisco from 1 to 5 June 2027. Submission is through the ACL Rolling Review; the relevant cycle closes on 12 October 2026, after which papers are committed to the conference. Acceptance would place the paper in the ACL Anthology. ARR has the practical advantage of decoupling review from venue: if the reviews suggest revision, the paper can be committed to a later venue rather than resubmitted from scratch.

My suggested plan is to submit to TMLR first, since it has no deadline and the fastest turnaround, and to prepare the ARR submission in parallel for the October cycle. I am happy to follow a different order if you prefer.

Before either submission I intend to complete one outstanding experiment. Three of our four research questions are answered on real data; the fourth, whether the policy rankings hold in multi-agent settings, is currently validated only on synthetic data. The harness is built and tested, and the remaining work is a 21-cell run. I expect this to take [N] days and believe it should be finished before we submit, as it is the most likely single point of reviewer objection.

I would welcome your feedback on the framing, the choice of venues and anything you would like changed before submission. I am happy to meet at your convenience.

Finally, if the paper is accepted at NAACL 2027, I would like to ask about the Stevens conference travel grant. Could you advise on eligibility for graduate students, the application timeline relative to the acceptance notification, and whether a faculty endorsement is required? I want to make sure I begin the process early enough.

Thank you for your guidance on this work.

Best regards,
Nandan Hemanth
[program, department]
Stevens Institute of Technology
[email] · [phone]

**Attachment:** DRIFT_SUMMARY.md, a one-page overview of the thesis, hypothesis, novelty and results.

---

## Notes before sending

- Replace `[repository link]`, `[N]`, `[program, department]`, `[email]`, `[phone]`.
- Confirm the exact name of the Stevens travel funding programme with the graduate office before sending, and adjust the closing paragraph if it is called something else.
- Attach `paper/DRIFT_SUMMARY.md`, or export it to PDF first if you prefer a formatted attachment.
- If you would rather not commit to a timeline for the multi-agent run, delete the `[N] days` estimate and say only that the experiment is outstanding.
