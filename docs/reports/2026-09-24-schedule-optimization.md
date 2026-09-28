# Schedule optimization record

## Purpose

This document records the schedule optimization work run on 24 September 2026. It covers the search space, assumptions, tested policies, measured results, mistakes found during the work, and the current recommendation.

The affected comparisons were rerun after consolidation commit `da6047d` and documentation commit `9e6ded9`. The post-merge results below replace the earlier pre-merge schedule numbers where they differ.

The goal was to reduce total student waiting across the 3,543-student campus cohort while keeping every student seated before 09:00 and keeping PPSL work manageable.

This is a simulation result, not a claim that every clock has been measured in the field. The comparison uses the same resolved demand and physical rules for every candidate.

## Fixed operating context

The searches kept these rules fixed unless a test explicitly varied an uncertain estimate:

- Full cohort: 3,543 students across eight hostels.
- Fleet: eight buses, exactly five coaches and three electric buses.
- One usable door per bus.
- The same buses loop from the RST boarding area to DTSP and return.
- Coach capacity: 80 students.
- Electric capacity sensitivity range: 70, 80, and 83 students.
- Full-load boarding dwell: 180 seconds.
- Full-load alighting dwell: 180 seconds.
- Outbound bus travel: 210 seconds.
- Return bus travel sensitivity range: 243 to 300 seconds.
- Origin turnaround and re-queue allowance: 60 seconds.
- Two active boarding berths in the recommended plan.
- DTSP allocation: 3,000 students.
- G03 overflow allocation: 543 students in the full cohort case.
- No checks or screening at DTSP doors.
- Hall access is open from the start.
- Required gathering-area headcounts remain in place.
- The deadline is 09:00.

The central bus loop calculation is:

`180 boarding + 210 outbound + 180 alighting + 243 return + 60 turnaround = 873 seconds`

That is 14 minutes 33 seconds. The conservative return case gives a 930-second loop, or 15 minutes 30 seconds.

## Objectives

Candidates were compared on:

- Total student waiting, in student-seconds or student-hours.
- Mean waiting per student.
- Outdoor exposed waiting.
- Last hall-area arrival.
- Last seated completion.
- Late and unfinished students.
- Worst hostel mean waiting.
- Peak PPSL needed at the boarding berths.

A plan was feasible only when all 3,543 students completed and no student was late.

## First bounded policy sweep

The first sweep tested 112 combinations:

- Administrative group targets: 20, 30, 40, 50, 60, 70, and 80.
- Simultaneous boarding berths: one, two, three, and four.
- Release intervals: immediate, 30 seconds, 60 seconds, and 120 seconds.

Seventy candidates passed the punctuality gate. The first apparent minimum was a 40-student target, four berths, and immediate release:

- Total wait: 2,968.9 student-hours.
- Mean wait: 50.28 minutes per student.
- Outdoor exposure: 560.1 student-hours.
- Peak boarding PPSL: eight.

A 40-student target with two berths produced 2,971.2 student-hours. It needed four boarding PPSL and added only 2.31 aggregate student-hours, or 2.35 seconds per student, compared with four berths.

This established that two berths were the better staff tradeoff. The later continuous-stream correction changed the interpretation of the group-size result, as documented below.

## Electric capacity and bus-loop sensitivity

Singapore single-deck electric buses commonly carry about 80 passengers. Published examples include 28 seated plus 52 standing, while the Linkker LM312 is listed at 83 passengers. The robust search used 70 as a low-capacity case, 80 as the planning estimate, and 83 as the upper reference.

A second search ran 120 simulations:

- 20 candidate policies.
- Electric capacities of 70, 80, and 83.
- Return travel of 243 and 300 seconds.

All 20 policies remained feasible. Before the continuous-stream correction, the robust Pareto comparison favored 70-person administrative groups with two or four berths. The two-berth version halved peak berth staffing from eight PPSL to four.

The useful result from this search was not the 70-person target. It was the stability of the two-berth plan under the tested vehicle capacity and return-time ranges.

## PPSL assumption used in the search

The berth staffing estimate was two PPSL per active berth:

1. One PPSL at the bus door for boarding control and count continuity.
2. One PPSL at the queue head to form and release the next load.

Two berths therefore require four boarding PPSL. Four berths require eight. Fixed headcount, crossing, walking-corridor, and destination posts sit outside this berth-only count.

This is a reasoned staffing model, not a measured roster. It is enough to compare berth choices, but it is not a full deployment plan for all 154 PPSL.

## Individual hostel release experiments

Each hostel was delayed independently while the other seven retained their original release. Delays were tested in five-minute increments and then extended to later windows.

The independent marginal optima were approximately:

- Tekun: 20 minutes later.
- Saujana: 50 minutes later.
- Restu: 70 minutes later.
- Aman Damai: 90 minutes later.
- Indah Kembara: 90 minutes later.
- Bakti Fajar Permai: 90 minutes later.
- Fajar Harapan: 100 minutes later.
- Cahaya Gemilang: 100 to 110 minutes later.

