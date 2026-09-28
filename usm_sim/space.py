"""Finite waiting space: actual occupants, reservations, and vehicle slots.

Physical capacity is a hard ceiling. Operating limits are reported separately.
A student key occupies one location token at a time.
"""

from __future__ import annotations

from dataclasses import dataclass, field


def _place(places: dict[str, dict], place_id: str | None) -> dict:
    if not place_id:
        return {}
    return places.get(place_id) or {}


G03_FOYER_ENTRANCE_PLACE = {
    "id": "g03_foyer_entrance",
    "latitude_deg": 5.357119,
    "longitude_deg": 100.302499,
    "label": "Bangunan G03 foyer entrance (DK G & DK H, OSM way 94331153)",
    "osm_way": "94331153",
}

G03_SEATING_PLACE = {
    "id": "g03_seating",
    "latitude_deg": 5.357119,
    "longitude_deg": 100.302499,
    "label": "Bangunan G03 seating (Dewan Kuliah G & H overflow)",
    "capacity_students": 600,
    "operating_limit_students": 500,
}

@dataclass
class OccupancyLedger:
    places: dict[str, dict]
    actual: dict[str, int] = field(default_factory=dict)
    reserved: dict[str, int] = field(default_factory=dict)
    vehicles: dict[str, int] = field(default_factory=dict)
    student_at: dict[str, str] = field(default_factory=dict)
    vehicle_at: dict[str, str] = field(default_factory=dict)
    reserved_parts: dict[str, str] = field(default_factory=dict)
    over_limit: dict[str, bool] = field(default_factory=dict)
    flow: list[dict] = field(default_factory=list)
    double_occupancy: list[dict] = field(default_factory=list)
    physical_excess: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        for place_id in self.places:
            self.actual.setdefault(place_id, 0)
            self.reserved.setdefault(place_id, 0)
            self.vehicles.setdefault(place_id, 0)

    def unbounded(self, place_id: str | None) -> bool:
        place = _place(self.places, place_id)
        return place.get("capacity_constraint") == "unbounded"

    def physical_students(self, place_id: str | None) -> int | None:
        if place_id is None or self.unbounded(place_id):
            return None
        place = _place(self.places, place_id)
        raw = place.get("physical_capacity_students")
        if raw is None:
            raw = place.get("capacity_students")
        if raw is None:
            return None
        return int(raw)

    def physical_vehicles(self, place_id: str | None) -> int | None:
        if place_id is None or self.unbounded(place_id):
            return None
        place = _place(self.places, place_id)
        raw = place.get("physical_capacity_vehicles")
        if raw is None:
            raw = place.get("capacity_vehicles")
        if raw is None:
            return None
        return int(raw)

    def operating_limit(self, place_id: str | None) -> int | None:
        place = _place(self.places, place_id)
        raw = place.get("operating_limit_students")
        if raw is None:
            return None
        return int(raw)

    def preceding_place_id(self, place_id: str | None) -> str | None:
        return _place(self.places, place_id).get("preceding_place_id")

    def vehicle_queue_place_id(self, place_id: str | None) -> str | None:
        return _place(self.places, place_id).get("vehicle_queue_place_id")

    def committed(self, place_id: str | None) -> int:
        if not place_id:
            return 0
        return self.actual.get(place_id, 0) + self.reserved.get(place_id, 0)

    def can_enter(self, place_id: str | None, n: int) -> bool:
        cap = self.physical_students(place_id)
        if cap is None:
            return True
        return self.committed(place_id) + n <= cap

    def can_park_vehicle(self, place_id: str | None, n: int = 1) -> bool:
        cap = self.physical_vehicles(place_id)
        if cap is None:
            return True
        return self.vehicles.get(place_id or "", 0) + n <= cap

    def add_background(self, place_id: str, n: int, now_ms: int = 0) -> None:
        if n <= 0:
            return
        self.actual[place_id] = self.actual.get(place_id, 0) + n
        self.flow.append(
            {
                "time_ms": now_ms,
                "place_id": place_id,
                "direction": "in",
                "student_count": n,
                "occupancy_after": self.actual[place_id],
                "reserved_after": self.reserved.get(place_id, 0),
                "kind": "background",
            }
        )

    def locate_members(self, part, token: str, now_ms: int) -> None:
        for member in part.members:
            key = member["student_key"]
            prev = self.student_at.get(key)
            if (
                prev
                and prev != token
                and prev.startswith("place:")
                and token.startswith("place:")
            ):
                self.double_occupancy.append(
                    {
                        "student_key": key,
                        "from": prev,
                        "to": token,
                        "time_ms": now_ms,
                        "part_id": part.part_id,
                    }
                )
            self.student_at[key] = token

    def clear_members(self, part, token: str | None = None) -> None:
        for member in part.members:
            key = member["student_key"]
            prev = self.student_at.get(key)
            if token is None or prev == token:
                self.student_at.pop(key, None)

    def occupy(self, place_id: str, part, now_ms: int) -> bool:
        n = part.student_count
        if not self.can_enter(place_id, n):
            cap = self.physical_students(place_id)
            self.physical_excess.append(
                {
                    "place_id": place_id,
                    "occupancy": self.committed(place_id) + n,
                    "capacity_students": cap,
                    "time_ms": now_ms,
                    "part_id": part.part_id,
                }
            )
            return False
        token = f"place:{place_id}"
        self.locate_members(part, token, now_ms)
        self.actual[place_id] = self.actual.get(place_id, 0) + n
        self.flow.append(
            {
                "time_ms": now_ms,
                "place_id": place_id,
                "direction": "in",
                "student_count": n,
                "occupancy_after": self.actual[place_id],
                "reserved_after": self.reserved.get(place_id, 0),
                "part_id": part.part_id,
            }
        )
        return True

    def vacate(self, place_id: str | None, part, now_ms: int) -> None:
        if not place_id:
            return
        n = part.student_count
        self.actual[place_id] = max(0, self.actual.get(place_id, 0) - n)
        self.clear_members(part, f"place:{place_id}")
        self.flow.append(
            {
                "time_ms": now_ms,
                "place_id": place_id,
                "direction": "out",
                "student_count": n,
                "occupancy_after": self.actual[place_id],
                "reserved_after": self.reserved.get(place_id, 0),
                "part_id": part.part_id,
            }
        )

    def reserve(self, place_id: str, part) -> bool:
        n = part.student_count
        if part.part_id in self.reserved_parts:
            return self.reserved_parts[part.part_id] == place_id
        if not self.can_enter(place_id, n):
            return False
        self.reserved[place_id] = self.reserved.get(place_id, 0) + n
        self.reserved_parts[part.part_id] = place_id
        part.reserved_place_id = place_id
        return True

    def release_reservation(self, part) -> None:
        place_id = self.reserved_parts.pop(part.part_id, None)
        if place_id is None:
            place_id = getattr(part, "reserved_place_id", None)
        if not place_id:
            part.reserved_place_id = None
            return
        self.reserved[place_id] = max(
            0, self.reserved.get(place_id, 0) - part.student_count
        )
        part.reserved_place_id = None

    def convert_reservation(self, part, now_ms: int) -> bool:
        place_id = self.reserved_parts.get(part.part_id) or getattr(
            part, "reserved_place_id", None
        )
        if not place_id:
            return self.occupy(place_id or "", part, now_ms) if place_id else False
        self.reserved[place_id] = max(
            0, self.reserved.get(place_id, 0) - part.student_count
        )
        self.reserved_parts.pop(part.part_id, None)
        part.reserved_place_id = None
        # Reservation already counted against committed occupancy, so add actual
        # without re-checking reserved+actual.
        token = f"place:{place_id}"
        self.locate_members(part, token, now_ms)
        self.actual[place_id] = self.actual.get(place_id, 0) + part.student_count
        self.flow.append(
            {
                "time_ms": now_ms,
                "place_id": place_id,
                "direction": "in",
                "student_count": part.student_count,
                "occupancy_after": self.actual[place_id],
                "reserved_after": self.reserved.get(place_id, 0),
                "part_id": part.part_id,
                "kind": "reservation_converted",
            }
        )
        return True

    def park_vehicle(self, place_id: str, vehicle_id: str) -> bool:
        prev = self.vehicle_at.get(vehicle_id)
        if prev == place_id:
            return True
        if prev:
            self.leave_vehicle(prev, vehicle_id)
        if not self.can_park_vehicle(place_id, 1):
            return False
        self.vehicles[place_id] = self.vehicles.get(place_id, 0) + 1
        self.vehicle_at[vehicle_id] = place_id
        return True

    def leave_vehicle(self, place_id: str | None, vehicle_id: str) -> None:
        if not place_id:
            return
        if self.vehicle_at.get(vehicle_id) != place_id:
            return
        self.vehicles[place_id] = max(0, self.vehicles.get(place_id, 0) - 1)
        self.vehicle_at.pop(vehicle_id, None)

    def max_actual(self, place_id: str) -> int:
        peak = 0
        running = 0
        for row in self.flow:
            if row.get("place_id") != place_id:
                continue
            if row.get("direction") == "in":
                running += int(row.get("student_count") or 0)
            else:
                running -= int(row.get("student_count") or 0)
            if running > peak:
                peak = running
        return max(peak, self.actual.get(place_id, 0))

    def snapshot(self) -> list[dict]:
        rows = []
        for place_id in sorted(self.places):
            rows.append(
                {
                    "place_id": place_id,
                    "occupancy_students": self.actual.get(place_id, 0),
                    "reserved_students": self.reserved.get(place_id, 0),
                    "occupancy_vehicles": self.vehicles.get(place_id, 0),
                }
            )
        return rows

    def integrity(self) -> dict:
        return {
            "double_occupancy_events": list(self.double_occupancy),
            "physical_excess_events": list(self.physical_excess),
        }
