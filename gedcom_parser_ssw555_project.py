import sys
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

            # Level 0: INDI or FAM records have format: 0 <id> <tag>
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

    # Post-process: calculate ages, resolve names in families
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


def run_user_stories(individuals, families):
    today = date.today()
    errors = []

    for iid, i in individuals.items():
        # US01: Dates before current date (kh)
        if i['birthday'] and i['birthday'] > today:
            errors.append(f"ERROR: INDIVIDUAL: US01: {iid}: Birthday {fmt_date(i['birthday'])} occurs in the future")
        if i['death'] and i['death'] > today:
            errors.append(f"ERROR: INDIVIDUAL: US01: {iid}: Death date {fmt_date(i['death'])} occurs in the future")

        # US03: Birth before death (kh)
        if i['birthday'] and i['death'] and i['death'] < i['birthday']:
            errors.append(f"ERROR: INDIVIDUAL: US03: {iid}: Died {fmt_date(i['death'])} before born {fmt_date(i['birthday'])}")

        # US07: Less than 150 years old (jt)
        if i['birthday']:
            age = calculate_age(i['birthday'], i['death'])
            if isinstance(age, int) and age >= 150:
                errors.append(f"ERROR: INDIVIDUAL: US07: {iid}: More than 150 years old - Birth date {fmt_date(i['birthday'])}")

    for fid, f in families.items():
        # US01: Marriage/divorce in future (kh)
        if f['married'] and f['married'] > today:
            errors.append(f"ERROR: FAMILY: US01: {fid}: Marriage date {fmt_date(f['married'])} occurs in the future")
        if f['divorced'] and f['divorced'] > today:
            errors.append(f"ERROR: FAMILY: US01: {fid}: Divorce date {fmt_date(f['divorced'])} occurs in the future")

        # US04: Marriage before divorce (mb)
        if f['married'] and f['divorced'] and f['divorced'] < f['married']:
            errors.append(f"ERROR: FAMILY: US04: {fid}: Divorced {fmt_date(f['divorced'])} before married {fmt_date(f['married'])}")
        if f['divorced'] and not f['married']:
            errors.append(f"ERROR: FAMILY: US04: {fid}: Divorced {fmt_date(f['divorced'])} with no marriage date")

        # US05: Marriage before death of spouses (mb)
        # US10: Marriage after 14 (mb)
        hid = f['husband_id']
        wid = f['wife_id']
        if hid in individuals and f['married']:
            hb = individuals[hid]['birthday']
            hd = individuals[hid]['death']
            if hb and calculate_age(hb, f['married']) < 14:
                errors.append(f"ERROR: FAMILY: US10: {fid}: Married {fmt_date(f['married'])} before husband ({hid}) at least 14 years old {fmt_date(hb)}")
            if hd and f['married'] > hd:
                errors.append(f"ERROR: FAMILY: US05: {fid}: Married {fmt_date(f['married'])} after husband ({hid}) death on {fmt_date(hd)}")
        if wid in individuals and f['married']:
            wb = individuals[wid]['birthday']
            wd = individuals[wid]['death']
            if wb and calculate_age(wb, f['married']) < 14:
                errors.append(f"ERROR: FAMILY: US10: {fid}: Married {fmt_date(f['married'])} before wife ({wid}) at least 14 years old {fmt_date(wb)}")
            if wd and f['married'] > wd:
                errors.append(f"ERROR: FAMILY: US05: {fid}: Married {fmt_date(f['married'])} after wife ({wid}) death on {fmt_date(wd)}")

        # US08: Birth before marriage of parents (jt)
        # US09: Birth before death of parents (mb/jt)
        if f['married']:
            for cid in f['children']:
                if cid in individuals:
                    cb = individuals[cid]['birthday']
                    if cb and cb < f['married']:
                        errors.append(f"ANOMALY: FAMILY: US08: {fid}: Child {cid} born {fmt_date(cb)} before marriage on {fmt_date(f['married'])}")
                    hd = individuals[hid]['death']
                    if hd and cb > hd + relativedelta(months=9):
                        errors.append(f"ANOMALY: FAMILY: US09: {fid}: Child {cid} born {fmt_date(cb)} after 9 months post death of father on {fmt_date(hd)}")
                    wd = individuals[wid]['death']
                    if wd and cb > wd:
                        errors.append(f"ANOMALY: FAMILY: US09: {fid}: Child {cid} born {fmt_date(cb)} after death of mother on {fmt_date(wd)}")

    for e in errors:
        print(e)


def main():
    if len(sys.argv) != 2:
        print("Usage: python gedcom_parser.py <gedcom_file>")
        sys.exit(1)

    filename = sys.argv[1]
    individuals, families = parse_gedcom(filename)
    print_individuals(individuals)
    print_families(families)
    print()
    run_user_stories(individuals, families)


if __name__ == '__main__':
    main()