These values cannot be applied together. Delaying every hostel to its individual optimum creates synchronized arrival pulses and changes shared-resource demand. A combined test that released all walking hostels together at a later time produced 49 to 745 late students, depending on the schedule.

The correct lesson was to stagger corridor waves, not to stack the independent optima.

## Release-order search

The RST hostels share the same bus fleet, so the search tested:

- All six sequential orders of Restu, Saujana, and Tekun.
- Every reasonable pair-first and pair-second arrangement.
- All three released together.
- Zero, five, and ten-minute separation.
- Central and conservative bus assumptions.

The final completion time was almost unchanged across RST orders. The fleet and downstream hall flow set the makespan. Release order mainly changed who waited and how much.

The post-merge rerun used the same walking releases and ten-minute RST spacing under both central and conservative bus assumptions. Total waiting ranked as follows:

1. Saujana, then Tekun, then Restu: 2,222.6 student-hours.
2. Tekun, then Saujana, then Restu: 2,228.6 student-hours.
3. Tekun, then Restu, then Saujana: 2,341.0 student-hours.
4. Saujana, then Restu, then Tekun: 2,361.1 student-hours.
5. Restu, then Saujana, then Tekun: 2,474.7 student-hours.
6. Restu, then Tekun, then Saujana: 2,480.8 student-hours.
7. All three together: 2,650.5 student-hours.

The two small-hostel-first orders are practically tied. Saujana-first saves 6.0 aggregate student-hours, or about six seconds per student, compared with Tekun-first. Restu-first still does not finish seating earlier and adds about 252 student-hours against the best order.

## Parallel walking waves

Walking hostels were grouped by independent destination approach:

- South corridor: Aman Damai, Fajar Harapan, and Indah Kembara.
- North corridor: Bakti Fajar Permai and Cahaya Gemilang.
- RST bus branch: Tekun, Saujana, and Restu.

The search tested all six orders of these three branches with gaps from zero to 30 minutes. Thirty-eight branch schedules remained feasible under both central and conservative bus cases.

The fastest candidates completed hall-area arrival at about 99 minutes after 06:30. More aggressive delay reduced recorded waiting but pushed the last arrival later. This produced a clear tradeoff between student waiting and completion margin.

## Refined schedule search

A final grid tested 144 schedules around the best region. It varied:

- South walking release: 06:30 or 06:35.
- North walking release: 06:30, 06:35, or 06:40.
- Tekun release: 06:35 or 06:40.
- Saujana gap after Tekun: five or ten minutes.
- Restu gap after Saujana: five, ten, or fifteen minutes.
- Two or four boarding berths.

The original 144-candidate run happened before the continuous-stream merge. The post-merge rerun covered 48 affected simulations first, then reran the feasible schedule neighborhood on the consolidated engine. The new engine changed queue packing and multi-berth dispatch, so the old waiting values are retained only as historical results.

The minimum-wait plan in that grid was:

| Time | Release |
|---|---|
| 06:30 | Aman Damai, Fajar Harapan, and Indah Kembara |
| 06:35 | Bakti Fajar Permai and Cahaya Gemilang |
| 06:40 | Tekun |
| 06:50 | Saujana |
| 07:05 | Restu |

The post-merge minimum-wait candidate uses four boarding berths and immediate dispatch whenever a bus and enough queued students are ready.

Conservative result:

- All students reached the hall area by about 07:55.
- All students were seated by about 08:24.
- Zero late students.
- Zero unfinished students.
- Total wait: 2,104.9 student-hours.
- Mean wait: 35.65 minutes per student.
- Outdoor wait: 347.8 student-hours.
- Peak boarding PPSL: eight.

Compared with the post-merge conservative immediate-release baseline, the schedule saves about 859.9 student-hours, a 29.0 percent reduction. Outdoor waiting falls by about 203.6 student-hours. Seating completion remains about 08:24.

The same release timetable with two berths produced:

- Total wait: 2,141.6 student-hours.
- Mean wait: 36.27 minutes per student.
- Outdoor wait: 380.7 student-hours.
- Last hall-area arrival: about 08:01.
- Last seated: about 08:24.
- Peak boarding PPSL: four.

Four berths save 36.7 aggregate student-hours against two berths, about 37 seconds per student. They also reduce exposed waiting by 32.8 student-hours and move the last hall-area arrival about six minutes earlier. The cost is four additional berth PPSL.

The simulated hostel means for this candidate were:

| Hostel | Mean wait |
|---|---:|
| Aman Damai | 11.8 min |
| Cahaya Gemilang | 18.6 min |
| Fajar Harapan | 23.7 min |
| Bakti Fajar Permai | 33.3 min |
| Restu | 33.6 min |
| Indah Kembara | 35.5 min |
| Tekun | 47.4 min |
| Saujana | 56.1 min |

