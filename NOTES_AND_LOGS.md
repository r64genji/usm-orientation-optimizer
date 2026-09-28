# Field Notes, Messages, & Context Log: USM Orientation

**Location**: Universiti Sains Malaysia (USM), Main Campus, Penang, Malaysia  
**Student Accommodation**: Desasiswa Restu  
**Destination**: Dewan Tuanku Syed Putra (DTSP)  
**Date**: September 17, 2026  

---

## 1. Primary User Transcripts & Telegram Messages

* **09:35 AM**: Uploaded raw Sensor Logger archive (`M08-2026-09-16_22-47-10.zip`) containing GPS telemetry, pedometer counts, and motion activity from morning transit.
* **10:46 AM**: Sent orientation commute footage and photo:
  * `video_15608a256edc.mp4`: Road shoulder queue approaching pedestrian bridge.
  * `img_9edf946ea34d.jpg`: Perspective along road toward elevated bridge.
  * `video_904e64840a87.mp4`: USM coach boarding line.
  * `video_d9bffd781295.mp4`: Staging pavilion pulse toward buses.
  * `video_fedd16a3e55d.mp4`: Massive holding reservoir outside DTSP hall.
  * Text: *"Waiting outside dud"*
* **10:49 AM**: Core issue briefing:
  > *"messages i sent just now are all of my issues in usm. i'm staying in desasiswa restu and i'm walking from the hostel all the way to dtsp inside the campus. the main issue is that transportation takes a long time as you can see from the logs and my gps data. i have walked. i have woken up at 6:30 but only arrived at about 8:30 i think or 9:30."*
  > *"i want you to mainly organise all of this data properly from my sensor data, from my messages, and my notes to help me do further analysis in the future. i should put this all in a folder inside the projects file called usm orientation optimizer."*
* **10:53 AM**: Analysis steering:
  > *"use gemini 3.8 flash for video analysis because it has authentic video understanding videos are mainly for you to estimate how many people there are, what the system is, and how the movements work. so far from what i've asked, they do have next-station reporting for the status so that they can send out in batches."*

---

## 2. Contextual Field Queries (Restu Life & Logistics)

### A. All-Day Sun Exposure & Handheld Fan
* **Problem**: Standing outside for 30–60+ minutes under morning/midday tropical heat with minimal tree canopy along queue corridors.
* **Research Conclusion**: Recommended **JISULIFE Handheld Fan Life 7 (5000mAh)** — high-RPM airflow, brushless motor, lasts 12–19 hours on low/medium to survive 8:00 AM to 10:00 PM orientation schedules without midday battery depletion.

### B. Parcel Receiving & Desasiswa Restu Logistics
* **Facility**: **Restu Box** (Desasiswa Restu's official parcel collection room).
* **Delivery Address Format**:
  ```text
  [Student Name]
  [Matric / Phone Number]
  Restu Box, Desasiswa Restu,
  Universiti Sains Malaysia (USM),
  11800 USM, Pulau Pinang, Malaysia.
  ```

### C. EpiCollect5 Observation Logger
* Form schema configured for orientation week field logging (`epicollect_usm_orientation.json`):
  * Inputs: Date, Time, Observation Type (Activity/venue, Movement/walking, Waiting/batching, Transport, Instruction/schedule change, Official information, General observation), Voice memo, Location, Photo, Video, GPS backup.

---

## 3. Structural Operational Constraints Identified

1. **Hostel Geographic Separation**: Desasiswa Restu is situated along the western/northwestern perimeter of USM campus, requiring either:
   * A 1.47 km straight-line walk (~1.7 km road route) through undulating campus terrain.
   * Campus shuttle bus transit that is vulnerable to severe batching bottlenecks.
2. **Next-Station Status Reporting**:
   * Orientation marshals use two-way radios / group messaging to report hall queue saturation back to the bus dispatch nodes.
   * If DTSP exterior is over capacity, boarding at Restu is paused, converting vehicular transit into a stagnant holding pen.
