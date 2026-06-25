from .campus_config import get_campus_options, get_campus_short_options, get_all_campuses, get_org_groups

def campus_options(request):
    return {
        'campus_options': get_campus_options(),
        'campus_short_options': get_campus_short_options(),
        'all_campuses': get_all_campuses(),
        'campus_org_groups': get_org_groups(),
    }
