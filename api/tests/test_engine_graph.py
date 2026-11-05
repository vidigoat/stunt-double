"""The Effect Graph: consequences linked into units of work, built only from measured effects and the trusted copy."""
import sqlite3

from app.engine import graph

SCHEMA = """CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, email TEXT);
CREATE TABLE stores (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE charges (id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers(id), store_id INTEGER REFERENCES stores(id),
                      amount_cents INTEGER, status TEXT);"""


def _db(tmp_path, n=40):
    p = tmp_path / "before.db"
    db = sqlite3.connect(p)
    db.executescript(SCHEMA)
    db.execute("INSERT INTO stores VALUES (1, 'Main street')")
    for i in range(1, n + 1):
        db.execute("INSERT INTO customers VALUES (?, ?, ?)", (i, f"C{i}", f"c{i}@example.com"))
        db.execute("INSERT INTO charges VALUES (?, ?, 1, 500, 'succeeded')", (100 + i, i))
    db.commit()
    return str(p)


def _refund_effects(ids):
    upd = [{"rowid": 100 + i, "before": {"id": 100 + i, "customer_id": i, "store_id": 1, "amount_cents": 500, "status": "succeeded"},
            "after": {"id": 100 + i, "customer_id": i, "store_id": 1, "amount_cents": 500, "status": "refunded"}, "changed": ["status"]} for i in ids]
    return {"changes": {"charges": {"dropped": False, "created": False, "deleted": [], "inserted": [], "updated": upd}},
            "payments": [{"op": "refund", "charge_id": 100 + i, "amount_cents": 500} for i in ids],
            "emails": [{"to": f"c{i}@example.com", "subject": "Sorry", "body": "..."} for i in ids], "http": []}


def test_each_refund_its_charge_and_its_email_form_one_unit(tmp_path):
    g = graph.build(_refund_effects(range(1, 31)), _db(tmp_path))
    assert g.summary()["units"] == 30 and g.summary()["largest_unit"] == 3
    u = g.units[g.unit_of["refund:0"]]
    assert set(u) == {"refund:0", "row:charges:101", "email:0"}


def test_a_shared_parent_row_does_not_merge_everything(tmp_path):
    # all 30 charges point at the same store: that store is a hub, drawn but not used to join units
    g = graph.build(_refund_effects(range(1, 31)), _db(tmp_path))
    assert "ctx:stores:1" in g.hubs and g.summary()["units"] == 30


def test_ambiguous_links_are_never_guessed(tmp_path):
    p = _db(tmp_path)
    db = sqlite3.connect(p)
    db.execute("INSERT INTO customers VALUES (999, 'Twin', 'c1@example.com')")   # two customers share an address
    db.commit()
    g = graph.build(_refund_effects([1]), p)
    assert g.unit_of["email:0"] != g.unit_of["refund:0"]                          # the email stays its own unit


def test_without_the_trusted_copy_only_measured_rows_link(tmp_path):
    g = graph.build(_refund_effects([1, 2]), None)
    assert g.unit_of["refund:0"] == g.unit_of["row:charges:101"] and g.summary()["units"] == 4   # emails unlinked


def test_export_is_capped_and_self_consistent(tmp_path):
    d = graph.build(_refund_effects(range(1, 41)), _db(tmp_path)).as_dict(max_units=5)
    assert len(d["units"]) == 5
    assert all(a in d["nodes"] and b in d["nodes"] for a, b, _ in d["edges"])