Saujana is now the largest hostel-level mean wait in this candidate. The consolidation removed the earlier Indah Kembara result as the dominant bottleneck.

## Continuous-stream correction

The early batch-size results were misleading.

The intended operation has a long continuous student queue. Buses fill to their own safe capacities regardless of administrative group boundaries. If the queue contains 70-person groups and an 80-person coach arrives, the engine should take 70 students from one group and 10 from the next. The remaining 60 stay at the front for the following vehicle.

The consolidated engine now does this. It:

- Packs coaches to 80 where capacity permits.
- Packs electric buses to their configured capacity.
- Splits oversized administrative groups at the vehicle.
- Keeps the remainder at the front of the queue.
- Combines remainders with following students.
- Prevents administrative target size from materially changing transport results.

The committed group-size invariance tests compare targets of 20, 40, and 80 under the canonical case. They pass. The post-merge sensitivity rerun also compared those targets after changing electric capacity and return time.

Central case rerun:

- 3,543 completed.
- Zero unfinished.
- Zero late.
- Targets 20, 40, and 80 each produced 10,492,275 waiting student-seconds.
- Each produced 28 boarding pulses.
- Each reached the hall area by 4,378 seconds and finished seating by 6,855 seconds.

Conservative sensitivity case:

- Targets 20 and 40 produced 10,673,394 waiting student-seconds.
- Target 80 produced 10,575,654 waiting student-seconds.
- All three completed with zero late or unfinished students and 29 boarding pulses.

The conservative 80-target difference is 97,740 student-seconds, about 27.2 student-hours or 27.6 seconds per student. That is small compared with the roughly 860 student-hours saved by release timing. It also appears only when the electric capacity is overridden to 70 while the administrative target is 80. Administrative batch size remains a supervision choice, not the main transport control.

The focused consolidation verification passed nine tests covering continuous-stream invariance, full bus packing, and full-cohort optimization.

The corrected conclusion is simple. A 70-person administrative batch does not reduce transport waiting. Group size remains useful for headcounts, escorts, identity continuity, and radio communication. Bus loading should remain a continuous stream that fills each vehicle to capacity.

## Current recommendation

Use this as the schedule candidate for the next comparison or rehearsal:

- Release the south walking corridor at 06:30.
- Release the north walking corridor at 06:35.
- Call Tekun at 06:40.
- Call Saujana at 06:50.
- Call Restu at 07:05.
- Use four active boarding berths when the aim is minimum waiting and eight boarding PPSL are available.
- Use two berths when PPSL availability matters more than the remaining small wait reduction. Keep four PPSL at berth operations in that version.
- Maintain one continuous boarding queue.
- Fill each bus to its verified safe capacity.
- Treat administrative groups as supervision units, not vehicle-load barriers.
- Dispatch as soon as a bus and a full safe load are available.

This schedule is the best tested post-merge minimum-wait candidate from the bounded searches. The earlier two-berth recommendation remains the lower-staff alternative, not the absolute minimum-wait result. Neither result is a universal optimum over every possible route and minute-level release combination.

## Limits and next measurements

The main remaining uncertainties are:

- Exact electric-bus model and safe standing capacity.
- Full field-measured empty return and re-queue time.
- PPSL travel and handover times between posts.
- Walking observations for hostels other than Restu.
- Indah Kembara corridor throughput and delay causes.
- Attendance variation and late reporting by hostel.

The searches handled electric capacity and return time as ranges, so these are not blockers. A rehearsal should verify the release clocks and the Indah Kembara bottleneck before operational use.

## Reproducibility note

The exploratory sweeps ran as bounded Python drivers against `usm_sim.simulate` and kept their result JSON under `/tmp` during the session. Those temporary files were not committed. The durable regression coverage now lives in:

- `tests/test_continuous_stream_group_size_invariance.py`
- `tests/test_full_bus_packing.py`
- `tests/test_full_cohort_optimization.py`
- `tests/test_continuous_streaming_multi_berth.py`

The consolidated branch was fast-forwarded into `master` at commits `da6047d` and `4c1dc0f` before this report was added.

## Post-merge rerun evidence

The rerun used the imported package at `usm_sim/__init__.py` on `master` commit `9e6ded9`.

Completed post-merge runs:

- 48 simulations covering group-size sensitivity, every reasonable RST order and parallel arrangement, and the narrowed schedule grid.
- Central electric capacity 80 with 243-second return travel.
- Conservative electric capacity 70 with 300-second return travel.
- A wider post-merge schedule grid was also attempted, but the command exceeded the execution limit before producing a complete result. No partial result from that run is reported as complete.

The durable raw result for the completed rerun was written to `/tmp/usm_post_merge_optimization_results.json` during the session. The report above contains the values needed for future comparison.
