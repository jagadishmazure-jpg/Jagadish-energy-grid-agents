"""Print severity + dispatch on seeded data (rendered into README, checked in CI)."""
import tempfile
from pathlib import Path

from gridops import demo_helpers as H
from gridops.dispatch import Crew, NoCrewAvailable, dispatch
from gridops.severity import classify

with tempfile.TemporaryDirectory() as tmp:
    plan = H.dispatch_plan(H.ensure_db(Path(tmp) / "grid.db"))
print(plan["severity_breakdown"])
print(plan["crew"], plan["score"], plan["tier"])
print(classify("OUT-CLINIC", 150, True, 2.0).breakdown)
near_unqualified = Crew("CREW-VEG", ("vegetation",), 0.0, "day", "available")
far_qualified = Crew("CREW-LINE", ("overhead", "switching"), 25.0, "day", "available")
print("chosen:", dispatch([near_unqualified, far_qualified], {"overhead", "switching"}, "critical").crew_id)
try:
    dispatch([near_unqualified], {"overhead"}, "critical")
except NoCrewAvailable as exc:
    print("NoCrewAvailable:", exc)
