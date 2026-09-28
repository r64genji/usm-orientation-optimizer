# Verification Log

## Test and Build Output

```
$ npm test
> proposal_site@1.0.0 test
> node tests/verify.mjs

All verification assertions passed.

$ npm run build
> proposal_site@1.0.0 build
> node scripts/build.mjs

[BUILD] Building proposal site into dist/...
[BUILD] Copied index.html -> dist/index.html
[BUILD] Copied styles.css -> dist/styles.css
[BUILD] Copied app.js -> dist/app.js
[BUILD] Copied package.json -> dist/package.json
[BUILD] Build completed successfully.
```

## PDF Generation Output

```
$ python3 -m http.server 4180 --directory dist &
$ google-chrome --headless --no-sandbox --disable-gpu --print-to-pdf=dist/usm-optimizer-proposal.pdf --print-to-pdf-no-header --print-to-pdf-with-background http://127.0.0.1:4180/index.html
210406 bytes written to file dist/usm-optimizer-proposal.pdf
```

## PDF Inspection Output

```
$ pdfinfo dist/usm-optimizer-proposal.pdf
Title:           USM Orientation Transit Operations Proposal
Creator:         Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/150.0.0.0 Safari/537.36
Producer:        Skia/PDF m150
CreationDate:    Thu Sep 24 11:46:10 2026 +08
ModDate:         Thu Sep 24 11:46:10 2026 +08
Custom Metadata: no
Metadata Stream: no
Tagged:          yes
UserProperties:  no
Suspects:        no
Form:            none
JavaScript:      no
Pages:           12
Encrypted:       no
Page size:       594.96 x 841.92 pts (A4)
Page rot:        0
File size:       210705 bytes
Optimized:       no
PDF version:     1.4
```

## Cover Render Output

```
$ pdftoppm -f 1 -singlefile -png -r 72 dist/usm-optimizer-proposal.pdf dist/usm-cover
$ ls -la proposal_site/dist/usm-optimizer-proposal.pdf proposal_site/dist/usm-cover.png
-rw-r--r-- 1 user user 210705 Sep 24 11:46 proposal_site/dist/usm-optimizer-proposal.pdf
-rw-r--r-- 1 user user  58975 Sep 24 11:46 proposal_site/dist/usm-cover.png
```
## Targeted Claim Replacements Verified

1. **Route Topography & Speed**: Replaced southern-to-northern route, 25 km/h, and electric torque statements with explicit notice that route map is schematic based on repository coordinates, and exact cycle times and speeds remain unmeasured.
2. **Passenger Dwell & Capacity**: Replaced 1.8s passenger dwell and guaranteed counts with conservative 180s full-coach boarding and 180s alighting baseline; noted exact electric capacity is unmeasured; noted headcounts occur at stations. Corrected drop-off bay table on Page 8 to reflect conservative 180s alighting baseline and unmeasured electric capacity instead of obsolete 75s/50s and 44/30 counts.
3. **Venue Allocation Trigger**: Replaced 2,800 DTSP trigger with rule that assignment to DTSP vs Dewan Budaya G03 must be fixed pre-event from verified attendance and confirmed capacity, and changed only by named command lead, with G03 (~500 seats) as active destination.
4. **Attendance & Schedule Hard Gate**: Replaced 3,500 all-seated / 08:30 claim with statement that total attendance is unresolved, the hard gate requires all assigned students seated before default 09:00:00, and dispatch clocks will be set after rehearsal.
5. **Communications Plan**: Replaced specific VHF radio channels with rule that radio channel allocation is unverified and operations must use the approved event communications plan.
6. **Proposal Status & Efficiency Claims**: Removed unsupported claims of no unscheduled layovers, maximum efficiency, and zero gridlock. Labeled document as a candidate proposal pending simulation and field validation. Added concise Provenance Legend and Operational Unknowns Register (owner, measurement plan, fallback).
