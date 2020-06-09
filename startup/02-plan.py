import bluesky.plans as bp

# $ ipython --profile=qas_pe_count

def its_a_plan():
    yield from bp.count([det1], num=2, delay=2)

def its_b_plan():
    yield from bp.count([detb], num=2, delay=2)

def its_c_plan():
    yield from bp.count([detc], num=2, delay=2)