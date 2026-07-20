import sys
from datetime import datetime
from prettytable import PrettyTable

TODAY = datetime.now()


def clean_id(raw):
    return raw.replace("@", "").strip()


def parse_date(text):
    if not text:
        return None
    text = text.strip()
    for fmt in ("%d %b %Y", "%b %Y", "%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def read_gedcom(path):
    individuals = {}
    families = {}
    current = None
    current_type = None
    pending_tag = None

    with open(path, "r", encoding="utf-8-sig") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split(" ", 2)
            level = parts[0]
            if len(parts) < 2:
                continue

            if level == "0" and len(parts) >= 3 and parts[2] in ("INDI", "FAM"):
                rec_id = clean_id(parts[1])
                if parts[2] == "INDI":
                    current_type = "INDI"
                    current = rec_id
                    individuals[current] = {
                        "id": current, "name": "", "sex": "",
                        "birth": None, "death": None,
                        "famc": None, "fams": [],
                    }
                else:
                    current_type = "FAM"
                    current = rec_id
                    families[current] = {
                        "id": current, "husb": None, "wife": None,
                        "children": [], "marr": None, "div": None,
                    }
                pending_tag = None
                continue

            if level == "0":
                current = None
                current_type = None
                continue

            if len(parts) < 2:
                continue
            tag = parts[1]
            arg = parts[2] if len(parts) > 2 else ""

            if current_type == "INDI":
                indi = individuals[current]
                if tag == "NAME":
                    indi["name"] = arg.replace("/", "").strip()
                elif tag == "SEX":
                    indi["sex"] = arg.strip()
                elif tag == "FAMC":
                    indi["famc"] = clean_id(arg)
                elif tag == "FAMS":
                    indi["fams"].append(clean_id(arg))
                elif tag == "BIRT":
                    pending_tag = "BIRT"
                elif tag == "DEAT":
                    pending_tag = "DEAT"
                elif tag == "DATE":
                    d = parse_date(arg)
                    if pending_tag == "BIRT":
                        indi["birth"] = d
                    elif pending_tag == "DEAT":
                        indi["death"] = d
                    pending_tag = None

            elif current_type == "FAM":
                fam = families[current]
                if tag == "HUSB":
                    fam["husb"] = clean_id(arg)
                elif tag == "WIFE":
                    fam["wife"] = clean_id(arg)
                elif tag == "CHIL":
                    fam["children"].append(clean_id(arg))
                elif tag == "MARR":
                    pending_tag = "MARR"
                elif tag == "DIV":
                    pending_tag = "DIV"
                elif tag == "DATE":
                    d = parse_date(arg)
                    if pending_tag == "MARR":
                        fam["marr"] = d
                    elif pending_tag == "DIV":
                        fam["div"] = d
                    pending_tag = None

    return individuals, families


def age_at(birth, ref):
    if not birth or not ref:
        return None
    years = ref.year - birth.year - ((ref.month, ref.day) < (birth.month, birth.day))
    return years


def last_name(name):
    if not name:
        return ""
    parts = name.strip().split()
    return parts[-1] if parts else ""


# ---------------- Sprint 1: US01, US03, US04, US05, US07, US08 ----------------

def check_us01(individuals, families):
    """Dates (birth, death, marriage, divorce) must not be after current date."""
    errors = []
    for i in individuals.values():
        if i["birth"] and i["birth"] > TODAY:
            errors.append(f"US01: {i['id']} ({i['name']}) has a birth date in the future")
        if i["death"] and i["death"] > TODAY:
            errors.append(f"US01: {i['id']} ({i['name']}) has a death date in the future")
    for fam in families.values():
        if fam["marr"] and fam["marr"] > TODAY:
            errors.append(f"US01: Family {fam['id']} has a marriage date in the future")
        if fam["div"] and fam["div"] > TODAY:
            errors.append(f"US01: Family {fam['id']} has a divorce date in the future")
    return errors


def check_us03(individuals):
    """Birth must occur before death."""
    errors = []
    for i in individuals.values():
        if i["birth"] and i["death"] and i["death"] < i["birth"]:
            errors.append(f"US03: {i['id']} ({i['name']}) died before they were born")
    return errors


def check_us04(families):
    """Marriage must occur before divorce."""
    errors = []
    for fam in families.values():
        if fam["marr"] and fam["div"] and fam["div"] < fam["marr"]:
            errors.append(f"US04: Family {fam['id']} has a divorce date before the marriage date")
    return errors


def check_us05(individuals, families):
    """Marriage must occur before death of either spouse."""
    errors = []
    for fam in families.values():
        if not fam["marr"]:
            continue
        for role in ("husb", "wife"):
            sid = fam[role]
            if sid and sid in individuals and individuals[sid]["death"]:
                if individuals[sid]["death"] < fam["marr"]:
                    errors.append(f"US05: Family {fam['id']} - {sid} died before the marriage date")
    return errors


def check_us07(individuals):
    """Individuals should be less than 150 years old."""
    errors = []
    for i in individuals.values():
        if not i["birth"]:
            continue
        end = i["death"] if i["death"] else TODAY
        age = age_at(i["birth"], end)
        if age is not None and age >= 150:
            errors.append(f"US07: {i['id']} ({i['name']}) is or was {age} years old")
    return errors


def check_us08(individuals, families):
    """Children should be born after their parents' marriage (and before divorce+9mo)."""
    errors = []
    for fam in families.values():
        if not fam["marr"]:
            continue
        for cid in fam["children"]:
            child = individuals.get(cid)
            if child and child["birth"] and child["birth"] < fam["marr"]:
                errors.append(f"US08: {cid} ({child['name']}) born before parents' marriage in family {fam['id']}")
    return errors


# ---------------- Sprint 2: US02, US06, US09, US10, US12, US13 ----------------

def check_us02_full(individuals, families):
    """Birth must occur before marriage of that individual."""
    errors = []
    for fam in families.values():
        if not fam["marr"]:
            continue
        for role in ("husb", "wife"):
            sid = fam[role]
            spouse = individuals.get(sid)
            if spouse and spouse["birth"] and spouse["birth"] > fam["marr"]:
                errors.append(f"US02: {sid} ({spouse['name']}) was born after their own marriage in family {fam['id']}")
    return errors


def check_us06(individuals, families):
    """Divorce must occur before death of either spouse."""
    errors = []
    for fam in families.values():
        if not fam["div"]:
            continue
        for role in ("husb", "wife"):
            sid = fam[role]
            if sid and sid in individuals and individuals[sid]["death"]:
                if individuals[sid]["death"] < fam["div"]:
                    errors.append(f"US06: Family {fam['id']} - {sid} died before the divorce date")
    return errors


def check_us09(individuals, families):
    """Child must be born before death of both parents (mother's death, father's death + 9 months)."""
    errors = []
    for fam in families.values():
        mother = individuals.get(fam["wife"]) if fam["wife"] else None
        father = individuals.get(fam["husb"]) if fam["husb"] else None
        for cid in fam["children"]:
            child = individuals.get(cid)
            if not child or not child["birth"]:
                continue
            if mother and mother["death"] and child["birth"] > mother["death"]:
                errors.append(f"US09: {cid} ({child['name']}) born after mother's death in family {fam['id']}")
            if father and father["death"]:
                cutoff = father["death"].replace(year=father["death"].year) 
                months_after = father["death"].month + 9
                year_adj = father["death"].year + (months_after - 1) // 12
                month_adj = (months_after - 1) % 12 + 1
                try:
                    cutoff = father["death"].replace(year=year_adj, month=month_adj)
                except ValueError:
                    cutoff = father["death"]
                if child["birth"] > cutoff:
                    errors.append(f"US09: {cid} ({child['name']}) born more than 9 months after father's death in family {fam['id']}")
    return errors


def check_us10(individuals, families):
    """Marriage should be at least 14 years after both spouses' birth dates."""
    errors = []
    for fam in families.values():
        if not fam["marr"]:
            continue
        for role in ("husb", "wife"):
            sid = fam[role]
            spouse = individuals.get(sid)
            if spouse and spouse["birth"]:
                age = age_at(spouse["birth"], fam["marr"])
                if age is not None and age < 14:
                    errors.append(f"US10: {sid} ({spouse['name']}) married at age {age} in family {fam['id']}")
    return errors


def check_us12(individuals, families):
    """Mother should be less than 60 years older, father less than 80 years older than their children."""
    errors = []
    for fam in families.values():
        mother = individuals.get(fam["wife"]) if fam["wife"] else None
        father = individuals.get(fam["husb"]) if fam["husb"] else None
        for cid in fam["children"]:
            child = individuals.get(cid)
            if not child or not child["birth"]:
                continue
            if mother and mother["birth"]:
                diff = age_at(mother["birth"], child["birth"])
                if diff is not None and diff >= 60:
                    errors.append(f"US12: Mother {fam['wife']} is {diff} years older than child {cid} in family {fam['id']}")
            if father and father["birth"]:
                diff = age_at(father["birth"], child["birth"])
                if diff is not None and diff >= 80:
                    errors.append(f"US12: Father {fam['husb']} is {diff} years older than child {cid} in family {fam['id']}")
    return errors


def check_us13(individuals, families):
    """Siblings should be born more than 8 months apart or less than 2 days apart (twins)."""
    errors = []
    for fam in families.values():
        births = []
        for cid in fam["children"]:
            child = individuals.get(cid)
            if child and child["birth"]:
                births.append((cid, child["birth"]))
        births.sort(key=lambda x: x[1])
        for idx in range(len(births) - 1):
            id_a, date_a = births[idx]
            id_b, date_b = births[idx + 1]
            gap_days = (date_b - date_a).days
            if 2 < gap_days < 240:
                errors.append(f"US13: Siblings {id_a} and {id_b} in family {fam['id']} are born {gap_days} days apart")
    return errors


# ---------------- Sprint 3: US14, US15, US16, US17, US18, US19 ----------------

def check_us14(individuals, families):
    """No more than five siblings should be born at the same time (multiple birth)."""
    errors = []
    for fam in families.values():
        birth_groups = {}
        for cid in fam["children"]:
            child = individuals.get(cid)
            if child and child["birth"]:
                birth_groups.setdefault(child["birth"], []).append(cid)
        for date, group in birth_groups.items():
            if len(group) > 5:
                errors.append(f"US14: Family {fam['id']} has {len(group)} siblings born on {date.date()}, exceeding 5")
    return errors


def check_us15(families):
    """There should be fewer than 15 siblings in a family."""
    errors = []
    for fam in families.values():
        count = len(fam["children"])
        if count >= 15:
            errors.append(f"US15: Family {fam['id']} has {count} siblings, which is 15 or more")
    return errors


def check_us16(individuals, families):
    """All male members of a family should have the same last name."""
    errors = []
    for fam in families.values():
        father = individuals.get(fam["husb"]) if fam["husb"] else None
        family_surname = last_name(father["name"]) if father and father["name"] else None
        if not family_surname:
            continue
        for cid in fam["children"]:
            child = individuals.get(cid)
            if child and child["sex"] == "M" and child["name"]:
                if last_name(child["name"]) != family_surname:
                    errors.append(f"US16: Male {cid} ({child['name']}) does not share family surname '{family_surname}' in family {fam['id']}")
    return errors


def _descendants_of(indi_id, individuals, families, seen=None):
    """Return the set of individual IDs descending from a given individual."""
    if seen is None:
        seen = set()
    person = individuals.get(indi_id)
    if not person:
        return seen
    for fid in person["fams"]:
        fam = families.get(fid)
        if not fam:
            continue
        for cid in fam["children"]:
            if cid in seen:
                continue
            seen.add(cid)
            _descendants_of(cid, individuals, families, seen)
    return seen


def check_us17(individuals, families):
    """Parents should not marry any of their own descendants."""
    errors = []
    for fam in families.values():
        husb, wife = fam["husb"], fam["wife"]
        if not husb or not wife:
            continue
        if wife in _descendants_of(husb, individuals, families):
            errors.append(f"US17: {husb} married their own descendant {wife} (family {fam['id']})")
        elif husb in _descendants_of(wife, individuals, families):
            errors.append(f"US17: {wife} married their own descendant {husb} (family {fam['id']})")
    return errors


def check_us18(individuals, families):
    """Siblings should not marry one another."""
    errors = []
    for fam in families.values():
        siblings = set(fam["children"])
        if len(siblings) < 2:
            continue
        for other_fam in families.values():
            spouses = {other_fam["husb"], other_fam["wife"]}
            overlap = spouses & siblings
            if len(overlap) == 2:
                a, b = tuple(overlap)
                errors.append(f"US18: Siblings {a} and {b} from family {fam['id']} are married to each other in family {other_fam['id']}")
    return errors


def _grandparent_families(indiv_id, individuals, families):
    """Return the set of grandparent-family IDs for the parents of an individual's family."""
    result = set()
    child = individuals.get(indiv_id)
    if not child or not child["famc"]:
        return result
    parent_fam = families.get(child["famc"])
    if not parent_fam:
        return result
    for role in ("husb", "wife"):
        pid = parent_fam[role]
        parent = individuals.get(pid) if pid else None
        if parent and parent["famc"]:
            result.add(parent["famc"])
    return result


def check_us21(individuals, families):
    """Husband in a family should be male and wife should be female."""
    errors = []
    for fam in families.values():
        husb = individuals.get(fam["husb"]) if fam["husb"] else None
        wife = individuals.get(fam["wife"]) if fam["wife"] else None
        if husb and husb["sex"] != "M":
            errors.append(f"US21: Husband {fam['husb']} ({husb['name']}) in family {fam['id']} is not male")
        if wife and wife["sex"] != "F":
            errors.append(f"US21: Wife {fam['wife']} ({wife['name']}) in family {fam['id']} is not female")
    return errors


ALL_CHECKS = [
    ("US01", lambda ind, fam: check_us01(ind, fam)),
    ("US02", lambda ind, fam: check_us02_full(ind, fam)),
    ("US03", lambda ind, fam: check_us03(ind)),
    ("US04", lambda ind, fam: check_us04(fam)),
    ("US05", lambda ind, fam: check_us05(ind, fam)),
    ("US06", lambda ind, fam: check_us06(ind, fam)),
    ("US07", lambda ind, fam: check_us07(ind)),
    ("US08", lambda ind, fam: check_us08(ind, fam)),
    ("US09", lambda ind, fam: check_us09(ind, fam)),
    ("US10", lambda ind, fam: check_us10(ind, fam)),
    ("US12", lambda ind, fam: check_us12(ind, fam)),
    ("US13", lambda ind, fam: check_us13(ind, fam)),
    ("US14", lambda ind, fam: check_us14(ind, fam)),
    ("US15", lambda ind, fam: check_us15(fam)),
    ("US16", lambda ind, fam: check_us16(ind, fam)),
    ("US17", lambda ind, fam: check_us17(ind, fam)),
    ("US18", lambda ind, fam: check_us18(ind, fam)),
    ("US21", lambda ind, fam: check_us21(ind, fam)),
]


def run_user_stories(individuals, families):
    all_errors = []
    for name, fn in ALL_CHECKS:
        all_errors.extend(fn(individuals, families))
    return all_errors


def print_individuals(individuals):
    table = PrettyTable()
    table.field_names = ["ID", "Name", "Sex", "Birth", "Death"]
    for i in sorted(individuals.values(), key=lambda x: x["id"]):
        table.add_row([
            i["id"], i["name"], i["sex"],
            i["birth"].date() if i["birth"] else "NA",
            i["death"].date() if i["death"] else "NA",
        ])
    print(table)


def print_families(families):
    table = PrettyTable()
    table.field_names = ["ID", "Husband", "Wife", "Children", "Married", "Divorced"]
    for f in sorted(families.values(), key=lambda x: x["id"]):
        table.add_row([
            f["id"], f["husb"] or "NA", f["wife"] or "NA",
            ", ".join(f["children"]) if f["children"] else "NA",
            f["marr"].date() if f["marr"] else "NA",
            f["div"].date() if f["div"] else "NA",
        ])
    print(table)


def main():
    if len(sys.argv) < 2:
        print("Usage: python gedcom_parser.py <file.ged>")
        sys.exit(1)

    individuals, families = read_gedcom(sys.argv[1])

    print("=== INDIVIDUALS ===")
    print_individuals(individuals)
    print()
    print("=== FAMILIES ===")
    print_families(families)
    print()

    print("=== USER STORY ERRORS/ANOMALIES ===")
    errors = run_user_stories(individuals, families)
    if errors:
        for e in errors:
            print(e)
    else:
        print("No errors found.")


if __name__ == "__main__":
    main()
