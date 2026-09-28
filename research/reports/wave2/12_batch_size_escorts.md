## Batch Size vs Escort Ratio Under Scarce Marshals

**TL;DR:** Moving students in small transfer batches sized exactly to vehicle capacity (40–44 seats) with 2 escorts (1 lead, 1 sweeper: 1:20–1:22 ratio) maximizes bottleneck utilization and eliminates curb congestion, whereas waiting for whole-hostel batches (300–500 students) forces batch-forming delays that multiply average wait times by 6x to 10x. Holding buses for stragglers is operational suicide under scarce resources; proven military (chalk/bump plan) and transit systems enforce strict vehicle cutoffs paired with subgroup ID tokens so stragglers flow seamlessly into subsequent pulses.

### Key Findings
- **Standard Escort Ratios:** Published guidelines require 1:10 to 1:15 for minor school excursions (HCPSS Policy 8100; KSBA Portal), 1:20 to 1:25 for university orientation groups (UMKC Orientation Leader Guidelines), and 1:44 to 1:52 (1 guide/chalk leader per bus) in large-scale civilian/military mass transit (PLOS ONE Hajj Transport Model; US Army FM 55-65).
- **Destructive "Wait for the Whole Hostel" Effect:** In queueing theory and operations management (Factory Physics / Theory of Constraints), process batching (e.g., mustering 500 students before release) introduces massive batch-forming wait time ($W_{batch} = \frac{B-1}{2\lambda}$). For a single-door coach boarding at 2.75–3.0 s/passenger, batching 500 students adds ~25 minutes of dead queueing before the convoy can even depart.
- **Straggler Handling via Bump Plans:** Military movement control (US Army Air Assault / Reception Battalion FM 55-65) and Hajj Tafwij dispatch prohibit holding vehicles for late arrivals. Instead, manifests are bound to vehicle chalk numbers; missing individuals are bumped to the next chalk without stalling the main serial.
- **Overhead Floor of Small Batches:** Reducing batch sizes below single-bus capacity (e.g., 15–20 students) wastes marshal headcount (requires 2 escorts per micro-group), creates head-of-line bus underfill, and multiplies briefing transaction times at loading zones.
- **Legal Duty of Care vs. Habit:** Under common law, universities owe adult students (18+) a duty of ordinary reasonable care (protection from foreseeable physical hazards like live traffic or heat exhaustion) rather than strict *in loco parentis* physical confinement. Demanding that an entire contingent remain physically chained to latecomers is an administrative habit that worsens heatstroke liability.

---

### Comparison of Batch Size and Escort Models

| Batch Size | Escorts Needed | Escort Ratio | Operational Context & Evidence Source | Likely USM Fit |
| :--- | :--- | :--- | :--- | :--- |
| **10–15** | 1–2 | 1:7 – 1:15 | **School Field Trips / Minor Tours** (KSBA Policy 4531R; HCPSS Policy 8100). High supervision for minors. | **No** (exhausts PPSL headcount; causes severe coach underfill). |
| **20–25** | 1 | 1:20 – 1:25 | **University Campus Walking Tours** (UMKC Orientation Leader Packet). Conversational walking groups. | **No** (half of a bus; splits single coach into multiple escorted squads). |
| **40–44** | **2 (1 lead, 1 sweep)** | **1:20 – 1:22** | **Standard Coach Chalk / Military Reception** (US Army FM 55-65; PLOS ONE Hajj Model). Sized 1:1 to single-door tour coach capacity. | **YES** (optimal: 1 lead loads front, 1 sweep clears tail; 100% coach seat utilization). |
| **80–90** | 3–4 | 1:22 – 1:30 | **Two-Bus Convoy** (Saudi Ministry of Hajj Tafwij sub-block). Lead marshal for convoy, 1 sweep at rear. | **Maybe** (requires dual curb bays at Restu and DTSP; induces slight curb idling). |
| **300–500** | 10–20+ | 1:25 – 1:50 | **Whole-Hostel Contingent Muster** (Traditional Malaysian IPTA orientation practice). Hold until hostel is complete. | **NO** (destroys throughput; creates road-shoulder heat piles; holds coaches idle). |

