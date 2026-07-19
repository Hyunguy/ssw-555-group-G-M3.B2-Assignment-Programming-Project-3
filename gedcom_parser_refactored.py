import sys
import itertools
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from prettytable import PrettyTable

MONTH_MAP = {
    'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
    'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
}

VALID_TAGS = {
    0: {'INDI', 'FAM', 'HEAD', 'TRLR', 'NOTE'},
    1: {'NAME', 'SEX', 'BIRT', 'DEAT', 'FAMC', 'FAMS', 'MARR', 'HUSB', 'WIFE', 'CHIL', 'DIV'},
    2: {'DATE'}
}


def parse_date(date_str):
    parts = date_str.strip().split()
    if len(parts) == 3:
        try:
            day = int(parts[0])
            month = MONTH_MAP.get(parts[1].upper(), 0)
            year = int(parts[2])
            if month:
                return date(year, month, day)
        except (ValueError, TypeError):
            pass
    return None


def calculate_age(birt, deat=None):
    end = deat if deat else date.today()
    try:
        age = end.year - birt.year - ((end.month, end.day) < (birt.month, birt.day))
        return age
    except Exception:
        return 'NA'


def parse_gedcom(filename):
    individuals = {}
    families = {}

    current_id = None
    current_type = None
    current_tag = None

    with open(filename, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            parts = line.split(' ', 2)
            if len(parts) < 2:
                continue

            level = parts[0]
            tag = parts[1]
            args = parts[2] if len(parts) > 2 else ''

            if level == '0':
                if args in ('INDI', 'FAM'):
                    current_id = tag.strip("@")
                    current_type = args
                    current_tag = None
                    if args == 'INDI':
                        individuals[current_id] = {
                            'id': current_id,
                            'name': 'NA',
                            'gender': 'NA',
                            'birthday': None,
                            'age': 'NA',
                            'alive': True,
                            'death': None,
                            'child': set(),
                            'spouse': set()
                        }
                    else:
                        families[current_id] = {
                            'id': current_id,
                            'married': None,
                            'divorced': None,
                            'husband_id': 'NA',
                            'husband_name': 'NA',
                            'wife_id': 'NA',
                            'wife_name': 'NA',
                            'children': set()
                        }
                else:
                    current_id = None
                    current_type = None
                    current_tag = None
                continue

            if current_id is None:
                continue

            if level == '1':
                current_tag = tag
                if current_type == 'INDI':
                    if tag == 'NAME':
                        individuals[current_id]['name'] = args.replace('/', '').strip()
                    elif tag == 'SEX':
                        individuals[current_id]['gender'] = args.strip()
                    elif tag == 'FAMC':
                        individuals[current_id]['child'].add(args.strip().strip('@'))
                    elif tag == 'FAMS':
                        individuals[current_id]['spouse'].add(args.strip().strip('@'))
                elif current_type == 'FAM':
                    if tag == 'HUSB':
                        families[current_id]['husband_id'] = args.strip().strip('@')
                    elif tag == 'WIFE':
                        families[current_id]['wife_id'] = args.strip().strip('@')
                    elif tag == 'CHIL':
                        families[current_id]['children'].add(args.strip().strip('@'))

            elif level == '2' and tag == 'DATE':
                parsed = parse_date(args)
                if current_type == 'INDI':
                    if current_tag == 'BIRT':
                        individuals[current_id]['birthday'] = parsed
                    elif current_tag == 'DEAT':
                        individuals[current_id]['death'] = parsed
                        individuals[current_id]['alive'] = False
                elif current_type == 'FAM':
                    if current_tag == 'MARR':
                        families[current_id]['married'] = parsed
                    elif current_tag == 'DIV':
                        families[current_id]['divorced'] = parsed

    for indi in individuals.values():
        if indi['birthday']:
            indi['age'] = calculate_age(indi['birthday'], indi['death'])

    for fam in families.values():
        hid = fam['husband_id']
        wid = fam['wife_id']
        if hid in individuals:
            fam['husband_name'] = individuals[hid]['name']
        if wid in individuals:
            fam['wife_name'] = individuals[wid]['name']

    return individuals, families


def fmt_date(d):
    return d.strftime('%Y-%m-%d') if d else 'NA'


def fmt_set(s):
    return str(s) if s else 'NA'


def print_individuals(individuals):
    t = PrettyTable()
    t.field_names = ['ID', 'Name', 'Gender', 'Birthday', 'Age', 'Alive', 'Death', 'Child', 'Spouse']
    for iid in sorted(individuals.keys()):
        i = individuals[iid]
        t.add_row([
            iid,
            i['name'],
            i['gender'],
            fmt_date(i['birthday']),
            i['age'],
            i['alive'],
            fmt_date(i['death']),
            fmt_set(i['child']) if i['child'] else 'NA',
            fmt_set(i['spouse']) if i['spouse'] else 'NA'
        ])
    print('Individuals')
    print(t)


def print_families(families):
    t = PrettyTable()
    t.field_names = ['ID', 'Married', 'Divorced', 'Husband ID', 'Husband Name', 'Wife ID', 'Wife Name', 'Children']
    for fid in sorted(families.keys()):
        f = families[fid]
        t.add_row([
            fid,
            fmt_date(f['married']),
            fmt_date(f['divorced']),
            f['husband_id'],
            f['husband_name'],
            f['wife_id'],
            f['wife_name'],
            fmt_set(f['children']) if f['children'] else 'NA'
        ])
    print('\nFamilies')
    print(t)


# --- Bad smell #1 fix: Duplicated Code ---
# The original code repeated the same "date > today" check and error string
# four separate times (birthday, death, marriage, divorce). Extracted into
# one helper used by every US01 check below.
def check_future_date(date_value, today, level, entity_id, label):
    if date_value and date_value > today:
        return f"ERROR: {level}: US01: {entity_id}: {label} {fmt_date(date_value)} occurs in the future"
    return None


# --- Bad smell #2 fix: Long Method ---
# run_user_stories() used to be one ~90 line function handling nine unrelated
# user stories at once. Each story is now its own small function with a
# single responsibility, and run_user_stories() just aggregates results.
# US01: Dates before current date (kh)
def check_us01(individuals, families, today):
    errors = []
    for iid, i in individuals.items():
        for e in (
            check_future_date(i['birthday'], today, 'INDIVIDUAL', iid, 'Birthday'),
            check_future_date(i['death'], today, 'INDIVIDUAL', iid, 'Death date'),
        ):
            if e:
                errors.append(e)
    for fid, f in families.items():
        for e in (
            check_future_date(f['married'], today, 'FAMILY', fid, 'Marriage date'),
            check_future_date(f['divorced'], today, 'FAMILY', fid, 'Divorce date'),
        ):
            if e:
                errors.append(e)
    return errors


# US03: Birth before death (kh)
def check_us03(individuals):
    errors = []
    for iid, i in individuals.items():
        if i['birthday'] and i['death'] and i['death'] < i['birthday']:
            errors.append(f"ERROR: INDIVIDUAL: US03: {iid}: Died {fmt_date(i['death'])} before born {fmt_date(i['birthday'])}")
    return errors


# US07: Less than 150 years old (jt)
def check_us07(individuals):
    errors = []
    for iid, i in individuals.items():
        if i['birthday']:
            age = calculate_age(i['birthday'], i['death'])
            if isinstance(age, int) and age >= 150:
                errors.append(f"ERROR: INDIVIDUAL: US07: {iid}: More than 150 years old - Birth date {fmt_date(i['birthday'])}")
    return errors


# US04: Marriage before divorce (mb)
def check_us04(families):
    errors = []
    for fid, f in families.items():
        if f['married'] and f['divorced'] and f['divorced'] < f['married']:
            errors.append(f"ERROR: FAMILY: US04: {fid}: Divorced {fmt_date(f['divorced'])} before married {fmt_date(f['married'])}")
        if f['divorced'] and not f['married']:
            errors.append(f"ERROR: FAMILY: US04: {fid}: Divorced {fmt_date(f['divorced'])} with no marriage date")
    return errors


# US05: Marriage before death of spouses (mb)
# US10: Marriage after 14 (mb)
def check_us05_us10(families, individuals):
    errors = []
    for fid, f in families.items():
        if not f['married']:
            continue
        for spouse_id, role in ((f['husband_id'], 'husband'), (f['wife_id'], 'wife')):
            if spouse_id not in individuals:
                continue
            sb = individuals[spouse_id]['birthday']
            sd = individuals[spouse_id]['death']
            if sb and calculate_age(sb, f['married']) < 14:
                errors.append(f"ERROR: FAMILY: US10: {fid}: Married {fmt_date(f['married'])} before {role} ({spouse_id}) at least 14 years old {fmt_date(sb)}")
            if sd and f['married'] > sd:
                errors.append(f"ERROR: FAMILY: US05: {fid}: Married {fmt_date(f['married'])} after {role} ({spouse_id}) death on {fmt_date(sd)}")
    return errors


# US08: Birth before marriage of parents (jt)
# US09: Birth before death of parents (mb/jt)
def check_us08_us09(families, individuals):
    errors = []
    for fid, f in families.items():
        if not f['married']:
            continue
        hid, wid = f['husband_id'], f['wife_id']
        for cid in f['children']:
            if cid not in individuals:
                continue
            cb = individuals[cid]['birthday']
            if not cb:
                continue
            if cb < f['married']:
                errors.append(f"ERROR: FAMILY: US08: {fid}: Child {cid} born {fmt_date(cb)} before marriage on {fmt_date(f['married'])}")
            if hid in individuals:
                hd = individuals[hid]['death']
                if hd and cb > hd + relativedelta(months=9):
                    errors.append(f"ERROR: FAMILY: US09: {fid}: Child {cid} born {fmt_date(cb)} after 9 months post death of father on {fmt_date(hd)}")
            if wid in individuals:
                wd = individuals[wid]['death']
                if wd and cb > wd:
                    errors.append(f"ERROR: FAMILY: US09: {fid}: Child {cid} born {fmt_date(cb)} after death of mother on {fmt_date(wd)}")
    return errors


# US12: Parents not too old (jt)
def check_us12(families, individuals):
    errors = []
    for fid, f in families.items():
        hid, wid = f['husband_id'], f['wife_id']
        for cid in f['children']:
            if cid not in individuals:
                continue
            cb = individuals[cid]['birthday']
            if not cb:
                continue
            if hid in individuals and individuals[hid]['birthday']:
                father_age = calculate_age(individuals[hid]['birthday'], cb)
                if isinstance(father_age, int) and father_age >= 80:
                    errors.append(f"ERROR: FAMILY: US12: {fid}: Father ({hid}) age {father_age} at birth of child {cid} on {fmt_date(cb)} is not less than 80 years older")
            if wid in individuals and individuals[wid]['birthday']:
                mother_age = calculate_age(individuals[wid]['birthday'], cb)
                if isinstance(mother_age, int) and mother_age >= 60:
                    errors.append(f"ERROR: FAMILY: US12: {wid}: Mother ({wid}) age {mother_age} at birth of child {cid} on {fmt_date(cb)} is not less than 60 years older")
    return errors

# US13: Siblings spacing (jt)
def check_us13(families, individuals):
    errors = []
    for fid, f in families.items():
        siblings_birth = [
            (cid, individuals[cid]['birthday'])
            for cid in f['children']
            if cid in individuals and individuals[cid]['birthday']
        ]
        for (cid1, cb1), (cid2, cb2) in itertools.combinations(siblings_birth, 2):
            earlier, later = (cb1, cb2) if cb1 <= cb2 else (cb2, cb1)
            days_apart = (later - earlier).days
            if days_apart >= 2 and later < earlier + relativedelta(months=8):
                errors.append(f"ERROR: FAMILY: US13: {fid}: Siblings {cid1} ({fmt_date(cb1)}) and {cid2} ({fmt_date(cb2)}) born {days_apart} days apart - not twins (<2 days) and less than 8 months apart")
    return errors

# US16: Male last names in family should match
def check_us16(families, individuals):
    errors = []
    for fid, f in families.items():
        surnames = []
        surnames.append(individuals[f['husband_id']]['name'].split(" ")[1])
        for cid in f['children']:
            if individuals[cid]['gender'] == 'M':
                surnames.append(individuals[cid]['name'].split(" ")[1])
        if len(set(surnames)) != 1:
            errors.append(f"ERROR: FAMILY: US16: {fid}: Last names do not match for all male family members. ({surnames})")
    return errors

# US17: Parents should not marry any descendants
def check_us17(families, individuals):
    def get_descendants(id):
        descendants = set()
        seen = set()
        search_families = set(individuals[id]['spouse'])
        while len(search_families) != 0:
            fid = search_families.pop()
            if fid not in seen:
                seen.add(fid)
                for cid in families[fid]['children']:
                    if cid not in descendants:
                        descendants.add(cid)
                        search_families = search_families.union(individuals[cid]['spouse'])
        return descendants
    errors = []
    for fid, f in families.items():
        hid = f['husband_id']
        for id in get_descendants(hid):
            if fid in individuals[id]['spouse']:
                errors.append(f"ERROR: FAMILY: US17: {fid}: Ancestor {hid} cannot marry descendant {id}.")
        wid = f['wife_id']
        for id in get_descendants(wid):
            if fid in individuals[id]['spouse']:
                errors.append(f"ERROR: FAMILY: US17: {fid}: Ancestor {wid} cannot marry descendant {id}.")
    return errors

# US18: Siblings should not marry (jt)
# US21: Husband -> male, wife -> female (jt)
def check_us18_us21(families, individuals):
    errors = []
    for fid, f in families.items():
        hid, wid = f['husband_id'], f['wife_id']
        if hid not in individuals or wid not in individuals:
            continue
        # US21
        if individuals[hid]['gender'] != 'M':
            errors.append(f"ERROR: FAMILY: US21: {fid}: Husband {hid} has gender '{individuals[hid]['gender']}', expected 'M'")
        if individuals[wid]['gender'] != 'F':
            errors.append(f"ERROR: FAMILY: US21: {fid}: Wife {wid} has gender '{individuals[wid]['gender']}', expected 'F'")
        # US18
        shared_parents = individuals[hid]['child'] & individuals[wid]['child']
        if shared_parents:
            errors.append(f"ERROR: FAMILY: US18: {fid}: Husband {hid} and wife {wid} are siblings (share parent family {sorted(shared_parents)}) but are married to each other")
    return errors

def run_user_stories(individuals, families):
    today = date.today()
    errors = []
    errors += check_us01(individuals, families, today)
    errors += check_us03(individuals)
    errors += check_us04(families)
    errors += check_us05_us10(families, individuals)
    errors += check_us07(individuals)
    errors += check_us08_us09(families, individuals)
    errors += check_us12(families, individuals)
    errors += check_us13(families, individuals)
    errors += check_us16(families, individuals)
    errors += check_us17(families, individuals)
    errors += check_us18_us21(families, individuals)
    return errors


def main():
    if len(sys.argv) != 2:
        print("Usage: python gedcom_parser_refactored.py <gedcom_file>")
        sys.exit(1)

    filename = sys.argv[1]
    individuals, families = parse_gedcom(filename)
    print_individuals(individuals)
    print_families(families)
    print()
    for e in run_user_stories(individuals, families):
        print(e)


if __name__ == '__main__':
    main()