---

### Details

#### 1. Published Escort Ratios
In organized group movements, escort requirements depend heavily on legal status (minors vs. adults) and the physical containment of the mode:
- **K-12 School Trips:** Kentucky School Boards Association (KSBA Policy 4531R) and Howard County Public School System (HCPSS Policy 8100) specify a standard ratio of **1:10** for secondary students, down to **1:6** for primary school.
- **University Orientation Leader (OL) Ratios:** At universities such as UMKC and Univ. of Minnesota, orientation leader-to-student cohorts range between **1:20 and 1:25**. However, these cohorts are designed for academic workshops and walking tours, not vehicle convoys.
- **Mass Transit / Mass Gathering Ratios:** In discrete-event simulation studies of Hajj pilgrim transportation (PLOS ONE, 2023), transport blocks assign **1 guide per bus of 52 passengers** (or 2 guides per 100 pilgrims across a 2-bus platoon). In military logistics (US Army FM 55-65 *Replacement and Movement Operations*), troop movements by bus use a **Chalk Leader** (senior troop/NCO) and an assistant chalk leader per commercial charter coach (44–50 passengers), giving an escort ratio of **2:44 (1:22)**.

#### 2. Straggler Policies and Decoupled Accountability (The "Bump Plan")
Forcing a 500-person cohort or a 44-person bus to wait for the final 5–10% of latecomers collapses system throughput. Proven high-throughput domains explicitly outlaw waiting:
- **The Military "Chalk & Bump Plan" SOP:** In US Army air assault and vehicle convoy doctrine (FM 55-65, 2nd Bn 5th Marines SOP), personnel are assigned to a "Chalk" (a vehicle-load unit). A manifest is maintained. If a soldier is missing when the chalk is called to board, the rule is strict: *"Sticks listed last are bumped first... chalk departs on schedule."* Stragglers fall out of the active chalk, report to a designated marshaling tent, and are re-manifested into the final "straggler chalk" (chalk sweep).
- **Accountability via Decoupled Subgroup Tokens:** Rather than identifying a student by their physical position in a convoy, accountability uses physical tokens (wristband colour corresponding to hostel block, plus a sequential index card or numbered lanyard). When a bus arrives at Restu:
  1. The station marshal counts exactly 44 students off the head of the queue into the boarding bay.
  2. Late stragglers from Block A do not stop Block A's bus; they are simply absorbed into the next available coach bay. Destination marshals at DTSP collect headcount tokens at the door.

#### 3. Quantitative Effect of Cutting Batch Size
Queuing theory (Factory Physics principles and Little's Law: $L = \lambda W$) provides the mathematical proof for why large batches generate catastrophic queues:
- **Batch Arrival Waiting Time:** When moving $N = 500$ students, if students are gathered as a monolithic "process batch" before boarding begins, the average student waits:
  $$W_{wait} = \frac{B - 1}{2 \times \lambda_{arrival}}$$
  For an arrival rate $\lambda = 10$ students/min, waiting for a 500-student batch forces an average wait of **25 minutes** standing idle before boarding even commences.
- **Transfer Batch Sizing (500 $\rightarrow$ 44):** By converting from a process batch of 500 to a transfer batch of 44 (the capacity of one coach), the batch-wait penalty drops from 25 minutes to **2.15 minutes** (a **91.4% reduction in idle waiting**).
- **Empirical Transit Validation:** Levinson's transit dwell equations (TCRP Report 100 / Dueker et al., *Determinants of Bus Dwell Time*) show that single-door coach boarding requires **2.75 to 3.0 seconds per passenger** without luggage. Loading a single 44-passenger bus takes exactly **2.0 to 2.2 minutes**. A continuous pipeline of 44-passenger pulses allows coaches to load, clear the curb, and cycle continuously without backing up the arterial corridor.

#### 4. Overhead of Too-Small Batches (<40 Students)
While operations research favors small transfer batches, batch sizes smaller than the vehicle capacity introduce severe inefficiencies:
- **Capacity Underfill:** If batches are released in groups of 20, but the coach holds 44, buses must either dwell twice as long waiting for a second batch or depart at 45% load factor, requiring more than double the bus runs.
- **Marshal Depletion:** Each independent moving pedestrian batch on a campus road requires a minimum of 2 marshals (1 front guide, 1 rear sweeper) to manage street crossings and keep the line tight. Running batches of 15 students to transport 500 students would require $\lceil 500/15 \rceil \times 2 = 68$ marshals. Using 44-seat batches requires only 2 escorts per operating bus (or 8–10 total rotating escorts for a 4–5 bus circuit).
- **Briefing Transaction Overhead:** Safety and routing briefings require ~60–90 seconds. Doing this for 35 micro-groups consumes excessive staff time compared to briefing one busload inside shaded waiting areas.

#### 5. Duty of Care: Safety Realities vs. Bureaucratic Habit
- **Adult Status in Law:** In Malaysia (Age of Majority Act 1971), university undergraduates (typically 18–19 years old) are legal adults. The historical doctrine of *in loco parentis* (acting with full parental custody and control) does **not** apply to adult university students.
- **The Legal Standard:** Under common tort law (negligence), university administration owes students a duty of **ordinary reasonable care** to provide a reasonably safe environment and protect them from foreseeable risks (such as vehicular traffic, crowd crushes, and heat illness).
- **The Paradox of Monolithic Convoys:** Demanding that an entire hostel of 500 students stand stationary on an unshaded road shoulder until every straggler arrives actively breaches the duty of care by creating a foreseeable, high-probability risk of **heat exhaustion and heatstroke**. Decoupling students into sheltered waiting buffers and dispatching discrete bus-sized packets (44 pax) fulfills legal duty of care while optimizing flow.

---

### Sources
1. **PLOS ONE (2023)** — *Transport of pilgrims during Hajj: Evidence from a discrete event simulation study* (https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0286460). Demonstrates discrete-event batching of 52-passenger buses and guide allocation during mass pilgrim movements.
2. **Transportation Research Board (TRB)** — *Transit Capacity and Quality of Service Manual (TCRP Report 100, Part 4)* (https://onlinepubs.trb.org/onlinepubs/tcrp/docs/tcrp100/Part4.pdf). Details bus dwell time equations (2.75s–3.0s per boarding passenger for single-door coaches).
3. **US Army Field Manual (FM 55-65 / FM 3-99)** — *Replacement and Movement Operations / Airborne and Air Assault Operations* (https://2ndbn5thmar.com/wp-content/uploads/2023/09/HeloSOPMcBreen.pdf; https://legalclarity.org/what-is-a-chalk-in-the-military). Formal doctrine on chalk manifests, chalk commanders, and the bump plan for moving troops without holding for stragglers.
4. **Hopp, W. J. & Spearman, M. L.** — *Factory Physics: Foundations of Manufacturing Management* / Theory of Constraints Batching (https://www.dbrmfg.co.nz/Production%20Batch%20Issues.htm). Mathematical demonstration that lead time and queue wait times shrink proportionally as process batches are split into transfer batches.
5. **Howard County Public School System (HCPSS)** — *Policy 8100 Implementation Procedures: Field Trips* (https://policy.hcpss.org/8000/8100/implementation). Documented standard field trip escort ratios (1:10 for secondary).
6. **University of Missouri-Kansas City (UMKC)** — *Orientation Leader Information Packet* (https://www.umkc.edu/admissions/documents/orientation-leader-packet-2024.pdf). Orientation leader cohort sizing and responsibilities for incoming university cohorts (1:20–1:25).
